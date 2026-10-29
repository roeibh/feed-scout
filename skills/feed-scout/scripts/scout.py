#!/usr/bin/env python3
"""feed-scout helper. Reads group chats through wacli (or a fixtures folder),
normalizes LinkedIn links, and keeps scan state. Every command prints one JSON document."""

import argparse
import functools
import http.client
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

FIRST_RUN_HOURS = 48
PENDING_HOURS = 72
DIG_DAYS = 90
POD_LIKE_LINKS = 5
TEXT_CAP = 1000
INSTALL_FIX = "Install wacli (brew install openclaw/tap/wacli), then pair it: wacli auth --history-days 90"
PAIR_FIX = "Run `wacli auth --history-days 90` in your own terminal and scan the QR code from WhatsApp > Linked devices."

GROUP_JID = re.compile(r"\d+(?:-\d+)?@g\.us")
WA_TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
NUM = re.compile(r"\d{1,5}")
CURSOR = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_=-]{0,4095}")
QUERY = re.compile(r"[^\s-][^\x00-\x1f]{0,99}")

# The only wacli commands this script may run. Strings must match exactly; patterns must fullmatch.
WACLI_ALLOWED = (
    ("version",),
    ("auth", "status"),
    ("sync", "--once", "--presence-mode", "quiet", "--refresh-groups", "--idle-exit", "30s"),
    ("groups", "list", "--limit", NUM),
    ("groups", "participants", "list", "--jid", GROUP_JID),
    ("messages", "list", "--chat", GROUP_JID, "--after", WA_TIME, "--asc", "--limit", NUM),
    ("messages", "list", "--chat", GROUP_JID, "--after", WA_TIME, "--asc", "--limit", NUM, "--cursor", CURSOR),
    ("contacts", "search", QUERY, "--limit", NUM),
)
CHILD_ENV = ("HOME", "PATH", "TMPDIR", "LANG", "LC_ALL", "USER", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "SYSTEMROOT", "XDG_STATE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME")

URL_RE = re.compile(r"https?://[^\s<>\"'`\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]+", re.I)
URL_TAIL = ".,;:!?)]}>*_~'\"\u2026"
POST_ID = (
    ("activity", re.compile(r"(?:urn:li:activity:|(?<![A-Za-z0-9])activity-)(\d{15,})", re.I)),
    ("ugcPost", re.compile(r"(?:urn:li:ugcPost:|(?<![A-Za-z0-9])ugcPost-)(\d{15,})", re.I)),
    ("share", re.compile(r"urn:li:share:(\d{15,})", re.I)),
)
LNKD_HOSTS = ("lnkd.in", "www.lnkd.in")
LNKD_CODE = re.compile(r"[A-Za-z0-9_-]{1,64}")
RUN_FIELDS = ("url", "group_jid", "sharer", "status", "reason", "action", "scores", "topic", "author", "headline", "first_line", "gloss", "fit_why", "quotes", "angle", "draft")


class Fail(Exception):
    def __init__(self, error, fix):
        super().__init__(error)
        self.error, self.fix = error, fix


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Fail(message, f"Check the arguments: {self.prog} --help")


# time

def parse_time(value):
    text = re.sub(r"\.\d+", "", str(value).strip()).replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def try_time(value):
    try:
        return parse_time(value) if value else None
    except ValueError:
        return None


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# state

def state_dir():
    return Path(os.path.abspath(os.path.expanduser(os.environ.get("FEED_SCOUT_HOME") or "~/.feed-scout")))


def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Fail(f"{path.name} could not be read as JSON", f"Fix or delete {path}")


def write_text(path, text):
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8", errors="backslashreplace") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError:
        raise Fail(f"Could not write {path.name}", f"Make {path.parent} a writable folder or set FEED_SCOUT_HOME")


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def load_history():
    path = state_dir() / "history.jsonl"
    if not path.exists():
        return []
    entries = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                entries.append(json.loads(line))
            except ValueError:
                raise Fail(f"history.jsonl line {number} is not valid JSON", f"Fix or delete that line in {path}")
    return entries


