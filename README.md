# Instagram Agent Skill

Fourteen Claude Code skills for planning, drafting, and reviewing Instagram
content in English and Korean. Start with `/ig-help` to choose a skill.

[한국어 안내](README.ko.md) · [Skill catalog](#the-fourteen-skills) · [Local tools](#local-tools)

This is [2lazzzy](https://github.com/2lazzzy)'s fork of
[Jake Schincariol's original project](https://github.com/Jakeschincariol/instagram-agent-skill).
It adds Korean workflows and text analysis, `/ig-help`, and tested fixes while
preserving the English commands and original attribution.

The pack produces scripts, slide copy, captions, plans, and message drafts.
You handle filming, video editing, publishing, and sending messages. No Instagram
account connection is required to install the pack or use its local text tools.

## Quick start

You need Claude Code to run the skills and **Python 3.9+** for the local helper
scripts. The Python scripts use the standard library; there is no package
installation step. Git is needed for the clone command below.

### Install the skill folders

Run in your terminal:

```bash
git clone https://github.com/2lazzzy/instagram-agent-skill.git
mkdir -p ~/.claude/skills
cp -r instagram-agent-skill/skills/ig-* ~/.claude/skills/
```

Copy every `ig-*` folder, including `ig-i18n`, the shared language library.
For a project-only installation, copy the same folders into that project's
`.claude/skills/` directory instead. Open Claude Code and run `/ig-help`.

### Or install as a plugin

Run these commands inside Claude Code ([plugin installation guide](https://code.claude.com/docs/en/discover-plugins)):

```text
/plugin marketplace add 2lazzzy/instagram-agent-skill
/plugin install instagram-agent@instagram-agent-skill
```

Plugin skills use the namespace `/instagram-agent:ig-help`,
`/instagram-agent:ig-reel`, and so on. This README uses `/ig-*` for brevity;
use the namespaced form when you install the plugin.

## Start with `/ig-help`

Help explains what is available without requiring a voice profile or account access.

```text
/ig-help
/ig-help reels
/ig-help carousels
/ig-help ig-caption
/ig-help --locale ko-KR 릴스
```

A bare command lists the skills. A topic gives a short workflow. An exact skill
name explains its inputs, output, and usage examples. Help itself does not
create content, install anything, or modify your profile.

## The fourteen skills

| Command | Purpose | What to provide | What you get |
| --- | --- | --- | --- |
| `/ig-help` | Choose a skill | Nothing, a topic, or a skill name | Catalog, routes, and examples |
| `/ig-profile` | Review your profile | Profile text or screenshots and goal | Assessment and suggested bio, links, highlights, and pins |
| `/ig-viral` | Research reference posts | Niche, audience, and reference accounts or posts | Research and a swipe file; rankings need account baselines |
| `/ig-plan` | Plan the week | Goal, audience, themes, and real material | Content and engagement plan |
| `/ig-repurpose` | Adapt existing material | Article, transcript, notes, or other source | Angles and drafts routed to the relevant formats |
| `/ig-reel` | Write a Reel | Idea, audience, facts, and duration | Hook options, spoken script, on-screen text, and timed beats |
| `/ig-carousel` | Make a swipe post | Topic, audience, facts, and takeaway | Slide copy, caption, and layout guidance; optional rendering after approval |
| `/ig-human` | Refine wording | Draft and voice preferences | Revised text and wording checks |
| `/ig-caption` | Write the post description | Reel script or carousel copy, goal, and keywords | First line, caption body, call to action, and hashtags |
| `/ig-story` | Plan Stories | Message, goal, and available material | Frame sequence, copy, and interaction prompts |
| `/ig-comment` | Comment on another post | Their post and your perspective | Comment options |
| `/ig-reply` | Answer your post's comments | Your post, received comments, and tone | Reply drafts |
| `/ig-dm` | Draft private messages | Situation, relationship, and purpose | Message drafts and follow-up guidance |
| `/ig-audit` | Review published content | Post history, goals, and available Insights | Performance review and next experiments |

`ig-i18n` supports these skills and is not a fifteenth command.

## Practical workflows

### A Reel from one idea

```text
/ig-reel Explain one mistake freelancers make in project handoffs. Audience:
first-time freelancers. Aim for 30 seconds. Use only the facts in my notes.
```

The skill compares three hooks drawn from 26 formulas, writes the spoken script
and on-screen text, estimates the timing, and includes `/ig-human` wording checks.
Review the result, then ask for the description below the post:

```text
/ig-caption Write a caption for the Reel above. Goal: saves. Keywords: project handoff.
```

The caption is separate from on-screen text or subtitles. You record and edit
the video, review the final assets, and publish it yourself.

### A carousel from your notes

```text
/ig-carousel Turn these project-handoff notes into a carousel for first-time
freelancers. Give each slide one takeaway. Use only the supplied examples.
```

This workflow includes the slide copy, a caption using `/ig-caption`, and
`/ig-human` wording checks. Approve the copy before building the images.
Rendering depends on the design or rendering tools available in your session;
the pack does not bundle a renderer. You review and upload the final files.

You do not need to run `/ig-human` again after these included checks. Use it
independently for an existing draft or a later revision. If you need a topic,
start with `/ig-plan`; use `/ig-viral` for references or `/ig-repurpose` for
material you already have.

## Language and optional voice setup

Supported languages are **English (`en-US`)** and **Korean (`ko-KR`)**. Korean
has its own hook formulas, syllable-based speech timing, caption measurements,
and wording rules. The English command names stay the same.

```text
/ig-reel --locale ko-KR 회의록에서 실행 항목을 정리하는 30초 릴스
/ig-caption --locale en-US Write a caption for the script above.
```

Language selection uses the first available setting in this order:

1. `--locale` in the request or script command.
2. The `IG_LOCALE` environment variable.
3. `locale` in `~/.claude/instagram/config.json`.
4. `Locale:` in `~/.claude/instagram/voice.md`.
5. The language of the request or input text.
6. `en-US` as the fallback.

For bare help commands, `/ig-help` can use the conversation language at step 5.
For mixed-language swipe files, `swipe.py` detects each hook's language unless
`--locale` or `IG_LOCALE` explicitly selects one language for the whole file.

A voice profile is optional setup for consistent writing. Copy
[`templates/voice.md`](templates/voice.md) or
[`templates/voice.ko-KR.md`](templates/voice.ko-KR.md) to
`~/.claude/instagram/voice.md`, then add your audience, tone, examples, and
verified facts. You can also ask Claude to draft it from your own writing.

[`templates/config.example.json`](templates/config.example.json) shows language,
caption settings, and a Korean humanizer allowlist. Its example locale is
`ko-KR`; adjust it before saving as `~/.claude/instagram/config.json`.
Merge settings if you already have a profile. See [the language guide](docs/i18n.md)
for speech calibration and configuration details.

## Local tools

Run these commands from the **repository root** after cloning. The input files
are your own UTF-8 text files; hooks use one candidate per line and scripts use
one beat per line. These six Python entrypoints read local files without making
network requests. Claude responses and research still depend on your host
session and its available tools.

```bash
python3 skills/ig-reel/hookscore.py hooks.txt
python3 skills/ig-reel/beats.py script.txt --target 30
python3 skills/ig-caption/caption.py caption.txt --keywords "project handoff,freelance"
python3 skills/ig-human/humanize.py draft.txt -o clean.txt --report
python3 skills/ig-human/detect.py draft.txt clean.txt
python3 skills/ig-viral/swipe.py captured.tsv --out swipe.md
```

- `hookscore.py` checks hook wording; `beats.py` estimates delivery time.
- `caption.py` checks the caption and previews an estimated feed cutoff.
- `humanize.py` cleans supported wording and formatting issues; `detect.py`
  checks style signals and can compare drafts. Neither proves authorship.
- `swipe.py` reads tab-separated rows with headers such as `account`,
  `followers`, `median`, `views`, and `hook`. Only rows with a positive recent
  account median enter the ranking. Others remain separate references and do
  not affect ranking statistics.

All six accept `--locale ko-KR` and `--help`. Short drafts may return
`INSUFFICIENT` with no overall style score; this is a completed check, not a
request to lengthen the text or keep rewriting until it passes.

## Tests, limits, and further reading

Run the local suite from the repository root:

```bash
python3 -m unittest discover -s tests -t tests
```

It covers reviewed English outputs, Korean analysis, language selection,
command behavior, fresh-install copying, and integration-runner failure cases.
The optional [Claude CLI integration runner](tests/integration/claude_cli.sh)
requires Claude CLI authentication and network access. It exercises real
skill/tool calls and consumes model usage:

```bash
bash tests/integration/claude_cli.sh
```

Scores are writing heuristics, not predictions of reach or proof that a human
wrote something. Timing and feed previews are estimates. Caption limits are
configurable defaults, not a live source of Instagram policy. Research and audits
need accessible references and real metrics; do not invent missing evidence.
Planning does not schedule publication, and message skills produce drafts only.

Browse [the help guide](skills/ig-help/SKILL.md),
[language architecture and configuration](docs/i18n.md),
[hook formulas](skills/ig-reel/hooks.json), and
[the profile rubric](skills/ig-profile/rubric.json) for more detail.

## Credits and license

Made by Jake Schincariol, [opusjake.ai](https://opusjake.ai).
Korean support, help, and maintenance in this fork by
[2lazzzy](https://github.com/2lazzzy).

Licensed under the [MIT License](LICENSE).
