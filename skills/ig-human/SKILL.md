---
name: ig-human
description: >-
  Strip the machine fingerprint out of any draft - em dashes, AI slop words,
  invisible watermark characters - and score it against a five-check detection
  panel before it goes out. Use whenever text needs to sound human, when the
  user says humanize, "does this sound like AI", "remove the em dashes",
  "de-slop this", "this sounds like ChatGPT", or before any caption, script,
  comment, reply or DM is shown to the user.
  Also in Korean (ko-KR): "AI 티 나는지 봐 줘", "자연스럽게 다듬어 줘", or /ig-human --locale ko-KR.
---

# ig-human

Two tools live in this folder and they both actually run. Use them. Do not
eyeball this.

```bash
python3 humanize.py draft.txt --report        # clean it, show what changed
python3 detect.py draft.txt                    # score it, five checks
python3 detect.py before.txt after.txt         # prove the delta
```

Both read `slop.json`: 154 stock words and phrases with plain-English
replacements, 18 invisible character classes, 11 typographic substitutions and
16 structural tells. The last block of each list is Instagram-specific, the
vocabulary that only shows up in captions and voiceovers. It is meant to be
edited. If the user has a word they always use that the lexicon strips, take it
out of the file.

## Language (en-US, ko-KR)

This skill writes English by default and Korean on request. Decide the locale
once, before anything else, in this order:

1. `--locale <code>` in the arguments, e.g. `/ig-human --locale ko-KR ...`.
   Remove the flag from the request before using the rest of it. `ko`, `ko-KR`,
   `en` and `en-US` are all accepted.
2. The `IG_LOCALE` environment variable, if the session can see it.
3. `"locale"` in `~/.claude/instagram/config.json`, then a `Locale:` line in
   `~/.claude/instagram/voice.md`.
4. The language the user wrote the request in.
5. en-US.

For en-US, follow this file as written.
For ko-KR, read `../ig-i18n/style-ko-KR.md` and `locales/ko-KR/guide.md` (both
relative to this folder) before writing, and where they differ from the English
examples below, they win. Every line of output is Korean, including labels and
the receipt. Never paste an English example from this file into Korean output,
and never invent a number or a first-person experience to fill one in.

Run every tool in this folder with the locale you chose: `python3 humanize.py draft.txt --locale ko-KR --report`, `python3 detect.py draft.txt --locale ko-KR`. Without the flag the tools follow the same order (IG_LOCALE, profile, the text's own language, en-US), but pass it anyway.

When this skill hands text to another one (`/ig-human`, `/ig-caption`,
`/ig-reel`), pass the same `--locale` along.

## Why this matters more on Instagram than it looks

Captions are short and scripts get said out loud. A written-sounding line in a
600-character caption is a larger share of the text than the same line in an
essay, and a voiceover that nobody could say naturally is obvious in the first
take. The tell here is not a detector flagging the post. The tell is a person
scrolling past something that reads like a brand, or a creator stumbling over
their own script.

## What gets fixed automatically

**1. Invisible characters.** Remove stray zero-width spaces and joiners, word
joiners, soft hyphens, byte-order marks, Unicode tag characters and invisible
separators; normalise non-breaking and narrow spaces. Preserve the joiners in
emoji such as 👩‍💻 and 👨‍👩‍👧: deleting those changes the visible content.
Both the cleaner and the detector distinguish these emoji joiners from stray
format characters in ordinary text.

**2. Typography.** Em dash to comma, en dash to hyphen, curly quotes to
straight, ellipsis to three dots, bullet character to hyphen. The em dash pass
is the one that matters: it collapses the dash to a comma and then cleans up
the double punctuation and orphaned periods that leaves behind.

**3. The slop lexicon.** delve, leverage, robust, seamless, crucial, testament
to, "in today's fast-paced world", plus the Instagram block: "stop scrolling",
"in today's video", "follow for more", "tag someone who needs this", "the
algorithm loves", "run don't walk". Each swapped for a plain word or deleted,
with capitalisation preserved and URLs, email addresses and @mentions left
untouched. URLs without a protocol, such as `example.com/guide`, are protected
too. Numeric decimal points such as `.5` must retain their value.

## What does NOT get fixed automatically

Structural tells get **flagged, not rewritten**, because changing the shape of
a sentence needs judgement:

- "It's not just X, it's Y" and "not only X but also Y"
- Rule-of-three triads
- Rhetorical one-word question lines: "The result?"
- The video preamble: "in this video I'm going to show you"
- Emoji bullet lists
- Three or more shouted words in a row
- Hashtag walls
- Reflex bait: "follow for more", "tag someone who", "double tap if"

That list is your job. Rewrite each flagged line by hand, keeping the meaning,
then re-run `detect.py`. This is the part that moves the score from REVIEW to
PASS, and it is the part a script cannot do.

## The five checks

`detect.py` scores assessable signals 0-100, higher is more human:

| check | what it measures | machine looks like |
| --- | --- | --- |
| BURSTINESS | sentence-length variation | every sentence the same length |
| SPECIFICITY | numbers, names, concrete markers per 100 words | abstract nouns, no figures |
| SLOP DENSITY | lexicon hits per 100 words | stock vocabulary |
| FINGERPRINT | invisible chars, em dashes, curly quotes per 1k chars | typographically perfect |
| VOICE | contractions, person, structural tells | no contractions, staged reveals |

When all five checks have enough text, the verdict weights the mean at 60%
and the **weakest single check** at 40%. PASS needs an overall of 70+ with no
check below 55.

If any check lacks enough text, its score is **N/A** and the overall verdict
is **INSUFFICIENT**. The JSON uses `null` for that check's `score` and for
`human_score`; it does not invent a 50-point score. Comparing such a draft
with another draft produces no numeric score delta. This is a completed
check with no overall judgment, not a failure or a PASS. Inspect any specific
issues still reported, then stop. Preserve the requested length, especially
the 1–3 sentences of a comment; never add sentences or repeat rewrites just
to obtain a score.

## Say this honestly

These are five local heuristics modelled on the signals public detectors key
on. They run entirely on the user's machine and nothing is uploaded. They are
**not** GPTZero, Originality, Copyleaks, Winston or Turnitin, they do not call
those APIs, and they cannot promise those verdicts. Fixing what they measure
does tend to move those numbers, because they are measuring the same underlying
things. That is the claim. Do not make a bigger one on the user's behalf, and
do not tell a user their text is undetectable.

## Order of operations

1. `humanize.py draft.txt -o clean.txt --report`
2. Read the structural flags. Rewrite those lines yourself.
3. `detect.py draft.txt clean.txt` to show the before and after.
4. If the verdict is INSUFFICIENT, finish the check after reviewing concrete
   issues. Keep short comments at 1–3 sentences and stop the rewrite loop.
   For REVIEW or FLAGGED, fix the weakest assessable check and re-run only
   after a meaningful change; do not invent facts or enlarge the requested
   format to chase PASS.
5. Show the user the cleaned text and the score, or the INSUFFICIENT explanation
   when no overall score is available. Never the score alone.