def save_history(entries):
    write_text(state_dir() / "history.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries))


def str_list(value):
    return isinstance(value, list) and all(isinstance(i, str) and i for i in value)


def entry_ids(entry):
    return {i for i in [entry.get("key"), *(entry.get("ids") or [])] if isinstance(i, str) and i}


def load_groups(required=False):
    groups = read_json(state_dir() / "groups.json", [])
    if not isinstance(groups, list) or not all(isinstance(g, dict) and GROUP_JID.fullmatch(str(g.get("jid"))) for g in groups):
        raise Fail("groups.json has an entry without a valid group id", "Run set-groups again")
    if required and not groups:
        raise Fail("No groups selected yet", "Run setup: scout.py groups, then scout.py set-groups JID [JID ...]")
    return groups


def target_groups(args):
    return [args.group] if args.group else [g["jid"] for g in load_groups(required=True)]


def split_pending(history, now):
    cutoff = now - timedelta(hours=PENDING_HOURS)
    pending = [e for e in history if e.get("status") == "pending"]
    fresh = [e for e in pending if (try_time(e.get("first_seen")) or now) >= cutoff]
    return fresh, len(pending) - len(fresh)


# wacli

def wacli_allowed(args):
    return any(
        len(pattern) == len(args) and all(a == p if isinstance(p, str) else bool(p.fullmatch(a)) for p, a in zip(pattern, args))
        for pattern in WACLI_ALLOWED
    )


def wacli(args, timeout=60):
    if not wacli_allowed(args):
        raise Fail("Refused a wacli command outside the read-only allowlist", "This is a bug in scout.py")
    exe = shutil.which("wacli")
    if not exe:
        raise Fail("wacli is not installed", INSTALL_FIX)
    readonly = args[0] != "sync"
    env = {k: v for k, v in os.environ.items() if (k in CHILD_ENV or k.startswith("WACLI_")) and k != "WACLI_READONLY"}
    if readonly:
        env["WACLI_READONLY"] = "1"
    argv = [exe, *(["--read-only", "--json"] if readonly else []), *args]
    try:
        return subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env, check=False)
    except subprocess.TimeoutExpired:
        raise Fail(f"wacli {args[0]} timed out after {timeout}s", "Try again; if it keeps happening, run `wacli doctor` in your terminal")
    except OSError:
        raise Fail("wacli could not be started", INSTALL_FIX)


def wacli_data(args):
    result = wacli(args)
    name = " ".join(args[:2])
    try:
        envelope = json.loads(result.stdout)
    except ValueError:
        raise Fail(f"wacli {name} did not return JSON", "Update wacli: brew upgrade openclaw/tap/wacli")
    if not isinstance(envelope, dict) or not envelope.get("success"):
        detail = envelope.get("error") if isinstance(envelope, dict) else None
        raise Fail(f"wacli {name} failed: {str(detail or result.stderr.strip() or 'no details')[:200]}", "Check `wacli auth status` and `wacli doctor` in your terminal")
    return envelope.get("data")


@functools.lru_cache(maxsize=None)
def ensure_paired():
    if not (wacli_data(["auth", "status"]) or {}).get("authenticated"):
        raise Fail("WhatsApp is not paired with wacli", PAIR_FIX)


def wacli_status():
    if not shutil.which("wacli"):
        return {"installed": False, "version": None, "paired": False}
    version, paired = None, False
    try:
        version = wacli(["version"]).stdout.strip()[:40] or None
        paired = bool((wacli_data(["auth", "status"]) or {}).get("authenticated"))
    except Fail:
        pass
    return {"installed": True, "version": version, "paired": paired}


def sync():
    result = wacli(["sync", "--once", "--presence-mode", "quiet", "--refresh-groups", "--idle-exit", "30s"], timeout=300)
    if result.returncode != 0:
        tail = (result.stderr.strip().splitlines() or ["no details"])[-1][:200]
        raise Fail(f"wacli sync failed: {tail}", "If `wacli sync --follow` is already running, rerun with --no-sync. Otherwise check the network and `wacli auth status`.")


# sources: fixtures folder or wacli

