#!/usr/bin/env python3
"""
caption.py - lint an Instagram caption and show exactly what the feed shows
before the "... more".

Instagram gives a caption about 125 characters in the feed and hides the rest
behind a tap. Almost every caption that fails, fails there: the hook is in
sentence three, or the first line is a greeting, or the whole thing opens on a
hashtag. This prints the visible window as a box so you can read it the way a
scrolling stranger does, then checks the eight things that are worth checking.

The 125-character cut is an approximation. The real number moves with the
device, the font size and where your line breaks fall, which is exactly why
you want a margin rather than a caption engineered to end at 125. Change it
with --truncate if you want to test a tighter one.

Usage
  python3 caption.py caption.txt
  python3 caption.py caption.txt --keywords "proposal software,client contract"
  pbpaste | python3 caption.py -
  python3 caption.py caption.txt --json
  python3 caption.py caption_ko.txt --locale ko-KR --keywords "업무 자동화,회의록"

Korean (ko-KR)
  Hangul hashtags (#업무자동화) are recognised, the feed cut is measured in
  display width because Hangul is about twice as wide as Latin on a phone
  (125 units, roughly 62 syllables, an estimate), the first line is checked
  for greetings and announcements, Korean asks are counted alongside English
  ones in mixed captions, emoji are counted as what a person sees (a skin-tone
  or ZWJ emoji is one), search terms match regardless of spacing, and long
  unbroken paragraphs are flagged. Rules live in locales/ko-KR/caption.json.

Platform numbers
  2,200 characters, 125 visible and 5 hashtags are Instagram's numbers, not
  the locale's. Override them with --limit, --truncate and --hashtag-limit,
  or with a "platform" block in ~/.claude/instagram/config.json, when
  Instagram moves them. Nothing here changes them on its own.
"""

import argparse
import json
import math
import os
import re
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ig-i18n"))
try:                                     # shared locale code; optional for en-US
    import ig_locale
    import ig_ko
    import ig_text
except ImportError:                      # ig-caption copied without ig-i18n
    ig_locale = ig_ko = ig_text = None

LIMIT = 2200             # Instagram's hard caption limit.
TRUNCATE = 125           # Roughly where the feed cuts to "... more".
HASHTAG_LIMIT = 5        # Instagram's cap per post or reel since 18 Dec 2025,
                         # down from 30. Announced by the @Creators account:
                         # "using fewer (up to 5) more targeted hashtags,
                         # rather than many generic ones, can improve both your
                         # content's performance and people's experience".

