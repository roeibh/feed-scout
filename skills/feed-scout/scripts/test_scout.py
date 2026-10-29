#!/usr/bin/env python3
"""Checks scout.py against synthetic fixtures. Run: python3 -I test_scout.py"""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "scout.py"
G1, G2 = "120363000000000001@g.us", "120363000000000002@g.us"
NOW1 = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc)
NOW2 = NOW1 + timedelta(hours=73)
ME = "15550100@s.whatsapp.net"


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def pid(n):
    return f"74{'0' * 15}{n:02d}"


def person(n):
    return f"155501{n:02d}@s.whatsapp.net"


def msg(i, chat, sender, name, at, text, display=None, from_me=False):
    return {
        "MsgID": f"MSG{i:03d}", "ChatJID": chat, "ChatName": "Group One" if chat == G1 else "Group Two",
        "SenderJID": sender, "SenderName": name, "FromMe": from_me, "Timestamp": iso(at), "Text": text,
        "DisplayText": text if display is None else display, "MediaCaption": "", "ReactionToID": "", "IsForwarded": False,
    }


def h(base, hours):
    return base - timedelta(hours=hours)


FIRST_BATCH = [
    msg(1, G1, person(1), "Alice Example", h(NOW1, 3), f"New post https://www.linkedin.com/posts/alice-example_topic-activity-{pid(1)}-AbCd?utm_source=share"),
    msg(2, G2, person(2), "Bob Example", h(NOW1, 2), f"Same one: https://www.linkedin.com/feed/update/urn:li:activity:{pid(1)}/"),
    msg(3, G1, ME, "Me Example", h(NOW1, 1), f"My post https://www.linkedin.com/posts/me-example_x-ugcPost-{pid(3)}-XyZw", from_me=True),
    msg(4, G1, person(3), "Carol Example", h(NOW1, 1), "", display="(message)"),
    msg(5, G1, person(3), "Carol Example", h(NOW1, 0.5), "Read https://example.com/article?x=1 and https://www.linkedin.com/company/example-co/"),
    msg(6, G1, person(4), "Dan Example", h(NOW1, 50), f"Old https://www.linkedin.com/posts/dan_x-activity-{pid(6)}-Ab"),
    msg(7, G1, person(2), "Bob Example", h(NOW1, 0.33), "Any intro to someone at Example Corp? https://www.linkedin.com/in/bob-example/"),
    msg(8, G1, person(1), "Alice Example", h(NOW1, 0.17), "We are hiring https://www.linkedin.com/jobs/view/4000000001/?refId=abc"),
    msg(9, G1, person(5), "Erin Example", h(NOW1, 0.08), f"https://www.linkedin.com/feed/update/urn:li:ugcPost:{pid(9)}"),
    msg(10, G1, person(6), "", h(NOW1, 0.07), "https://lnkd.in/eAbC123"),
    msg(11, G1, person(4), "Dan Example", h(NOW1, 0.05), "https://www.linkedin.com/pulse/some-article-dan-example/?trackingId=x"),
    {**msg(14, G1, person(1), "Alice Example", h(NOW1, 0.9), "Nice numbers"), "quoted_msg_id": "MSG003"},
]
SECOND_BATCH = [
    msg(12, G1, person(7), "Gina Example", h(NOW2, 1), f"https://www.linkedin.com/posts/alice-example_topic-ugcPost-{pid(2)}-Zz"),
    msg(13, G2, person(8), "Hank Example", h(NOW2, 2), f"https://www.linkedin.com/feed/update/urn:li:share:{pid(13)}"),
]


def write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def make_runner(home, fixtures):
    env = dict(os.environ, FEED_SCOUT_HOME=str(home), PATH=str(home / "no-bin"))
    env.pop("FEED_SCOUT_FIXTURES", None)

    def run(*args, now=NOW1, ok=True, fixtures_arg=None):
        argv = [sys.executable, "-I", str(SCRIPT), *args, "--fixtures", str(fixtures) if fixtures_arg is None else fixtures_arg, "--now", iso(now)]
        result = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=60)
        assert (result.returncode == 0) == ok, (args, result.returncode, result.stdout, result.stderr)
        assert not result.stderr, (args, result.stderr)
        return json.loads(result.stdout)

    return run