@functools.lru_cache(maxsize=None)
def fixture(folder, name):
    data = read_json(Path(folder) / name, [])
    if not isinstance(data, list):
        raise Fail(f"{name} in the fixtures folder is not a JSON list", f"Fix {Path(folder) / name}")
    return data


def list_groups(args):
    if args.fixtures:
        groups = fixture(args.fixtures, "groups.json")
    else:
        ensure_paired()
        groups = wacli_data(["groups", "list", "--limit", "5000"]) or []
    return [g for g in groups if isinstance(g, dict)]


def read_messages(args, jid, since, tally=None):
    if args.fixtures:
        raw = [m for m in fixture(args.fixtures, "messages.json") if isinstance(m, dict) and m.get("ChatJID") == jid]
    else:
        ensure_paired()
        raw, cursor = [], None
        while True:
            command = ["messages", "list", "--chat", jid, "--after", iso(since), "--asc", "--limit", "1000"]
            data = wacli_data(command + (["--cursor", cursor] if cursor else [])) or {}
            raw += data.get("messages") or []
            page = data.get("page") or {}
            following = page.get("next_cursor")
            if not page.get("has_more") or not following or following == cursor:
                break
            cursor = following
    kept = []
    for m in raw:
        at = try_time(m.get("Timestamp")) if isinstance(m, dict) else None
        if not at or not since < at <= args.now:
            continue
        if usable(m):
            kept.append(compact(m))
        elif tally is not None and not m.get("ReactionToID"):
            tally["placeholders"] = tally.get("placeholders", 0) + 1
    return sorted(kept, key=lambda m: m["at"])


def history_start(args, jid):
    if args.fixtures:
        times = [try_time(m.get("Timestamp")) for m in fixture(args.fixtures, "messages.json") if isinstance(m, dict) and m.get("ChatJID") == jid]
        times = [t for t in times if t and t <= args.now]
    else:
        ensure_paired()
        data = wacli_data(["messages", "list", "--chat", jid, "--after", "1970-01-01T00:00:00Z", "--asc", "--limit", "1"]) or {}
        times = [try_time(m.get("Timestamp")) for m in data.get("messages") or [] if isinstance(m, dict)]
        times = [t for t in times if t]
    return iso(min(times)) if times else None


def find_contact(args, jid):
    if args.fixtures:
        return next((c for c in fixture(args.fixtures, "contacts.json") if isinstance(c, dict) and c.get("jid") == jid), None)
    user = jid.split("@")[0].split(":")[0]
    if not (user.isascii() and user.isdigit()):
        return None
    data = wacli_data(["contacts", "search", user, "--limit", "5"])
    rows = data.get("contacts") if isinstance(data, dict) else data
    return next((c for c in rows or [] if isinstance(c, dict) and c.get("jid") == jid), None)


# messages and links

def usable(m):
    if m.get("ReactionToID"):
        return False
    return bool(m.get("Text") or m.get("MediaCaption") or m.get("DisplayText") not in (None, "", "(message)"))


def compact(m):
    body = "\n".join(dict.fromkeys(x for x in (m.get("Text"), m.get("MediaCaption")) if x))
    display = m.get("DisplayText") or ""
    return {
        "at": try_time(m.get("Timestamp")),
        "group": m.get("ChatJID") or "",
        "group_name": m.get("ChatName") or "",
        "sender": m.get("SenderName") or "",
        "sender_jid": m.get("SenderJID") or "",
        "id": m.get("MsgID") or "",
        "quoted": m.get("quoted_msg_id") or "",
        "from_me": bool(m.get("FromMe")),
        "text": body or ("" if display == "(message)" else display),
        "urls": extract_urls(body),
    }


def who(m):
    return m["sender"] or ("me" if m["from_me"] else phone_of(m["sender_jid"]) or m["sender_jid"])


def phone_of(jid):
    user, _, server = (jid or "").partition("@")
    user = user.split(":")[0]
    return f"+{user}" if server == "s.whatsapp.net" and user.isascii() and user.isdigit() else None


def extract_urls(text):
    return list(dict.fromkeys(u.rstrip(URL_TAIL) for u in URL_RE.findall(text or "")))


