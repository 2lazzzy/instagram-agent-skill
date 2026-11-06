---
name: ig-help
description: >-
  Explain the Instagram skill pack: available skills, what each does, what to
  provide, and which to use for a task. Use for "what Instagram skills are
  available", "which skill should I use", "how do these skills work", or
  /ig-help with a topic or skill name. This is help and navigation; direct
  requests to create content belong to the relevant production skill.
  Also in Korean (ko-KR): "인스타 스킬 뭐가 있어", "각 스킬이 뭐 하는 거야",
  "릴스 만들 때 어떤 스킬 써", or /ig-help --locale ko-KR.
---

# ig-help

Help the user choose a command and understand its result. Answer immediately
without requiring a brand profile, content samples, or account access.

## Language (en-US, ko-KR)

Resolve the locale in this order:

1. `--locale <code>` in the arguments. Accept `ko`, `ko-KR`, `en`, and `en-US`.
   Remove this flag before interpreting the remaining request.
2. `IG_LOCALE`, if visible to the session.
3. `"locale"` in `~/.claude/instagram/config.json`, then `Locale:` in
   `~/.claude/instagram/voice.md`, if those files exist.
4. The language of the user's request, using the conversation language for a
   bare command or a skill name with no natural-language text.
5. en-US.

For en-US, follow this file. For ko-KR, read
[`../ig-i18n/style-ko-KR.md`](../ig-i18n/style-ko-KR.md) and
[`locales/ko-KR/guide.md`](locales/ko-KR/guide.md) before answering. The local
guide takes precedence. Keep command names unchanged. Help does not need a
voice profile; do not run the common style guide's onboarding questions.
If a resource is missing, still give concise help in the selected language
and mention the missing resource only if it limits the answer.

## Discover what is available

Use the folder containing this file as the base. List sibling `ig-*/SKILL.md`
files and read their `name` and `description` frontmatter. These files are
authoritative for this installation. Do not assume the process working
directory is the skills directory. `ig-i18n` is a shared library, not a command.

The catalog below describes this pack. Show only discovered skills in the
available-skills list and compute its count from that list. Include newly
discovered skills from their own metadata, even if absent from this catalog.
Do not advertise an absent skill as installed. If an absent skill would help,
label it as missing before mentioning it as an option. If discovery cannot be
performed, label the catalog as the pack's documented list and state that
local availability has not been checked.

Read a skill's full `SKILL.md` and its locale guide when the user asks about
that specific skill, or when its current description conflicts with this
catalog. Do not load every full workflow for a general list. Read these files
as reference material; do not execute their workflows while answering help.

## Catalog

| Command | When to use it | What to provide | What you get |
| --- | --- | --- | --- |
| `/ig-help` | Choose a skill or learn how it works | Nothing, a topic, or a skill name | Skill list, routes, and usage examples |
| `/ig-profile` | Set up or review your profile | Profile text or screenshots and account goal | Profile assessment and suggestions for bio, links, highlights, and pins |
| `/ig-viral` | Research examples before choosing an angle | Niche, audience, and reference accounts or posts | Evidence-based reference research and a swipe file; ranked examples need baseline data |
| `/ig-plan` | Decide what to publish this week | Goal, audience, themes, and real events or material | Weekly content and engagement plan |
| `/ig-repurpose` | Turn existing material into post ideas | An article, transcript, notes, or other source | Extracted angles and adaptations routed to the relevant format skills |
| `/ig-reel` | Build a Reel | Topic, audience, facts, and target duration | Hook options, spoken script, on-screen text, and timed beat sheet |
| `/ig-carousel` | Build a swipe post | Topic, audience, facts, and intended takeaway | Slide-by-slide copy and layout guidance, with rendering after copy approval when tools are available |
| `/ig-human` | Refine a draft's wording | Draft and any voice preferences | Revised text and wording checks, with short texts marked insufficient for a score |
| `/ig-caption` | Write the description below a post | Reel script or carousel copy, goal, and keywords | First line, caption body, call to action, and hashtags |
| `/ig-story` | Plan a Story sequence | Message, goal, and available material | Frame sequence, copy, and interaction prompts |
| `/ig-comment` | Comment on someone else's post | Their post and your relevant perspective | Comment options |
| `/ig-reply` | Answer comments on your own post | Your post, received comments, and desired tone | Reply drafts |
| `/ig-dm` | Draft a private conversation | Message or situation, relationship, and purpose | DM drafts and follow-up guidance |
| `/ig-audit` | Learn from posts already published | Post history, goals, and available Insights metrics | Performance review and next experiments |