HASHTAG_RE = re.compile(r"(?:^|\s)(#[A-Za-z0-9_]+)")
MENTION_RE = re.compile(r"(?:^|\s)(@[A-Za-z0-9_.]+)")
LINK_RE = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|co|io|net|org|ai|app)/\S*",
                     re.IGNORECASE)
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿←-⇿️]")
CONCRETE_RE = re.compile(r"\$\s?\d|\b\d[\d,.]*\b|(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)

ASKS = [
    (re.compile(r"(?i)\bcomment (?:the word |\")?[A-Z0-9]{2,}\b"), "comment a keyword"),
    (re.compile(r"(?i)\b(?:dm|message) me\b"), "DM me"),
    (re.compile(r"(?i)\bsave (?:this|it)\b"), "save this"),
    (re.compile(r"(?i)\bshare (?:this|it)\b"), "share this"),
    (re.compile(r"(?i)\bfollow (?:me|for)\b"), "follow"),
    (re.compile(r"(?i)\blink in (?:my )?bio\b"), "link in bio"),
    (re.compile(r"(?i)\b(?:swipe|tap) (?:through|left|right|for|to)\b"), "swipe or tap"),
    (re.compile(r"(?i)\btell me\b|\bwhat would you\b|\bwhich one\b"), "answer a question"),
]

FILLER_TAGS = {"#viral", "#fyp", "#explore", "#explorepage", "#foryou", "#foryoupage",
               "#trending", "#instagood", "#love", "#follow", "#like4like", "#reels",
               "#reelsinstagram", "#viralreels", "#instadaily"}


def visible_window(text, cut):
    """What the feed shows. Instagram cuts mid-word, so this does too."""
    flat = text.strip()
    return flat if len(flat) <= cut else flat[:cut]


def render_box(window, truncated, out=sys.stdout, width=52):
    print("\n  WHAT THE FEED SHOWS", file=out)
    print("  +" + "-" * (width + 2) + "+", file=out)
    lines = []
    for raw in window.split("\n"):
        lines.extend(textwrap.wrap(raw, width) or [""])
    for line in lines[:8]:
        print(f"  | {line:<{width}} |", file=out)
    tail = "... more" if truncated else "(whole caption fits)"
    print("  +" + "-" * (width + 2 - len(tail) - 2) + f" {tail} " + "+", file=out)


def analyse(text, cut=TRUNCATE, keywords=None, limit=LIMIT, hashtag_limit=HASHTAG_LIMIT):
    text = text.rstrip()
    stripped = text.strip()
    chars = len(stripped)
    lines = [l for l in stripped.split("\n")]
    first_line = lines[0].strip() if lines else ""
    tags = HASHTAG_RE.findall(stripped)
    mentions = MENTION_RE.findall(stripped)
    links = LINK_RE.findall(stripped)
    emoji = EMOJI_RE.findall(stripped)
    window = visible_window(stripped, cut)
    truncated = chars > cut
    asks = [name for pattern, name in ASKS if pattern.search(stripped)]
    filler = [t for t in tags if t.lower() in FILLER_TAGS]
    keywords = [k.strip() for k in (keywords or []) if k.strip()]

    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    add("LENGTH", "FAIL" if chars > limit else "PASS",
        f"{chars} / {limit} characters" + (f", {chars - limit} over the limit"
                                           if chars > limit else ""))

    if not first_line:
        add("FIRST LINE", "FAIL", "the caption opens on a blank line")
    elif first_line.startswith("#") or first_line.startswith("@"):
        add("FIRST LINE", "FAIL",
            "opens on a hashtag or a mention, which is the one position worth a sentence")
    elif len(first_line) > cut:
        add("FIRST LINE", "WARN",
            f"{len(first_line)} characters, so it gets cut at {cut} mid-thought. "
            "Fine if the cut is a cliffhanger, bad if it is a subordinate clause")
    else:
        add("FIRST LINE", "PASS", f"{len(first_line)} characters, lands whole")

    add("HOOK IS CONCRETE", "PASS" if CONCRETE_RE.search(window) else "WARN",
        f"{len(CONCRETE_RE.findall(window))} number(s) or name(s) in the visible window"
        + ("" if CONCRETE_RE.search(window) else " - nothing checkable before the tap"))

    if len(tags) > hashtag_limit:
        add("HASHTAGS", "FAIL", f"{len(tags)} tags, over Instagram's cap of {hashtag_limit}. "
                                "Tags past the fifth do not count and the block reads as old")
    elif len(tags) == hashtag_limit and filler:
        add("HASHTAGS", "WARN", f"{len(tags)} tags, at the cap, and "
                                f"{len(filler)} of them generic. Spend the five on topics")
    elif filler:
        add("HASHTAGS", "WARN", f"{len(tags)} tags, {len(filler)} of them generic "
                                f"({', '.join(filler[:3])}). Those describe nothing")
    else:
        add("HASHTAGS", "PASS", f"{len(tags)} tag(s)" + (f": {' '.join(tags)}" if tags else ""))

    if not tags:
        add("TAG PLACEMENT", "PASS", "no tags to place")
    elif any(re.search(r"(?:^|\s)" + re.escape(t) + r"\b", window) for t in tags):
        add("TAG PLACEMENT", "WARN", "a hashtag is inside the visible window, "
                                     "spending feed space on a label")
    else:
        add("TAG PLACEMENT", "PASS", "tags are below the fold")

    add("LINKS", "WARN" if links else "PASS",
        f"{len(links)} link(s) in the caption, and captions are not clickable. "
        f"Move it to the bio or the DM" if links else "no dead links in the body")

    if len(asks) == 1:
        add("ONE ASK", "PASS", f"one call to action: {asks[0]}")
    elif not asks:
        add("ONE ASK", "WARN", "no call to action. Decide what this post is for")
    else:
        add("ONE ASK", "WARN", f"{len(asks)} asks ({', '.join(asks)}). "
                               "Two asks is the same as none")

    density = len(emoji) * 100 / max(chars, 1)
    add("EMOJI", "WARN" if density > 4 else "PASS",
        f"{len(emoji)} emoji, {density:.1f} per 100 characters"
        + (" - reads as decoration" if density > 4 else ""))

    if keywords:
        low = stripped.lower()
        found = [k for k in keywords if k.lower() in low]
        missing = [k for k in keywords if k.lower() not in low]
        in_window = [k for k in found if k.lower() in window.lower()]
        status = "PASS" if not missing else ("WARN" if found else "FAIL")
        add("SEARCH TERMS", status,
            f"{len(found)}/{len(keywords)} present"
            + (f", {len(in_window)} in the visible window" if found else "")
            + (f". Missing: {', '.join(missing)}" if missing else ""))

    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    verdict = "FIX" if fails else ("REVIEW" if warns else "READY")

    return {
        "characters": chars, "limit": limit, "truncate_at": cut,
        "visible": window, "truncated": truncated,
        "first_line_chars": len(first_line),
        "hashtags": tags, "mentions": mentions, "links": links,
        "emoji": len(emoji), "asks": asks,
        "checks": checks, "verdict": verdict,
    }


# --------------------------------------------------------------------------
# ko-KR

STATUS_KO = {"PASS": "통과", "WARN": "주의", "FAIL": "실패"}
VERDICT_KO = {"READY": "게시 가능", "REVIEW": "검토 필요", "FIX": "수정 필요"}
NAMES_KO = {"LENGTH": "길이", "FIRST LINE": "첫 줄", "HOOK IS CONCRETE": "첫 화면 구체성",
            "HASHTAGS": "해시태그", "TAG PLACEMENT": "태그 위치", "LINKS": "링크",
            "ONE ASK": "요청은 하나", "EMOJI": "이모지", "SEARCH TERMS": "검색어",
            "PARAGRAPHS": "문단"}
_ko_rules = None


def ko_rules():
    global _ko_rules
    if _ko_rules is None:
        if ig_ko is None:
            raise SystemExit("ko-KR needs the shared skills/ig-i18n folder next to ig-caption.")
        r = ig_locale.load_json(os.path.join(HERE, "locales", "ko-KR", "caption.json"))
        r["hashtag_re"] = re.compile(r["hashtag_pattern"])
        r["link_re"] = re.compile(r["link_pattern"], re.IGNORECASE)
        for a in r["asks"]:
            a["re"] = re.compile(a["pattern"], re.MULTILINE)
        for o in r["first_line_openers"]:
            o["re"] = re.compile(o["pattern"])
        _ko_rules = r
    return _ko_rules


def _squash(s):
    return re.sub(r"\s+", "", s).lower()


def visible_window_ko(text, cut, unit):
    flat = text.strip()
    if unit == "width":
        return ig_text.cut_width(flat, cut)
    return flat if len(flat) <= cut else flat[:cut]


def analyse_ko(text, cut=None, unit=None, keywords=None, limit=LIMIT, hashtag_limit=HASHTAG_LIMIT):
    r = ko_rules()
    cut = cut or r["truncate"]["value"]
    unit = unit or r["truncate"]["unit"]
    measure = ig_text.display_width if unit == "width" else len
    unit_ko = "폭" if unit == "width" else "자"
    text = text.rstrip()
    stripped = text.strip()
    chars = len(stripped)
    width = ig_text.display_width(stripped)
    lines = stripped.split("\n")
    first_line = lines[0].strip() if lines else ""
    tags = r["hashtag_re"].findall(stripped)
    mentions = MENTION_RE.findall(stripped)
    links = r["link_re"].findall(stripped)
    emoji = ig_text.emoji_clusters(stripped)
    window = visible_window_ko(stripped, cut, unit)
    truncated = measure(stripped) > cut
    asks, seen = [], set()
    for a in r["asks"]:
        if a["type"] not in seen and a["re"].search(stripped):
            seen.add(a["type"])
            asks.append(a["label"])
    filler_set = {t.lower() for t in r["filler_tags"]}
    filler = [t for t in tags if t.lower() in filler_set]
    keywords = [k.strip() for k in (keywords or []) if k.strip()]

    checks = []

    def add(name, status, detail):
        checks.append({"check": name, "status": status, "detail": detail})

    add("LENGTH", "FAIL" if chars > limit else "PASS",
        f"{chars} / {limit}자" + (f", {chars - limit}자 초과" if chars > limit else ""))

    opener = next((o for o in r["first_line_openers"] if o["re"].search(first_line)), None)
    if not first_line:
        add("FIRST LINE", "FAIL", "빈 줄로 시작합니다")
    elif first_line.startswith("#") or first_line.startswith("@"):
        add("FIRST LINE", "FAIL", "해시태그나 멘션으로 시작합니다. 문장 하나가 들어가야 할 유일한 자리입니다")
    elif opener:
        add("FIRST LINE", "WARN", opener["message"])
    elif measure(first_line) > cut:
        add("FIRST LINE", "WARN",
            f"{unit_ko} {measure(first_line)}, {cut}에서 문장 중간에 잘립니다. "
            "궁금하게 끊기면 괜찮고, 조사나 수식어 중간에서 끊기면 손해입니다")
    else:
        add("FIRST LINE", "PASS", f"{len(first_line)}자 ({unit_ko} {measure(first_line)}), 잘리지 않음")

    found = ig_ko.concrete(window)
    add("HOOK IS CONCRETE", "PASS" if found else "WARN",
        f"보이는 부분에 숫자, 금액, 이름 {len(found)}개"
        + (": " + ", ".join(s for _, s in found[:3]) if found else ", 더 보기 전에 확인할 게 없음"))

    if len(tags) > hashtag_limit:
        add("HASHTAGS", "FAIL", f"해시태그 {len(tags)}개, 상한 {hashtag_limit}개 초과. "
                                f"{hashtag_limit}개를 넘는 태그는 의미가 없고 오래된 계정처럼 보입니다")
    elif len(tags) == hashtag_limit and filler:
        add("HASHTAGS", "WARN", f"{len(tags)}개로 상한이고 그중 {len(filler)}개가 의미 없는 태그. "
                                "주제 태그에 쓰세요")
    elif filler:
        add("HASHTAGS", "WARN", f"{len(tags)}개 중 {len(filler)}개가 의미 없는 태그 "
                                f"({', '.join(filler[:3])}). 아무것도 설명하지 않습니다")
    else:
        add("HASHTAGS", "PASS", f"{len(tags)}개" + (f": {' '.join(tags)}" if tags else ""))

    if not tags:
        add("TAG PLACEMENT", "PASS", "배치할 태그 없음")
    elif any(t in window for t in tags):
        add("TAG PLACEMENT", "WARN", "보이는 부분에 해시태그가 있어 첫 화면을 라벨에 씁니다")
    else:
        add("TAG PLACEMENT", "PASS", "태그가 더 보기 아래에 있음")

    add("LINKS", "WARN" if links else "PASS",
        f"캡션에 링크 {len(links)}개. 캡션 링크는 눌리지 않습니다. 프로필이나 DM으로 옮기세요"
        if links else "본문에 죽은 링크 없음")

    if len(asks) == 1:
        add("ONE ASK", "PASS", f"요청 하나: {asks[0]}")
    elif not asks:
        add("ONE ASK", "WARN", "요청이 없습니다. 이 게시물이 무엇을 위한 건지 정하세요")
    else:
        add("ONE ASK", "WARN", f"요청 {len(asks)}개 ({', '.join(asks)}). 두 개면 없는 것과 같습니다")

    density = len(emoji) * 100 / max(chars, 1)
    warn_at = r["emoji_per_100_warn"]
    add("EMOJI", "WARN" if density > warn_at else "PASS",
        f"이모지 {len(emoji)}개, 100자당 {density:.1f}개" + (", 장식처럼 읽힘" if density > warn_at else ""))

    paragraphs = [p for p in re.split(r"\n\s*\n", stripped) if p.strip()]
    longest = max((ig_text.display_width(p) for p in paragraphs), default=0)
    if len(paragraphs) == 1 and width > r["wall_width"]:
        add("PARAGRAPHS", "WARN", f"빈 줄 없이 한 덩어리(폭 {width}). 2~4문장마다 빈 줄을 넣으세요")
    elif longest > r["paragraph_width"]:
        add("PARAGRAPHS", "WARN", f"가장 긴 문단의 폭이 {longest}. 휴대폰에서 다섯 줄이 넘어가니 나누세요")
    else:
        add("PARAGRAPHS", "PASS", f"문단 {len(paragraphs)}개, 가장 긴 문단 폭 {longest}")

    if keywords:
        flat = _squash(stripped)
        found_k = [k for k in keywords if _squash(k) in flat]
        missing = [k for k in keywords if _squash(k) not in flat]
        in_window = [k for k in found_k if _squash(k) in _squash(window)]
        status = "PASS" if not missing else ("WARN" if found_k else "FAIL")
        add("SEARCH TERMS", status,
            f"{len(found_k)}/{len(keywords)}개 포함"
            + (f", 보이는 부분에 {len(in_window)}개" if found_k else "")
            + (f". 빠진 검색어: {', '.join(missing)}" if missing else ""))

    fails = sum(1 for c in checks if c["status"] == "FAIL")
    warns = sum(1 for c in checks if c["status"] == "WARN")
    verdict = "FIX" if fails else ("REVIEW" if warns else "READY")

    return {
        "locale": "ko-KR",
        "characters": chars, "display_width": width, "limit": limit,
        "truncate_at": cut, "truncate_unit": unit,
        "visible": window, "truncated": truncated,
        "first_line_chars": len(first_line),
        "hashtags": tags, "mentions": mentions, "links": links,
        "emoji": len(emoji), "asks": asks,
        "checks": checks, "verdict": verdict,
    }


def render_box_ko(window, truncated, out=sys.stdout, width=52):
    print("\n  피드에 보이는 부분", file=out)
    print("  +" + "-" * (width + 2) + "+", file=out)
    lines = []
    for raw in window.split("\n"):
        lines.extend(ig_text.wrap_width(raw, width) or [""])
    for line in lines[:8]:
        print(f"  | {ig_text.pad_width(line, width)} |", file=out)
    tail = "... 더 보기" if truncated else "(캡션 전체가 보임)"
    fill = width + 2 - ig_text.display_width(tail) - 2
    print("  +" + "-" * fill + f" {tail} " + "+", file=out)


def render_ko(a, out=sys.stdout):
    head = (f"캡션 검사  |  {a['characters']} / {a['limit']}자  |  "
            f"해시태그 {len(a['hashtags'])}개  |  요청 {len(a['asks'])}개")
    print("\n" + head, file=out)
    print("=" * 62, file=out)
    render_box_ko(a["visible"], a["truncated"], out=out)
    unit = "표시 폭" if a["truncate_unit"] == "width" else "글자 수"
    print(f"  잘림 기준: {unit} {a['truncate_at']} (추정치, --truncate 로 변경)\n", file=out)
    for c in a["checks"]:
        print(f"  {ig_text.pad_width(STATUS_KO[c['status']], 5)} "
              f"{ig_text.pad_width(NAMES_KO[c['check']], 15)} {c['detail']}", file=out)
    print("-" * 62, file=out)
    print(f"  판정  {VERDICT_KO[a['verdict']]} ({a['verdict']})\n", file=out)


def render(a, out=sys.stdout):
    head = (f"CAPTION LINT  ·  {a['characters']} / {a['limit']} chars  ·  "
            f"{len(a['hashtags'])} hashtags  ·  {len(a['asks'])} ask(s)")
    print("\n" + head, file=out)
    print("=" * max(len(head), 62), file=out)
    render_box(a["visible"], a["truncated"], out=out)
    print("", file=out)
    for c in a["checks"]:
        print(f"  {c['status']:<5} {c['check']:<17} {c['detail']}", file=out)
    print("-" * max(len(head), 62), file=out)
    print(f"  VERDICT  {a['verdict']}\n", file=out)


def platform_numbers(args):
    """CLI flag, then the profile's platform block, then the built-in number."""
    cfg = (ig_locale.load_config().get("platform") or {}) if ig_locale else {}

    def pick(flag, key, default):
        if flag is not None:
            return flag
        v = cfg.get(key)
        return v if isinstance(v, int) and v > 0 else default
    return (pick(args.limit, "caption_limit", LIMIT),
            pick(args.hashtag_limit, "hashtag_limit", HASHTAG_LIMIT),
            pick(args.truncate, "truncate", None))


def main():
    ap = argparse.ArgumentParser(description="Lint an Instagram caption.")
    ap.add_argument("input", nargs="?", default="-", help="caption file, or - for stdin")
    ap.add_argument("--truncate", type=int, default=None,
                    help=f"characters shown before '... more' (default {TRUNCATE}; "
                         "ko-KR: 125 display-width units)")
    ap.add_argument("--truncate-unit", choices=["chars", "width"], default=None,
                    help="ko-KR: measure the cut in characters or display width (default width)")
    ap.add_argument("--limit", type=int, default=None, help=f"caption limit (default {LIMIT})")
    ap.add_argument("--hashtag-limit", type=int, default=None,
                    help=f"hashtags allowed per post (default {HASHTAG_LIMIT})")
    ap.add_argument("--keywords", default="", help="comma-separated terms you want to be found for")
    ap.add_argument("--json", action="store_true")
    if ig_locale:
        ig_locale.add_argument(ap)
    else:
        ap.add_argument("--locale", default=None)
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    locale = resolve_locale(args.locale, raw)
    limit, hashtag_limit, truncate = platform_numbers(args)
    if locale == "ko-KR":
        a = analyse_ko(raw, cut=truncate, unit=args.truncate_unit,
                       keywords=args.keywords.split(","), limit=limit, hashtag_limit=hashtag_limit)
    else:
        a = analyse(raw, cut=truncate or TRUNCATE, keywords=args.keywords.split(","),
                    limit=limit, hashtag_limit=hashtag_limit)
        a["locale"] = "en-US"
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        (render_ko if locale == "ko-KR" else render)(a)
    sys.exit(0 if a["verdict"] == "READY" else 1)


def resolve_locale(cli, text):
    """--locale, IG_LOCALE, profile, the text's language, en-US. See ig_locale."""
    if ig_locale is None:
        if cli and cli.lower() not in ("en", "en-us", "en_us"):
            print("--locale needs the shared skills/ig-i18n folder next to ig-caption.",
                  file=sys.stderr)
            sys.exit(2)
        return "en-US"
    return ig_locale.resolve_or_exit(cli, text).locale


if __name__ == "__main__":
    main()