def is_question(text):
    return "?" in URL_RE.sub(lambda u: u.group(0)[len(u.group(0).rstrip(URL_TAIL)):], text or "")


def linkedin_host(host):
    host = (host or "").lower().rstrip(".")
    return bool(re.fullmatch(r"[a-z0-9.-]+", host)) and (host == "linkedin.com" or host.endswith(".linkedin.com"))


def host_of(url):
    try:
        return (urlsplit(url).hostname or "").rstrip(".")
    except ValueError:
        return ""


def is_linkedin(url):
    host = host_of(url)
    return host in LNKD_HOSTS or linkedin_host(host)


def linkedin_location(location):
    try:
        parts = urlsplit(location or "")
    except ValueError:
        return None
    return location if parts.scheme in ("http", "https") and linkedin_host(parts.hostname) else None


@functools.lru_cache(maxsize=None)
def resolve_lnkd(code):
    conn = http.client.HTTPSConnection("lnkd.in", timeout=10, context=ssl.create_default_context())
    try:
        conn.request("GET", f"/{code}", headers={"User-Agent": "Mozilla/5.0"})
        response = conn.getresponse()
        location = response.getheader("Location") if 300 <= response.status < 400 else None
    except (OSError, http.client.HTTPException):
        return None
    finally:
        conn.close()
    return linkedin_location(location)


def normalize(url, resolve=False):
    if "://" not in url:
        url = f"https://{url}"
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").rstrip(".")
    except ValueError:
        return {"url": url, "kind": "other"}
    path = parts.path.rstrip("/")
    clean = f"https://{host}{path}"
    if host in LNKD_HOSTS:
        found = LNKD_CODE.match(path.strip("/"))
        if not found:
            return {"url": clean, "kind": "ignored"}
        code = found.group(0)
        target = resolve_lnkd(code) if resolve else None
        if target:
            link = normalize(target)
            return {**link, "short_key": f"lnkd:{code}"} if link.get("key") else link
        return {"url": f"https://lnkd.in/{code}", "kind": "short", "key": f"lnkd:{code}", "unresolved": True}
    if not linkedin_host(host):
        return {"url": f"{parts.scheme}://{parts.netloc}{parts.path}", "kind": "other"}
    plain = unquote(path)
    for in_query, text in ((False, plain), (True, unquote(parts.query))):
        for name, pattern in POST_ID:
            found = pattern.search(text)
            if found:
                key = f"{name}:{found.group(1)}"
                return {"url": f"https://www.linkedin.com/feed/update/urn:li:{key}" if in_query else clean, "kind": "post", "key": key}
    if plain.startswith("/pulse/"):
        return {"url": clean, "kind": "post", "key": f"url:linkedin.com{path}"}
    if plain.startswith("/in/"):
        return {"url": clean, "kind": "profile"}
    if plain.startswith("/jobs/"):
        return {"url": clean, "kind": "job"}
    return {"url": clean, "kind": "ignored"}


# commands

def cmd_status(args):
    history = load_history()
    offline = bool(args.fixtures)
    return {
        "wacli": {"installed": None, "version": None, "paired": None} if offline else wacli_status(),
        "offline": offline,
        "fixtures": os.path.abspath(args.fixtures) if offline else None,
        "state_dir": str(state_dir()),
        "profile_exists": (state_dir() / "profile.md").exists(),
        "groups": load_groups(),
        "history_count": len(history),
        "pending_count": len(split_pending(history, args.now)[0]),
    }


def cmd_groups(args):
    since = args.now - timedelta(days=args.days)
    rows = []
    for group in list_groups(args):
        jid = group.get("JID") or ""
        if not GROUP_JID.fullmatch(str(jid)):
            continue
        messages = read_messages(args, jid, since)
        links = sum(is_linkedin(u) for m in messages for u in m["urls"])
        rows.append({
            "jid": jid, "name": group.get("Name") or "", "linkedin_links": links, "messages": len(messages), "pod_like": links >= POD_LIKE_LINKS,
            "history_starts": history_start(args, jid),
        })
    return sorted(rows, key=lambda r: (-r["linkedin_links"], -r["messages"], r["name"]))


