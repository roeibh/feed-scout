# Scoring

Two questions, kept apart: is the post good (VALUE), and is it for this user (FIT). Style is a side note.

Why keep them apart: a great post on a topic the user doesn't care about is still a great post, and a weak post on their favorite topic is still weak. Mixing the two hides both.

Why style is only a note: most of the group writes English as a second language, and many people use AI tools to help them write. Judging surface style would bury real expertise and reward polished fluff. Value comes first.

## VALUE (0 to 8)

Score four parts, 0 to 2 each. For every part above 0, keep one short quote from the post that backs it.

| Part | 0 | 1 | 2 |
|---|---|---|---|
| V1 Specific | no numbers, names, or tools, or only decoration | some specifics, but the argument doesn't rest on them | real numbers, dates, named tools, companies, or people carry the argument |
| V2 First-hand | generic advice, or someone else's story retold | the author was there, but gives little detail | something the author did, measured, shipped, or got wrong, with detail only they would know |
| V3 Arguable | a truism nobody would dispute ("communication matters") | a mild take | a claim a competent peer could disagree with |
| V4 Usable | nothing to try | a vague tip | something the reader can try, copy, or check: a config, a checklist, a query, a number to compare against |

Example, made up. "We cut our Postgres bill 44% in a month. Most of it came from one change: we stopped autovacuum fighting our append-only tables. I think the default settings are wrong for most event tables. Our config is in the first comment."
- V1 2: "44% in a month"
- V2 2: "we stopped autovacuum fighting our append-only tables"
- V3 2: "the default settings are wrong for most event tables"
- V4 2: "Our config is in the first comment"
- VALUE 8.

Example, made up. "Data is the new oil. Leaders who invest in data culture win. Agree?"
- VALUE 0. Style flag: bait.

## FIT (0 to 2)

How much the post overlaps with the profile's topics, role, and current work.

- **0:** no overlap. Also 0 when the topic is on the Ignore list.
- **1:** nearby. Same field from another side, or it touches a Want topic in passing.
- **2:** central to a Want topic or to what the user is building now.

Use every profile fact for FIT, `[private]` ones included. FIT stays between the user and the skill.

Read the Learned section too. `+X` and `↑X` lines raise topic X. A `−X` line lowers X by one step, never below 0. Only the Ignore list skips a post outright.

Language and region don't change FIT. A Hebrew post on a Want topic fits like an English one.

## Style flags (a note only)

- **contrast frame:** "It's not X. It's Y."
- **formula:** a hook line, one-line paragraphs, and generic numbered lessons.
- **bait:** "Agree?", "comment YES", "like if you…".
- **interchangeable:** swap the company name and it still reads true.

Flags change the action in one case only: 3 or more flags with VALUE 4 or less is a skip (see below). Otherwise they are shown in `why N` and nothing more.

## Never count against a post

- Em dashes, grammar, spelling, or vocabulary level.
- Sounding non-native.
- Being in Hebrew, or mixing Hebrew and English.
- Sounding like AI wrote it.
- An AI-detector score. Don't use one.

## Action

Work through these in order.

1. **Skip** when a rule below matches. The first match, in this order, is the reason shown in the skipped line:
   1. `thin`: VALUE 2 or less.
   2. `ignored topic`: the topic is on the Ignore list, whatever the VALUE.
   3. `off-topic`: FIT 0 and VALUE under 6.
   4. `bait/formula`: 3 or more style flags and VALUE 4 or less.
2. **Comment:** VALUE 6 or more and FIT 1 or more. When FIT is 2, it becomes `comment + repost with your take`. A repost only ever comes with a comment, and the take reuses the comment's angle.
3. **Like:** everything else that passed. That is VALUE 3 to 5 with FIT 1 or more, or VALUE 6 or more with FIT 0.
4. **VIP author: one tier up.** Skip becomes like. Like becomes comment. Two exceptions stay skipped: junk (VALUE 1 or less) and an ignored topic. A VIP post with 3 or more flags and VALUE 3 or 4 becomes a like. The scores themselves don't change, so a bumped post never becomes a repost. Mark a bumped row `(VIP ↑)`.

Content comes first: the VIP bump moves a post one step, it never rescues junk.

Edge cases, made up:

| Case | VALUE | FIT | Flags | VIP | Action |
|---|---|---|---|---|---|
| Great post, off the user's topics | 7 | 0 | 0 | no | like |
| Same post, VIP author | 7 | 0 | 0 | yes | comment (VIP ↑), with a question angle |
| Strong and central | 8 | 2 | 0 | no | comment + repost with your take |
| Formula post with real substance | 6 | 1 | 3 | no | comment (flags only bite at VALUE 4 or less) |
| Formula post, VIP author | 4 | 1 | 3 | yes | like (VIP ↑) |
| VIP junk | 1 | 2 | 0 | yes | skip, thin |
| VIP thin post | 2 | 1 | 0 | yes | like (VIP ↑) |
| Ignored topic, strong | 7 | 0 | 0 | either | skip, ignored topic |
| Thin post on a Want topic | 2 | 2 | 0 | no | skip, thin |

## Rank

1. Tier first: comment rows (including comment + repost), then like rows.
2. Inside a tier, `early` posts first. Early means the post is under 2 hours old at scan time.
3. Then VALUE + FIT, highest first.
4. Ties: newer first.

Post age comes from LinkedIn's age label ("3h") when the read had one. Otherwise use the WhatsApp share time.

Old good posts still show; they just never get the `early` boost. Pending posts from earlier runs compete under the same rules. Age counts only through `early` and the last tie-break, so a strong pending post can beat a weaker fresh one.

## Backing quotes

- One per nonzero VALUE part, copied word for word, 15 words at most.
- They go into history with `record` and come back when the user asks `why N`.
- A Hebrew quote stays in Hebrew, followed by an English gloss: `"<Hebrew quote>" (English: three engineers, two time zones)`. The original is the evidence; the gloss is so the user can read it.
