---
name: ig-viral
description: >-
  Go and find the reels that are actually working right now in the user's
  niche, rank them by how far each beat its own account, name the hook formula
  each one used, and turn that into a swipe file they can shoot from. Use when
  the user says "find viral videos", "what's working right now", "what are
  people posting in my niche", "reverse engineer this account", "build me a
  swipe file", "why is this reel doing numbers", or asks what to make next and
  has no evidence to answer with.
  Also in Korean (ko-KR): "요즘 뭐가 터지는지 찾아 줘", "스와이프 파일 만들어 줘", or /ig-viral --locale ko-KR.
---

# ig-viral

The research skill. Everything else in this pack writes; this one goes and
looks. Run it monthly, not daily. Formulas last a season.

One tool lives in this folder and it runs:

```bash
python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
```

## Language (en-US, ko-KR)

This skill writes English by default and Korean on request. Decide the locale
once, before anything else, in this order:

1. `--locale <code>` in the arguments, e.g. `/ig-viral --locale ko-KR ...`.
   Remove the flag from the request before using the rest of it. `ko`, `ko-KR`,
   `en` and `en-US` are all accepted.
2. The `IG_LOCALE` environment variable, if the session can see it.
3. `"locale"` in `~/.claude/instagram/config.json`, then a `Locale:` line in
   `~/.claude/instagram/voice.md`.
4. The language the user wrote the request in.
5. en-US.

For en-US, follow this file. Count validation and median-only ranking apply to
both English and Korean reports.
For ko-KR, read `../ig-i18n/style-ko-KR.md` and `locales/ko-KR/guide.md` (both
relative to this folder) before writing, and where they differ from the English
examples below, they win. Every line of output is Korean, including labels and
the receipt. Never paste an English example from this file into Korean output,
and never invent a number or a first-person experience to fill one in.