def cmd_set_groups(args):
    names = {g.get("JID"): g.get("Name") or "" for g in list_groups(args)}
    unknown = [j for j in args.jids if j not in names]
    if unknown:
        raise Fail(f"Unknown group: {', '.join(unknown)}", "Run scout.py groups and copy a jid from its output")
    old = {g["jid"]: g for g in load_groups()}
    groups = [{"jid": j, "name": names[j], "source": "wacli", "last_scan": old.get(j, {}).get("last_scan")} for j in dict.fromkeys(args.jids)]
    write_json(state_dir() / "groups.json", groups)
    return groups


def cmd_collect(args):
    groups = load_groups(required=True)
    if not args.fixtures and not args.no_sync:
        ensure_paired()
        sync()
    history = load_history()
    known = {i for e in history for i in entry_ids(e)}
    out = {
        "now": iso(args.now), "first_run": not any(g.get("last_scan") for g in groups), "windows": {}, "history_starts": {}, "messages_read": 0,
        "new_posts": [], "seen_before": 0, "non_linkedin_links": 0, "ignored_linkedin_links": 0,
        "profile_links": [], "job_links": [], "own_posts": [], "pending": [], "pending_expired": 0, "opportunities_hint": {"questions": 0}, "questions": [],
    }
    out["pending"], out["pending_expired"] = split_pending(history, args.now)
    pending_by_id = {i: e for e in out["pending"] for i in entry_ids(e)}
    tally = {"placeholders": 0}
    shares = {}
    for group in groups:
        since = try_time(group.get("last_scan")) or args.now - timedelta(hours=FIRST_RUN_HOURS)
        out["windows"][group["jid"]] = iso(since)
        out["history_starts"][group["jid"]] = history_start(args, group["jid"])
        for m in read_messages(args, group["jid"], since, tally):
            out["messages_read"] += 1
            if not m["from_me"] and is_question(m["text"]):
                out["opportunities_hint"]["questions"] += 1
                out["questions"].append({"at": iso(m["at"]), "group_jid": group["jid"], "sender": who(m), "text": m["text"][:300]})
            for url in m["urls"]:
                link = normalize(url, resolve=not args.fixtures)
                kind = link["kind"]
                if kind in ("post", "short"):
                    shares.setdefault(link["key"], []).append((m, link, group))
                elif kind == "profile":
                    out["profile_links"].append({"url": link["url"], "sharer": who(m), "at": iso(m["at"])})
                elif kind == "job":
                    out["job_links"].append({"url": link["url"], "sharer": who(m), "at": iso(m["at"]), "message_text": m["text"][:TEXT_CAP]})
                elif kind == "ignored":
                    out["ignored_linkedin_links"] += 1
                else:
                    out["non_linkedin_links"] += 1
    for key, items in shares.items():
        items.sort(key=lambda item: item[0]["at"])
        others = [item for item in items if not item[0]["from_me"]]
        ids = list(dict.fromkeys([key, *(link["short_key"] for _, link, _ in items if link.get("short_key"))]))
        if not others:
            m, link, _ = items[0]
            out["own_posts"].append({"key": key, "url": link["url"], "at": iso(m["at"])})
            continue
        sharers = {}
        for m, _, _ in others:
            sharers.setdefault(m["sender_jid"], {"name": who(m), "jid": m["sender_jid"], "at": iso(m["at"])})
        waiting = next((pending_by_id[i] for i in ids if i in pending_by_id), None)
        if waiting is not None:
            waiting.setdefault("new_sharers", []).extend(sharers.values())
            continue
        if any(i in known for i in ids):
            out["seen_before"] += 1
            continue
        m, link, group = others[0]
        post = {
            "key": key, "ids": ids, "url": link["url"], "group_jid": group["jid"], "group_name": group.get("name") or m["group_name"],
            "sharers": list(sharers.values()), "first_shared_at": iso(m["at"]), "message_text": m["text"][:TEXT_CAP],
        }
        if link.get("unresolved"):
            post["unresolved"] = True
        out["new_posts"].append(post)
    out["new_posts"].sort(key=lambda p: p["first_shared_at"])
    if args.debug:
        out["placeholders_skipped"] = tally["placeholders"]
    return out


