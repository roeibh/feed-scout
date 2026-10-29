# Comment drafts

Every comment row gets an angle and a draft. The goal is a comment that adds something the post doesn't already have. Generic praise is the slop this skill exists to filter out. Posted under the user's name, it costs them more than skipping the post would.

## Which facts a draft may use

Only `[public]` facts (LinkedIn profile and posts) and `[said]` facts (interview and feedback). Never `[private]` ones.

Why: `[private]` facts come from the user's local files, memory, and commits. A comment is public. Mentioning an unannounced project, a customer, or an internal tool would leak it to everyone who reads the post. If a `[private]` fact would make the perfect angle, pick another angle. The user can turn it into `[said]` by stating it in setup or in a reply.

Never invent facts about the user: numbers, employers, past jobs, things they "also saw". If the profile doesn't say it, the draft doesn't claim it.

## The angle

One concrete hook. It joins a specific point in the post with something real from the profile. Three shapes work:

- **A detail you know:** the post says X; the user has done Y, which adds to or tests X.
- **A disagreement:** the post claims X; the user's experience says otherwise, and says why.
- **A question from your own work:** the post solved X; the user is stuck on a close cousin of X and asks the one question that would help them.

When no `[public]` or `[said]` fact fits, the angle is a specific question or disagreement about the post itself, with no profile fact. This is common for VIP posts with FIT 0. A sharp question about the post is still worth posting.

Write the angle for the user, not for the post: two or three plain sentences saying what the post says, what the user brings, and what to do with it.

## The draft

- 1 to 3 sentences, in English, whatever the post's language. For a Hebrew post add one line under the block: "The post is in Hebrew. The draft is in English."
- In the user's voice. Use the Voice notes and samples in `profile.md`, and the `voice:` lines in Learned. Newer Learned lines win over older notes.
- Lead with the substance: the question, the number, the disagreement.
- Don't repeat a point a top comment already made. Another "same here" adds nothing.
- The user edits it before posting. Give them something worth editing, not a template.

## Bans

Never in a draft or a share message:

- Restating the post back to its author.
- Praise-only openers.
- "Great insight", "Thanks for sharing", "This resonates".
- Contrast frames ("It's not X. It's Y.").
- Emoji bullets.
- Hashtags.

## Trope list

Written for this project. Check every draft and share message against it before showing it.

1. **Applause openers:** "Love this", "So true", "Spot on", "Well said", "This is gold", "Couldn't agree more", or "Congrats!" with nothing after it.
2. **The echo:** the first sentence sums up what the author just said.
3. **Borrowed weight:** "This is so important", "More people need to hear this", "A masterclass in…".
4. **Buzzwords:** unlock, game-changer, deep dive, journey, landscape, ecosystem, elevate, supercharge, next level.
5. **Throat-clearing:** "As someone who…", "I couldn't help but notice", "Here's the thing", "Let that sink in".
6. **Rhythm triplets:** three adjectives or three short clauses in a row, there for the beat ("faster, cheaper, and simpler").
7. **The empty question:** "Thoughts?", "What do you think?", "How about you?" with nothing specific in it.
8. **The pivot to self:** steering toward the user's product, job search, or own post.
9. **Filler wisdom:** "In today's fast-paced world", "At the end of the day", "It all comes down to…".
10. **Decoration:** exclamation stacks, emoji at the end of every sentence, tagging people who aren't in the thread.
11. **Thanking the journey:** "Thank you for sharing your journey", "Proud of you".
12. **The swap test:** if the draft would fit under a different post, it is a trope even when no phrase above shows up.

## Check before showing

For each draft:

1. Every fact about the user is `[public]` or `[said]`, and each one is on the `uses:` line.
2. No ban and no trope. If one hits, rewrite. Don't just delete the phrase.
3. It passes the swap test: it names something only this post has.
4. It is 3 sentences or fewer.

## Block format

One block per comment row, below the table, numbered like the row:

```
3 · Yael K. · AI reviewer on 80 PRs
Angle: She counts the real catches but not the false alarms. You said review noise is why your team hasn't turned an AI reviewer on. Ask how many of its comments she dismissed.
Draft: "How many of its comments did you dismiss as noise? Review noise is why we haven't turned one on, so that number decides it for us."
uses: [said] review noise is why your team hasn't turned an AI reviewer on
repost: your take reuses this angle
```

- The header is the row number, the author, and a few words naming the post.
- `uses:` lists every profile fact the angle used, with its tag. When none fit, write `uses: no profile facts; the angle is a question about the post itself`.
- For a `comment + repost with your take` row, add `repost: your take reuses this angle`.
- For a Hebrew post, add `The post is in Hebrew. The draft is in English.`

## Good and bad, made up

Post: "We moved from nightly batch jobs to streaming. Freshness went from 6 hours to 4 minutes. The cloud bill went up 30%, and I'd do it again."

- Bad: "Great insight! Real-time data is a game-changer for every business. Thanks for sharing!" (applause opener, buzzword, no point from the post, fits any post.)
- Bad: "So you moved to streaming and freshness went from 6 hours to 4 minutes." (the echo.)
- Good, with the `[said]` fact "moving nightly batch jobs to streaming": "We're halfway through the same move. Where did the extra 30% come from: compute, or the always-on brokers?"
- Good, with no profile fact: "Did most of your consumers need 4 minutes, or would 30 have done? A 30-minute batch might have kept most of that 30% off the bill."