def check_normalize(run):
    cases = {
        f"https://www.linkedin.com/posts/alice-example_topic-activity-{pid(1)}-AbCd?utm_source=share": ("post", f"activity:{pid(1)}"),
        f"https://www.linkedin.com/feed/update/urn:li:activity:{pid(1)}/": ("post", f"activity:{pid(1)}"),
        f"https://www.linkedin.com/posts/bob-example_x-ugcPost-{pid(2)}-Zz": ("post", f"ugcPost:{pid(2)}"),
        f"https://www.linkedin.com/feed/update/urn%3Ali%3AugcPost%3A{pid(2)}": ("post", f"ugcPost:{pid(2)}"),
        f"https://www.linkedin.com/feed/update/urn:li:share:{pid(3)}?trk=x": ("post", f"share:{pid(3)}"),
        "https://www.linkedin.com/pulse/some-article-dan-example/?trackingId=x": ("post", "url:linkedin.com/pulse/some-article-dan-example"),
        "https://www.linkedin.com/in/bob-example/": ("profile", None),
        "https://www.linkedin.com/jobs/view/4000000001/?refId=abc": ("job", None),
        "https://www.linkedin.com/company/example-co/": ("ignored", None),
        "https://example.com/article?x=1": ("other", None),
        f"https://linkedin.com.example.net/posts/x-activity-{pid(4)}-A": ("other", None),
        f"https://www.linkedin.com/posts/example-noam_activity-{pid(4)}": ("post", f"activity:{pid(4)}"),
        f"https://www.linkedin.com/posts/example-noam_ugcPost-{pid(5)}": ("post", f"ugcPost:{pid(5)}"),
        f"https://www.linkedin.com/posts/activity-{pid(6)}": ("post", f"activity:{pid(6)}"),
        f"https://www.linkedin.com/posts/jane-example_daily-physical-activity-30-minutes-activity-{pid(7)}-AbCd": ("post", f"activity:{pid(7)}"),
        f"https://www.linkedin.com/feed/?highlightedUpdateUrn=urn%3Ali%3Aactivity%3A{pid(8)}": ("post", f"activity:{pid(8)}"),
        "https://www.linkedin.com/in/bob-example/recent-activity/all/": ("profile", None),
        "https://lnkd.in/": ("ignored", None),
        "https://lnkd.in/eAbC123\u00e9": ("short", "lnkd:eAbC123"),
        "https://lnkd.in/eAbC123": ("short", "lnkd:eAbC123"),
    }
    rows = run("normalize", *cases)
    for (url, (kind, key)), row in zip(cases.items(), rows):
        assert row["kind"] == kind and row.get("key") == key, (url, row)
        assert "?" not in row["url"], row
    assert rows[-1]["unresolved"] is True
    assert rows[5]["url"] == "https://www.linkedin.com/pulse/some-article-dan-example"
    assert rows[15]["url"] == f"https://www.linkedin.com/feed/update/urn:li:activity:{pid(8)}", rows[15]
    assert rows[-2]["url"] == "https://lnkd.in/eAbC123", rows[-2]


def check_unit():
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(HERE))
    import scout

    after = "2026-11-01T00:00:00Z"
    assert scout.wacli_allowed(["groups", "list", "--limit", "5000"])
    assert scout.wacli_allowed(["messages", "list", "--chat", G1, "--after", after, "--asc", "--limit", "1000", "--cursor", "eyJ2IjoxfQ"])
    for bad in (
        ["send", "text", "--to", "+15550101", "--message", "hi"],
        ["chats", "mark-read", "--jid", G1],
        ["presence", "available"],
        ["messages", "list", "--chat", "--help", "--after", after, "--asc", "--limit", "10"],
        ["messages", "list", "--chat", G1, "--after", after, "--asc", "--limit", "10", "--cursor", "-x"],
        ["contacts", "search", "--store", "--limit", "5"],
        ["sync", "--follow"],
    ):
        assert not scout.wacli_allowed(bad), bad
    assert scout.linkedin_location(f"https://www.linkedin.com/posts/x-activity-{pid(1)}-A")
    for bad in ("https://evil-linkedin.com/x", "https://linkedin.com.example.net/x", "javascript:alert(1)", "/relative", "ftp://www.linkedin.com/x", None):
        assert not scout.linkedin_location(bad), bad
    assert scout.extract_urls("see https://lnkd.in/eAbC123\u200b more") == ["https://lnkd.in/eAbC123"]
    assert scout.is_question("anyone at Example Corp who can intro https://www.linkedin.com/in/bob-example?")
    target = f"https://www.linkedin.com/posts/x_activity-{pid(1)}-A"
    scout.resolve_lnkd = lambda code: target
    assert scout.normalize("https://lnkd.in/eAbC123", resolve=True) == {"url": target, "kind": "post", "key": f"activity:{pid(1)}", "short_key": "lnkd:eAbC123"}