def merge_entry(history, item, now):
    ids = {item["key"], *(item.get("ids") or [])}
    matches = [e for e in history if entry_ids(e) & ids]
    urls = [u for e in [*matches, item] for u in [*(e.get("urls") or []), e.get("url")] if isinstance(u, str) and u]
    if matches:
        entry = next((e for e in matches if e.get("status") == "done"), matches[0])
        for other in [e for e in matches if e is not entry]:
            ids |= entry_ids(other)
            entry["first_seen"] = min(entry.get("first_seen") or iso(now), other.get("first_seen") or iso(now))
            history.remove(other)
    else:
        entry = {"key": item["key"], "first_seen": iso(now)}
        history.append(entry)
    was_done = entry.get("status") == "done"
    entry.update({k: item[k] for k in RUN_FIELDS if k in item})
    entry["ids"] = sorted(entry_ids(entry) | ids)
    entry["urls"] = list(dict.fromkeys(urls))
    if was_done:
        entry["status"] = "done"
    if entry["status"] == "seen":
        entry["shown_at"] = iso(now)
    return entry


def cmd_record(args):
    data = read_json(Path(args.input), None)
    run = data.get("run") if isinstance(data, dict) else None
    if not isinstance(run, list):
        raise Fail("The record input must be a JSON object with a run list", "Write {now, groups_scanned, run: [...]} and run record again")
    for item in run:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str) or not item["key"] or item.get("status") not in ("seen", "pending", "skipped"):
            raise Fail("Each run item needs a key and a status of seen, pending or skipped", "Fix the record input and run record again")
        if not str_list(item.get("ids") or []):
            raise Fail(f"ids for {item['key']} must be a list of strings", "Fix the record input and run record again")
    if not str_list(data.get("groups_scanned") or []):
        raise Fail("groups_scanned must be a list of group jids", "Fix the record input and run record again")
    now = try_time(data.get("now")) or args.now
    history = load_history()
    counts = {"recorded": len(run), "seen": 0, "pending": 0, "skipped": 0}
    refs = {}
    for item in run:
        entry = merge_entry(history, item, now)
        counts[item["status"]] += 1
        for ref in (item.get("n"), item.get("letter")):
            if ref not in (None, ""):
                refs[str(ref).strip().lower()] = entry["key"]
    cutoff = now - timedelta(hours=PENDING_HOURS)
    expired = 0
    for entry in history:
        if entry.get("status") == "pending" and (try_time(entry.get("first_seen")) or now) < cutoff:
            entry.update(status="skipped", reason="older than 72h")
            expired += 1
    save_history(history)
    scanned = set(data.get("groups_scanned") or [])
    if scanned:
        groups = load_groups()
        for group in groups:
            if group["jid"] in scanned:
                group["last_scan"] = iso(now)
        write_json(state_dir() / "groups.json", groups)
    last_path = state_dir() / "last_run.json"
    last = read_json(last_path, {})
    if not isinstance(last, dict) or last.get("now") != iso(now):
        last = {"now": iso(now), "refs": {}}
    last.setdefault("refs", {}).update(refs)
    write_json(last_path, last)
    return {**counts, "expired": expired}


def cmd_mark(args):
    last = read_json(state_dir() / "last_run.json", {})
    refs = (last.get("refs") if isinstance(last, dict) else None) or {}
    history = load_history()
    updated = []
    for ref in args.refs:
        key = refs.get(ref.strip().lower())
        entry = next((e for e in history if key and key in entry_ids(e)), None)
        if not entry:
            raise Fail(f"No item {ref} in the last run", "Use a number or letter from the last scan table")
        if args.verdict == "done":
            entry.update(status="done", done_at=iso(args.now))
            if args.text:
                entry["posted_text"] = args.text
        else:
            entry.update(status="skipped", reason="not for me")
        updated.append(entry)
    save_history(history)
    return updated


def touched(entry):
    return max(str(entry.get(k) or "") for k in ("first_seen", "shown_at", "done_at"))