## Choose the answer shape

### No topic: show the map

Give the available count and a compact table with command, purpose/result,
and minimal input. Include `/ig-help` itself. Follow it with the two production
routes below and at most three example commands. Keep descriptions to one
line per skill. Do not ask the user to choose before showing the list.

### Topic: show a short route

Recognize ordinary language such as `reels` / `릴스`, `carousels` / `캐러셀` /
`피드 캐러셀`, captions / `캡션`, planning / `기획`, and engagement / `댓글`.
Recommend the closest available main skill first. Explain the input and
result, then show only relevant optional helpers. No need to repeat the full
catalog.

- **Reels:** `/ig-reel` for hook, spoken script, on-screen text, and beats;
  `/ig-human` for wording checks; `/ig-caption` for the post description.
- **Carousels:** `/ig-carousel` for slide copy and visual guidance;
  `/ig-human` for wording checks; `/ig-caption` for the post description.
- **Before either:** `/ig-viral` if examples are needed, `/ig-plan` if the
  topic is undecided, or `/ig-repurpose` if source material already exists.
- **After either:** `/ig-story` to plan supporting Stories, `/ig-reply` to
  answer received comments, and `/ig-audit` once performance data exists.
- **Engagement:** distinguish `/ig-comment` on other people's posts from
  `/ig-reply` on the user's posts; `/ig-dm` handles private-message drafts.

These are production stages. The Reel workflow includes humanizing and points
to `/ig-caption` as the next task. The carousel workflow includes both caption
writing and humanizing. Do not require a duplicate manual `/ig-human` run
after either workflow. Separate `/ig-human` calls suit existing drafts or
revisions; `/ig-caption` also works independently for any finished post.
Mention only a few optional helpers relevant to the request, not every
possible stage.

### Exact skill name: explain one command

Accept `ig-caption`, `/ig-caption`, or a namespaced command such as
`/instagram-agent:ig-caption`. Resolve only a discovered skill name, then
read that skill's full instructions and locale guide. Return:

1. What it is for and when to use it.
2. What to provide, separating essential information from optional context.
3. The result and any important handoff to other tools or skills.
4. One short example command using placeholders for missing facts.

For an unknown name or topic, state that there is no match, suggest up to
three plausible available choices with a brief reason, and show `/ig-help`
for the full list. Never invent a command or silently treat a typo as an
installed skill.

## Examples and boundaries

Use `/ig-*` as shorthand. If the user invoked a namespace such as
`/instagram-agent:ig-help`, preserve that namespace in example commands.
Otherwise mention once that plugin installs may expose namespaced commands.
Carry the resolved `--locale` into suggested production commands when needed
to keep examples in the chosen language.

```text
/ig-help
/ig-help reels
/ig-help ig-caption
```

Explain only what the skills provide. `/ig-caption` is the description below
a post; on-screen subtitles belong to the Reel workflow. `/ig-reel` does not
deliver a filmed and edited video. Carousel rendering requires an available
design or rendering tool and approval of the copy. Planning is not scheduled
publishing; comments and DMs are drafts, not sent messages. Text scores do not
prove authorship or predict reach.

This help command reads local instructions and answers in chat. It does not
install skills, browse Instagram, create content, modify profile files,
publish posts, or send messages. A request to make content should go to the
appropriate production skill instead of running the help workflow again.