def main():
    check_unit()
    with tempfile.TemporaryDirectory() as tmp:
        home, fixtures = Path(tmp) / "home", Path(tmp) / "fixtures"
        fixtures.mkdir()
        write(fixtures / "groups.json", [{"JID": G1, "Name": "Group One"}, {"JID": G2, "Name": "Group Two"}])
        write(fixtures / "messages.json", FIRST_BATCH)
        write(fixtures / "contacts.json", [{"jid": person(3), "name": "Carol C.", "phone": "15550103", "system_name": "Carol C."}])
        run = make_runner(home, fixtures)

        check_normalize(run)

        error = run("collect", ok=False)
        assert error["error"] and error["fix"], error
        assert "fixtures" in run("status", ok=False, fixtures_arg="")["error"]

        status = run("status")
        assert status["offline"] is True and status["groups"] == [] and status["profile_exists"] is False
        assert status["fixtures"] == os.path.abspath(fixtures) and status["state_dir"] == os.path.abspath(home), status

        groups = run("groups", "--days", "90")
        assert [g["jid"] for g in groups] == [G1, G2] and groups[0]["pod_like"] and not groups[1]["pod_like"], groups
        assert [g["history_starts"] for g in groups] == [iso(h(NOW1, 50)), iso(h(NOW1, 2))], groups

        chosen = run("set-groups", G1, G2)
        assert [(g["jid"], g["name"], g["last_scan"]) for g in chosen] == [(G1, "Group One", None), (G2, "Group Two", None)]

        first = run("collect", "--no-sync")
        assert first["first_run"] is True
        assert first["windows"] == {G1: iso(NOW1 - timedelta(hours=48)), G2: iso(NOW1 - timedelta(hours=48))}, first["windows"]
        assert first["messages_read"] == 10, first["messages_read"]
        assert first["history_starts"] == {G1: iso(h(NOW1, 50)), G2: iso(h(NOW1, 2))}, first["history_starts"]
        assert [(q["sender"], q["group_jid"]) for q in first["questions"]] == [("Bob Example", G1)], first["questions"]
        assert "placeholders_skipped" not in first and run("collect", "--no-sync", "--debug")["placeholders_skipped"] == 1
        posts = {p["key"]: p for p in first["new_posts"]}
        assert set(posts) == {f"activity:{pid(1)}", f"ugcPost:{pid(9)}", "lnkd:eAbC123", "url:linkedin.com/pulse/some-article-dan-example"}, set(posts)
        merged = posts[f"activity:{pid(1)}"]
        assert [s["name"] for s in merged["sharers"]] == ["Alice Example", "Bob Example"], merged
        assert merged["first_shared_at"] == iso(h(NOW1, 3)) and merged["group_jid"] == G1 and "?" not in merged["url"]
        assert posts["lnkd:eAbC123"]["unresolved"] is True and posts["lnkd:eAbC123"]["sharers"][0]["name"] == "+15550106"
        assert [p["key"] for p in first["own_posts"]] == [f"ugcPost:{pid(3)}"]
        assert first["non_linkedin_links"] == 1 and first["ignored_linkedin_links"] == 1
        assert [p["url"] for p in first["profile_links"]] == ["https://www.linkedin.com/in/bob-example"]
        assert [j["url"] for j in first["job_links"]] == ["https://www.linkedin.com/jobs/view/4000000001"]
        assert first["opportunities_hint"] == {"questions": 1}
        assert first["seen_before"] == 0 and first["pending"] == [] and first["pending_expired"] == 0

        record = Path(tmp) / "record.json"
        write(record, {"now": iso(NOW1), "groups_scanned": [G1, G2], "run": [
            {"key": f"activity:{pid(1)}", "ids": [f"activity:{pid(1)}", f"ugcPost:{pid(2)}"], "group_jid": G1, "status": "seen", "n": 1,
             "action": "comment", "scores": {"v": [2, 2, 1, 1], "fit": 2, "flags": []}, "topic": "platform teams", "author": "Alice Example", "headline": "Staff engineer", "draft": "A draft."},
            {"key": f"ugcPost:{pid(9)}", "ids": [f"ugcPost:{pid(9)}"], "status": "seen", "n": 2, "topic": "tokens", "author": "Erin Example"},
            {"key": "lnkd:eAbC123", "ids": ["lnkd:eAbC123"], "status": "pending"},
            {"key": "url:linkedin.com/pulse/some-article-dan-example", "status": "skipped", "reason": "thin"},
        ]})
        assert run("record", "--input", str(record)) == {"recorded": 4, "seen": 2, "pending": 1, "skipped": 1, "expired": 0}

        done = run("mark", "done", "1", "--text", "What I posted")
        assert done[0]["status"] == "done" and done[0]["posted_text"] == "What I posted" and done[0]["draft"] == "A draft." and done[0]["headline"] == "Staff engineer" and done[0]["done_at"] == iso(NOW1), done
        not_for_me = run("mark", "not-for-me", "2")
        assert not_for_me[0]["status"] == "skipped" and not_for_me[0]["reason"] == "not for me", not_for_me
        assert run("mark", "done", "7", ok=False)["error"]

        write(fixtures / "messages.json", FIRST_BATCH + SECOND_BATCH)
        second = run("collect", "--no-sync", now=NOW2)
        assert second["first_run"] is False and second["windows"] == {G1: iso(NOW1), G2: iso(NOW1)}, second["windows"]
        assert second["messages_read"] == 2 and second["seen_before"] == 1, second
        assert [p["key"] for p in second["new_posts"]] == [f"share:{pid(13)}"]
        assert second["pending"] == [] and second["pending_expired"] == 1

        write(record, {"now": iso(NOW2), "groups_scanned": [G1, G2], "run": []})
        assert run("record", "--input", str(record), now=NOW2)["expired"] == 1
        skipped = {e["key"]: e["reason"] for e in run("history", "--status", "skipped", now=NOW2)}
        assert skipped == {f"ugcPost:{pid(9)}": "not for me", "lnkd:eAbC123": "older than 72h", "url:linkedin.com/pulse/some-article-dan-example": "thin"}, skipped
        assert [e["key"] for e in run("history", "--status", "done", now=NOW2)] == [f"activity:{pid(1)}"]
        assert [e["key"] for e in run("history", "--grep", "erin", now=NOW2)] == [f"ugcPost:{pid(9)}"]

        status = run("status", now=NOW2)
        assert status["history_count"] == 4 and status["pending_count"] == 0 and all(g["last_scan"] == iso(NOW2) for g in status["groups"])

        questions = run("messages", "--questions", now=NOW2)
        assert [(q["sender"], q["links"]) for q in questions] == [("Bob Example", ["https://www.linkedin.com/in/bob-example"])], questions

        members = {m["jid"]: m for m in run("members", now=NOW2)}
        assert ME not in members and members[person(3)]["contact_name"] == "Carol C." and members[person(3)]["phone"] is None
        assert members[person(6)]["phone"] == "+15550106" and members[person(1)]["linkedin_links_shared"] == 2

        stats = run("stats", now=NOW2)
        assert stats["messages"] == 13 and stats["linkedin_links"] == 12 and stats["other_links"] == 1, stats
        assert [(o["key"], o["replies"]) for o in stats["own_shared"]] == [(f"ugcPost:{pid(3)}", 1)], stats["own_shared"]
        assert [(q["sender"], q["later_messages_48h"]) for q in stats["questions"]] == [("Bob Example", 4)], stats["questions"]
        assert stats["history_starts"] == {G1: iso(h(NOW1, 50)), G2: iso(h(NOW1, 2))}, stats["history_starts"]

        now3 = NOW2 + timedelta(hours=5)
        write(record, {"now": iso(NOW2), "groups_scanned": [], "run": [
            {"key": f"share:{pid(13)}", "ids": [f"share:{pid(13)}"], "status": "pending", "scores": {"v": [1, 1, 1, 1], "fit": 1, "flags": []}},
        ]})
        run("record", "--input", str(record), now=NOW2)
        reshare = msg(15, G1, person(9), "Ivy Example", h(now3, 1), f"https://www.linkedin.com/feed/update/urn:li:share:{pid(13)}")
        write(fixtures / "messages.json", FIRST_BATCH + SECOND_BATCH + [reshare])
        third = run("collect", "--no-sync", now=now3)
        assert third["seen_before"] == 0 and third["new_posts"] == [], third
        assert [(p["key"], [s["name"] for s in p["new_sharers"]]) for p in third["pending"]] == [(f"share:{pid(13)}", ["Ivy Example"])], third["pending"]

        run2 = make_runner(Path(tmp) / "home2", fixtures)
        bad = Path(tmp) / "bridge.json"
        write(bad, {"now": iso(NOW1), "run": [{"key": "activity:1", "ids": "activity:1", "status": "seen"}]})
        assert "ids" in run2("record", "--input", str(bad), ok=False)["error"]
        for n, key in ((2, f"ugcPost:{pid(20)}"), (1, f"activity:{pid(21)}")):
            write(bad, {"now": iso(NOW1), "run": [{"key": key, "status": "seen", "n": n}]})
            run2("record", "--input", str(bad))
        run2("mark", "done", "1", "--text", "posted words")
        write(bad, {"now": iso(NOW1), "run": [{"key": "lnkd:bridge", "ids": ["lnkd:bridge", f"ugcPost:{pid(20)}", f"activity:{pid(21)}"], "status": "seen", "url": "https://lnkd.in/bridge"}]})
        run2("record", "--input", str(bad))
        bridged = run2("history")
        assert [(e["status"], e.get("posted_text"), len(e["ids"]), e["urls"]) for e in bridged] == [("done", "posted words", 3, ["https://lnkd.in/bridge"])], bridged

        written = sorted(p.name for p in home.iterdir())
        assert written == ["groups.json", "history.jsonl", "last_run.json"], written
    print("ok")


if __name__ == "__main__":
    main()