def cmd_history(args):
    rows = load_history()
    if args.status:
        rows = [e for e in rows if e.get("status") == args.status]
    if args.days:
        cutoff = iso(args.now - timedelta(days=args.days))
        rows = [e for e in rows if touched(e) >= cutoff]
    if args.grep:
        needle = args.grep.lower()
        rows = [e for e in rows if needle in json.dumps(e, ensure_ascii=False).lower()]
    return sorted(rows, key=touched, reverse=True)[: args.limit]


def group_names():
    return {g["jid"]: g.get("name") or "" for g in load_groups()}


def cmd_messages(args):
    since = args.now - timedelta(days=args.days)
    names = group_names()
    rows = []
    for jid in target_groups(args):
        for m in read_messages(args, jid, since):
            if args.sender and args.sender.lower() not in f"{who(m)} {m['sender_jid']}".lower():
                continue
            if args.grep and args.grep.lower() not in m["text"].lower():
                continue
            if args.questions and (m["from_me"] or not is_question(m["text"])):
                continue
            rows.append({
                "at": iso(m["at"]), "group": names.get(jid) or m["group_name"], "sender": who(m), "sender_jid": m["sender_jid"],
                "from_me": m["from_me"], "text": m["text"][:TEXT_CAP], "links": [normalize(u)["url"] for u in m["urls"]],
            })
    return sorted(rows, key=lambda r: r["at"], reverse=True)[: args.limit]


def cmd_members(args):
    since = args.now - timedelta(days=DIG_DAYS)
    people = {}

    def person(jid):
        return people.setdefault(jid, {"jid": jid, "display_names": [], "contact_name": None, "phone": None, "messages": 0, "linkedin_links_shared": 0})

    for group_jid in target_groups(args):
        for m in read_messages(args, group_jid, since):
            if m["from_me"] or not m["sender_jid"]:
                continue
            p = person(m["sender_jid"])
            if m["sender"] and m["sender"] not in p["display_names"]:
                p["display_names"].append(m["sender"])
            p["messages"] += 1
            p["linkedin_links_shared"] += sum(is_linkedin(u) for u in m["urls"])
        if not args.fixtures:
            for member in wacli_data(["groups", "participants", "list", "--jid", group_jid]) or []:
                if isinstance(member, dict) and member.get("user_jid"):
                    person(member["user_jid"])
    for p in people.values():
        contact = find_contact(args, p["jid"]) or {}
        names = list(dict.fromkeys(n for n in (contact.get("name"), contact.get("system_name")) if n))
        p["contact_name"] = " / ".join(names) or None
        if not p["display_names"] and not p["contact_name"]:
            p["phone"] = phone_of(p["jid"]) or contact.get("phone") or None
    return sorted(people.values(), key=lambda p: (-p["messages"], -p["linkedin_links_shared"], p["jid"]))


def cmd_stats(args):
    since = args.now - timedelta(days=args.days)
    jids = target_groups(args)
    messages = [m for jid in jids for m in read_messages(args, jid, since)]
    replies = {}
    for m in messages:
        if m["quoted"] and not m["from_me"]:
            replies[m["quoted"]] = replies.get(m["quoted"], 0) + 1
    linkedin = other = 0
    sharers, own, own_ids, questions = {}, {}, {}, []
    for m in messages:
        for url in m["urls"]:
            if not is_linkedin(url):
                other += 1
                continue
            linkedin += 1
            if m["from_me"]:
                link = normalize(url)
                if link["kind"] in ("post", "short"):
                    own.setdefault(link["key"], {"key": link["key"], "url": link["url"], "at": iso(m["at"])})
                    own_ids.setdefault(link["key"], set()).add(m["id"])
            else:
                sharers.setdefault(m["sender_jid"], {"name": who(m), "links": 0})["links"] += 1
        if not m["from_me"] and is_question(m["text"]):
            end = m["at"] + timedelta(hours=48)
            later = sum(1 for x in messages if x["group"] == m["group"] and m["at"] < x["at"] <= end and x["sender_jid"] != m["sender_jid"])
            questions.append({"at": iso(m["at"]), "sender": who(m), "text": m["text"][:300], "later_messages_48h": later})
    for key, share in own.items():
        share["replies"] = sum(replies.get(i, 0) for i in own_ids[key] if i)
    return {
        "window": {"since": iso(since), "until": iso(args.now), "days": args.days},
        "history_starts": {jid: history_start(args, jid) for jid in jids},
        "messages": len(messages),
        "linkedin_links": linkedin,
        "other_links": other,
        "top_sharers": sorted(sharers.values(), key=lambda s: -s["links"])[:10],
        "own_shared": list(own.values()),
        "questions": sorted(questions, key=lambda q: q["at"], reverse=True),
    }