Run every tool in this folder with the locale you chose: `python3 swipe.py captured.tsv --locale ko-KR` (without `--locale`, each row is read in the language of its hook, so mixed Korean and English batches work). Without the flag the tools follow the same order (IG_LOCALE, profile, the text's own language, en-US), but pass it anyway.

When this skill hands text to another one (`/ig-human`, `/ig-caption`,
`/ig-reel`), pass the same `--locale` along.

## The one idea that makes this worth doing

**Raw views are not evidence.** An account with two million followers doing
400,000 views had a quiet Tuesday. An account with four thousand followers
doing 400,000 views found something, and that something is copyable.

So everything here ranks on the **outlier multiple**: views divided by that
account's own recent median. Anything above 3x is a signal. Anything below 1.5x
is that account's normal day and it teaches you nothing, no matter how big the
number looks.

Collect accounts **within about 10x of the user's own size**. A formula that
works at 2M followers often works because it is at 2M followers.

## Step 1: pick the accounts

Ask the user for 6 to 12 accounts, or propose them and get approval:

- **4 direct** - same niche, same offer, slightly ahead.
- **4 adjacent** - different niche, same audience. This is where formats get
  borrowed from before anybody in the niche has them.
- **2 to 4 outsized** - much bigger accounts, for format only, never for
  cadence or tone.

Also ask them to open their own **Saved collection**. It is the fastest and
most relevant corpus that exists and it is already filtered by their taste.

## Step 2: go and look

Use whatever browsing tool this session actually has: an in-app browser, a
browser extension connected to the user's own Chrome, or a computer-use tool.
There is no API for this and there does not need to be, because the volume is
small enough to read.

**Rules that are not negotiable:**

- **Never log into Instagram on the user's behalf and never ask for a
  password.** If a page needs a login, the user is the one who is already
  logged in. Drive their browser with them present, or ask them to paste.
- **This is reading, not scraping.** Ten accounts, a dozen reels each, at human
  speed. Automated collection at volume violates Instagram's Terms of Use and
  gets accounts action-blocked. Do not build a crawler, do not use a scraping
  service, and do not loop this in the background.
- **Copy the formula, never the video.** The hook shape, the structure, the
  length, the pattern of cuts. Not their script, not their voice, not their
  edit. Attribute every row in the swipe file to the account it came from.

**What to capture per reel**, in the creator's own words:

| field | notes |
| --- | --- |
| account | handle |
| followers | from the profile |
| median | eyeball the last 12 reels and take the middle view count |
| views | this reel |
| hook | the first line, spoken or on screen, verbatim including bad grammar |
| on-screen | the first text card, if different |
| length | seconds |
| cta | what they asked for at the end |

Median is required for the main ranking. A row without a positive recent
median belongs in a separate **REFERENCE ONLY** list. Its views / followers
ratio can supply context, but is never an outlier multiple and must not enter
the top/bottom comparison or formula analysis. A zero median is also unusable
as a denominator. Keep the original row and collect a recent median before
promoting it into the ranking.

**When Instagram will not show you enough:** the same hook grammar runs on
YouTube Shorts, where view counts and transcripts are public and no login is
involved. It is a legitimate second corpus, and the spoken hook is easier to
get:

```bash
# view counts for a channel's shorts
python3 -m yt_dlp --flat-playlist --playlist-end 40 -J \
  "https://www.youtube.com/@HANDLE/shorts" > channel.json

# the spoken first line of one short, from its auto-captions
python3 -m yt_dlp --skip-download --write-auto-subs --sub-langs "en.*" \
  --sub-format json3 -o hook "https://www.youtube.com/watch?v=VIDEO_ID"
```

Take every caption word with a timestamp under 3.0 seconds. That is the hook,
as said, not as written.

## Step 3: rank it

Fill a tab-separated file with a header row and run the script:

```
account	followers	median	views	hook
@someone	48000	11000	412000	nobody tells you your first 30 reels are supposed to flop
```

```bash
python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
```

It computes the outlier multiple, names the hook formula using the same 26
formulas `/ig-reel` writes from, scores each hook with `hookscore.py`, and
prints what separates the top third from the bottom third of **ranked rows
only**. Reference rows are shown separately, in their original order. If every
row is a reference, report the collected hooks and ask for recent medians;
do not infer winning formulas or top/bottom performance.

Counts may be plain numbers, comma-grouped numbers, or screen abbreviations:
`41.2K` = 41,200, `1.2M` = 1,200,000, `1B` = 1,000,000,000;
`41.2만`, `1.5천`, and `3억` also work. K/M/B are case-insensitive. A count must
resolve to a non-negative whole number. Malformed, negative, fractional, or
non-finite values are rejected, never stripped into a different number. The
tool skips that row and reports its original line number and field on stderr.
Blank optional followers/median fields remain valid; if all rows are unusable,
the command exits with status 2.

`--out swipe.md` writes in the current directory; nested and absolute paths
also work. The Markdown file uses the same report language, ranking, and
reference separation as the terminal report. `--json` keeps `n` and `accounts`
as the total accepted sample; `ranked_n` and `ranked_accounts` describe `reels`,
which contains only ranked rows. `references` and `reference_n` hold the rest.
Reference rows have null `baseline` and `outlier`; `views_per_follower` is an
explicit views / followers ratio, or null when followers are unavailable or
zero. The summary fields (`top_formulas`, top/bottom scores and lengths, and
`unclassified`) use only `reels`. With no ranked rows, formula counts are empty,
top/bottom metrics are null, and `unclassified` is 0.

## Step 4: say what it means, carefully

Report three things and no more:

1. **Which formulas over-index** in the top third, with counts. Two formulas
   appearing four times each across six accounts is a finding. One appearing
   twice is not.
2. **What the top third have in common structurally** that the bottom third do
   not: hook length, whether the payoff is visual, whether the first frame
   moves, where the ask is.
3. **The unclassified rows.** Every hook the classifier could not name is
   either noise or a formula that is not in `hooks.json` yet. Read them by
   hand. This is the most valuable column in the output and it is the reason
   the script prints the count.

Then state the sample size and the confidence in plain words. Forty reels
across six accounts supports a claim. Twelve does not, and saying so is the
difference between research and horoscopes.
State the ranked sample size separately from reference rows, so missing
baselines cannot inflate the evidence behind a claim.

## Step 5: turn it into something to shoot

For the top three formulas, write **the user's version**: their own story,
their own number, in the shape that is working. Hand each one to `/ig-reel`
with the formula id already chosen.

Never hand back "make a reel like this one". Hand back a hook line they could
say tomorrow.

## Output

```
SWIPE  ·  38 reels  ·  7 accounts  ·  baseline: account median

OUTLIERS (above 3x)
  38.4x  hook 86  #3  Nobody Tells You   @acct_a    412,000  (median 10,700)
  11.2x  hook 79  #9  The Steal          @acct_c    180,000  (median 16,100)
  ...

WHAT IS OVER-INDEXING
  #3 Nobody Tells You   x5 in the top third, 0 in the bottom
  #2 Negative Command   x4
  median hook length    8 words up top, 19 at the bottom

UNCLASSIFIED (6)
  Two of these are the same shape and it is not in hooks.json: a hook that
  opens on someone else's comment read out loud. Worth adding.

YOUR VERSION
  #3  "Nobody tells you the first 20 proposals are supposed to lose."
  ...
```

Write the swipe file to `~/.claude/instagram/swipe.md`. `/ig-reel` and
`/ig-plan` both read it, which is the point: after this runs once, the rest of
the pack is working from the user's own evidence instead of from defaults.

Nothing is posted, followed, liked or messaged by this skill. It reads.