def cmd_sync(args):
    if args.fixtures:
        return {"synced": False, "offline": True}
    ensure_paired()
    sync()
    return {"synced": True, "offline": False}


def cmd_normalize(args):
    return [normalize(u, resolve=not args.fixtures) for u in args.urls]


# arguments

def time_arg(value):
    try:
        return parse_time(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected an ISO 8601 time such as 2026-11-02T08:00:00Z")


def jid_arg(value):
    if not GROUP_JID.fullmatch(value):
        raise argparse.ArgumentTypeError("expected a group jid such as 120363000000000001@g.us")
    return value


def whole(low, high):
    def check(value):
        if not (value.isascii() and value.isdigit() and low <= int(value) <= high):
            raise argparse.ArgumentTypeError(f"expected a whole number from {low} to {high}")
        return int(value)
    return check


def build_parser():
    common = Parser(add_help=False)
    common.add_argument("--fixtures", default=os.environ.get("FEED_SCOUT_FIXTURES") or None, help="offline mode: read this fixtures folder, no wacli, no network")
    common.add_argument("--now", type=time_arg, help="override the clock (ISO 8601)")
    parser = Parser(prog="scout.py", description="feed-scout helper; prints one JSON document")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func):
        p = sub.add_parser(name, parents=[common])
        p.set_defaults(func=func)
        return p

    add("status", cmd_status)
    add("groups", cmd_groups).add_argument("--days", type=whole(1, 3650), default=DIG_DAYS)
    add("set-groups", cmd_set_groups).add_argument("jids", nargs="+", type=jid_arg)
    p = add("collect", cmd_collect)
    p.add_argument("--no-sync", action="store_true")
    p.add_argument("--debug", action="store_true", help="also count skipped (message) placeholders")
    add("sync", cmd_sync)
    add("record", cmd_record).add_argument("--input", required=True)
    p = add("mark", cmd_mark)
    p.add_argument("verdict", choices=("done", "not-for-me"))
    p.add_argument("refs", nargs="+")
    p.add_argument("--text")
    p = add("history", cmd_history)
    p.add_argument("--status", choices=("pending", "seen", "done", "skipped"))
    p.add_argument("--days", type=whole(1, 3650))
    p.add_argument("--grep")
    p.add_argument("--limit", type=whole(1, 10000), default=50)
    p = add("messages", cmd_messages)
    p.add_argument("--group", type=jid_arg)
    p.add_argument("--days", type=whole(1, 3650), default=DIG_DAYS)
    p.add_argument("--sender")
    p.add_argument("--grep")
    p.add_argument("--questions", action="store_true")
    p.add_argument("--limit", type=whole(1, 10000), default=300)
    add("members", cmd_members).add_argument("--group", type=jid_arg)
    p = add("stats", cmd_stats)
    p.add_argument("--group", type=jid_arg)
    p.add_argument("--days", type=whole(1, 3650), default=DIG_DAYS)
    add("normalize", cmd_normalize).add_argument("urls", nargs="+")
    return parser


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        args = build_parser().parse_args(argv)
        if args.fixtures is not None and (not args.fixtures or not Path(args.fixtures).is_dir()):
            raise Fail("The fixtures folder does not exist", "Pass --fixtures DIR with groups.json and messages.json inside")
        args.now = args.now or datetime.now(timezone.utc)
        out = args.func(args)
    except Fail as e:
        print(json.dumps({"error": e.error, "fix": e.fix}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
