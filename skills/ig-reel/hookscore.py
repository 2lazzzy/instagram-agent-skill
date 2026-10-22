#!/usr/bin/env python3
"""
hookscore.py - score the first line of a Reel on the five things strong hooks
have in common, and rank a batch of them against each other.

What this is:  five local heuristics, computed on your machine from the text
alone. They measure properties that hooks which hold attention tend to share -
a length you can say in under three seconds, a concrete marker, something at stake,
the payload at the front rather than the back, and a viewer to aim it at.

What this is NOT:  a view predictor. It was tested against 74 real short-form
hooks, transcribed from the first three seconds of the top eight and bottom
eight performers on five channels. Separating a real hook from a deliberately
bad one it does well: AUC 0.83, and 9 of 10 written-to-be-bad hooks scored
below the real median. Separating a good creator's hits from that same
creator's misses it barely does at all: AUC 0.56, where 0.50 is a coin flip.

So use it for what it measured well. It catches greetings, preambles, hooks
with nothing concrete in them and hooks that take five seconds to say. It will
not tell you which of two decent hooks will travel, and nothing that reads text
can, because that is decided by your face, your edit, your audio and who
Instagram shows it to. Trust the retention graph over this script.

Each check returns 0 to 100. Higher is better.

Usage
  python3 hookscore.py hooks.txt              # one hook per line, ranked
  python3 hookscore.py --hook "I lost $18,000 on one missing contract."
  pbpaste | python3 hookscore.py -
  python3 hookscore.py hooks.txt --json
  python3 hookscore.py hooks_ko.txt --locale ko-KR

Locales
  en-US is the panel described above, unchanged. ko-KR runs the same five
  checks rebuilt for Korean (syllables instead of words, Korean numbers and
  units, verb-final word order, dropped subjects); its lexicon lives in
  locales/ko-KR/hookscore.json. Without --locale the tool uses IG_LOCALE, then
  the profile in ~/.claude/instagram, then the language of the text, then
  en-US. The Korean thresholds mirror the English intent and have not been
  validated against Korean performance data: a heuristic, not a forecast.
"""

import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ig-i18n"))
try:                                     # shared locale code; optional for en-US
    import ig_locale
    import ig_ko
    import ig_text
except ImportError:                      # ig-reel copied without ig-i18n
    ig_locale = ig_ko = ig_text = None

WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+")
NUMBER_RE = re.compile(
    r"\$\s?\d[\d,]*(?:\.\d+)?"                       # money, whole
    r"|\b\d[\d,]*(?:\.\d+)?\s?"                      # a figure, with or
    r"(?:%|k\b|x\b|hrs?\b|hours?\b|mins?\b|minutes?\b"  # without a unit
    r"|days?\b|weeks?\b|months?\b|years?\b)?",
    re.IGNORECASE)
PROPER_RE = re.compile(r"(?<!^)\b[A-Z][a-z]{2,}\b")
HASHTAG_RE = re.compile(r"(?:^|\s)#\w+")
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")

# Spoken hooks say their numbers out loud. "Zero dollars" and "twenty grand"
# are as concrete as "$0" and "$20,000", and counting only digits missed them.
# "one" and "first" are deliberately absent: they are filler far more often
# than they are a quantity.
SPOKEN_NUMBERS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "fifteen", "twenty", "thirty", "forty", "fifty",
    "sixty", "seventy", "eighty", "ninety", "hundred", "thousand", "million",
    "billion", "dozen", "half", "twice", "triple",
}
MONEY_WORDS = {
    "dollars", "dollar", "bucks", "grand", "percent", "cents",
    "millionaire", "billionaire", "revenue", "profit", "salary", "rent",
}

# Words that put something on the line. A hook with none of these is a
# statement; a hook with one is a reason to keep watching.
STAKES = {
    "stop", "never", "wrong", "mistake", "mistakes", "lost", "lose", "losing",
    "cost", "costs", "broke", "broken", "failed", "failure", "fail", "nobody",
    "no", "not", "don't", "dont", "doesn't", "didn't", "can't", "won't",
    "quit", "quitting", "fired", "deleted", "delete", "killed", "kills", "kill",
    "replaced", "replaces", "cut", "beat", "free", "paid", "charged", "hired",
    "saved", "first",
    "banned", "illegal", "worst", "hate", "hated", "wasted", "waste", "scam",
    "lie", "lied", "lying", "truth", "secret", "hidden", "stole", "stolen",
    "before", "until", "instead", "but", "except", "unless", "problem",
    "risk", "danger", "warning", "regret", "wish", "should", "shouldn't",
    "still", "already", "only", "without", "versus", "vs", "actually",
}

# Openers that spend the first second saying nothing.
WEAK_OPENERS = [
    "so", "ok", "okay", "hey", "hi", "hello", "guys", "yo", "alright",
    "welcome", "today", "basically", "honestly", "look", "listen", "um",
    "just", "let", "lets", "let's", "i wanted", "i want", "one of",
    "have you", "did you", "do you", "are you", "in this", "in today",
    "the thing", "a lot", "there is", "there are", "this is", "it is",
    "as a", "when it", "if you've", "you know",
]

# Imperatives that earn the front position.
IMPERATIVES = {
    "stop", "steal", "copy", "delete", "try", "watch", "read", "save",
    "use", "build", "make", "write", "send", "take", "start", "quit",
    "never", "always", "don't", "dont", "do", "put", "run", "check",
}

DEALBREAKERS = [
    (re.compile(r"(?i)^\s*(?:stop scrolling|don'?t scroll)"),
     "Opens with \"stop scrolling\". Asking for attention proves you have not earned it."),
    (re.compile(r"(?i)\b(?:in (?:this|today'?s) (?:video|reel)|i'?m going to show you|i'?ll show you how)\b"),
     "Video preamble. Delete it and open on the payoff."),
    (re.compile(r"(?i)^\s*(?:hey |hi |what'?s up |welcome )"),
     "Greeting. Nobody came to the feed to be greeted."),
    (HASHTAG_RE,
     "Hashtag in the hook. Hashtags belong at the bottom of the caption, if anywhere."),
    (EMOJI_RE,
     "Emoji in the hook. On-screen text at hook size has room for words or for an emoji, not both."),
]


def clamp(n):
    return max(0.0, min(100.0, n))


def words(text):
    # "$18,000" is one word when it is spoken, so it is one word here too.
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text))


def check_length(text):
    """A hook has to land before the thumb moves. Roughly two seconds."""
    w = words(text)
    n = len(w)
    secs = n / 2.75                      # ~165 words per minute, spoken
    chars = len(text.strip())
    if 5 <= n <= 12:
        score = 100.0
    elif n < 5:
        score = clamp(100 - (5 - n) * 20)
    else:
        score = clamp(100 - (n - 12) * 11)
    if chars > 60:                       # two lines of big on-screen text
        score -= 12
    return clamp(score), f"{n} words, {chars} chars, ~{secs:.1f}s spoken (want 5-12 words)"


def check_specificity(text):
    """One concrete thing beats three abstract ones."""
    nums = [n.strip() for n in NUMBER_RE.findall(text) if n.strip()]
    propers = set(PROPER_RE.findall(text))
    low = [w.lower().strip("'’") for w in words(text)]
    spoken = [w for w in low if w in SPOKEN_NUMBERS or w in MONEY_WORDS]
    hits = len(nums) + len(propers) + len(spoken)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    found = ", ".join(nums[:2] + sorted(propers)[:2] + spoken[:2])
    return score, (f"{hits} concrete marker(s)" + (f": {found}" if found else
                   " - no number, no name, nothing checkable"))


def check_stakes(text):
    """Tension, cost, negation. Something the viewer might lose."""
    w = [x.lower().strip("'’") for x in words(text)]
    hits = [x for x in w if x in STAKES]
    markers = sorted(set(hits))
    if re.search(r"\$\s?\d", text):
        markers.append("a price")
    n = len(markers)
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    detail = f"{n} tension marker(s)" + (f": {', '.join(markers[:4])}" if markers else
                                         " - nothing is at stake in this line")
    return clamp(score), detail


def check_frontload(text):
    """The interesting word cannot be in position nine."""
    w = words(text)
    if not w:
        return 0.0, "empty"
    low = [x.lower().strip("'’") for x in w]
    opener = " ".join(low[:2])
    penalty = 0
    hit_opener = None
    for weak in WEAK_OPENERS:
        if opener.startswith(weak) or low[0] == weak:
            penalty, hit_opener = 30, weak
            break
    payload = None
    for i, token in enumerate(low):
        if (token in STAKES or token in SPOKEN_NUMBERS or token in MONEY_WORDS
                or NUMBER_RE.match(w[i]) or (i and PROPER_RE.match(w[i]))):
            payload = i
            break
    if payload is None:
        base = 30.0
        where = "no payload word anywhere in the line"
    elif payload <= 3:
        base = 100.0
        where = f"payload at word {payload + 1}"
    elif payload <= 6:
        base = 70.0
        where = f"payload at word {payload + 1}, could move forward"
    else:
        base = 40.0
        where = f"payload at word {payload + 1}, too late"
    detail = where + (f"; weak opener \"{hit_opener}\"" if hit_opener else "")
    return clamp(base - penalty), detail


def check_address(text):
    """Aimed at one viewer, or floating in the air."""
    low = text.lower()
    w = [x.lower().strip("'’") for x in words(text)]
    if re.search(r"\b(you|your|you're|youre|yourself)\b", low):
        return 100.0, "speaks to the viewer"
    if w and w[0] in IMPERATIVES:
        return 90.0, f"imperative opener (\"{w[0]}\")"
    if re.search(r"\b(i|my|me|we|our)\b", low):
        return 70.0, "first person, no viewer named"
    return 35.0, "third person, nobody in the room"


CHECKS = ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]


def run(text, locale="en-US"):
    if locale == "ko-KR":
        return run_ko(text)
    results = {
        "LENGTH": check_length(text),
        "SPECIFICITY": check_specificity(text),
        "STAKES": check_stakes(text),
        "FRONTLOAD": check_frontload(text),
        "ADDRESS": check_address(text),
    }
    flags = [msg for pattern, msg in DEALBREAKERS if pattern.search(text)]
    scores = [results[c][0] for c in CHECKS]
    # The weakest property caps the hook, same logic as detect.py: one bad
    # property is enough for the thumb to keep moving.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else (
        "OK" if overall >= 50 else "WEAK")
    return results, overall, verdict, flags

# --------------------------------------------------------------------------
# ko-KR. Same five checks, same weighting and verdict rules as English, with
# Korean measurements underneath. See locales/ko-KR/hookscore.json.

LABELS_KO = {"LENGTH": "길이", "SPECIFICITY": "구체성", "STAKES": "긴장감",
             "FRONTLOAD": "앞배치", "ADDRESS": "대상"}
VERDICT_KO = {"STRONG": "강함", "OK": "보통", "WEAK": "약함"}
KIND_KO = {"number": "숫자", "money": "금액", "time": "시간", "percent": "비율",
           "count": "개수", "name": "이름"}
_ko_lex = None


def ko_lexicon():
    global _ko_lex
    if _ko_lex is None:
        if ig_ko is None:
            raise SystemExit("ko-KR needs the shared skills/ig-i18n folder next to ig-reel.")
        _ko_lex = ig_locale.load_json(os.path.join(HERE, "locales", "ko-KR", "hookscore.json"))
        for item in _ko_lex["stakes"]:
            item["re"] = re.compile(item["pattern"], re.IGNORECASE)
        for item in _ko_lex["dealbreakers"]:
            item["re"] = re.compile(item["pattern"], re.IGNORECASE)
        a = _ko_lex["address"]
        _ko_lex["address_re"] = {k: re.compile(v, re.IGNORECASE | re.MULTILINE) for k, v in a.items()}
    return _ko_lex


def ko_rate():
    _, spm, _ = ig_locale.speech_rate("ko-KR")
    return spm


def check_length_ko(text):
    """한 번에 말할 수 있는 길이. 단어 수가 아니라 실제로 말하는 음절 수로 잽니다."""
    cfg = ko_lexicon()["length"]
    syl, _ = ig_ko.spoken_syllables(text)
    secs = ig_ko.speech_seconds(text, ko_rate())
    width = ig_text.display_width(text.strip())
    lo, hi = cfg["ideal_min"], cfg["ideal_max"]
    if lo <= syl <= hi:
        score = 100.0
    elif syl < lo:
        score = clamp(100 - (lo - syl) * cfg["short_penalty"])
    else:
        score = clamp(100 - (syl - hi) * cfg["long_penalty"])
    if width > cfg["screen_width"]:          # 큰 화면 텍스트 두 줄을 넘김
        score -= cfg["screen_penalty"]
    return clamp(score), f"{syl}음절, 화면 폭 {width}, 말하면 약 {secs:.1f}초 (권장 {lo}~{hi}음절)"


def check_specificity_ko(text):
    """추상적인 말 세 개보다 구체적인 것 하나. 숫자, 금액, 시간, 이름."""
    found = ig_ko.concrete(text)
    hits = len(found)
    score = 15.0 if hits == 0 else clamp(45 + hits * 30)
    shown = ", ".join(f"{s}({KIND_KO[k]})" for k, s in found[:3])
    return score, (f"구체 표현 {hits}개" + (f": {shown}" if shown else
                   ": 숫자도 이름도 없어 확인할 수 있는 게 없음"))


def _stake_hits(text):
    hits = []
    for item in ko_lexicon()["stakes"]:
        if item["re"].search(text):
            hits.append(item["label"])
    if any(k == "money" for k, _ in ig_ko.concrete(text)):
        hits.append("가격")
    return sorted(set(hits))


def check_stakes_ko(text):
    """잃을 수 있는 것, 부정, 대가. 한국어는 어미가 변하므로 어간으로 찾습니다."""
    markers = _stake_hits(text)
    n = len(markers)
    score = {0: 20.0, 1: 70.0}.get(n, 100.0)
    return clamp(score), (f"긴장 표현 {n}개" + (f": {', '.join(markers[:4])}" if markers else
                                              ": 이 문장에는 걸린 게 없음"))


def check_frontload_ko(text):
    """핵심이 앞쪽 어절에 있는지. 서술어와 부정은 문법상 끝에 오므로 세지 않습니다."""
    lex = ko_lexicon()
    cfg = lex["frontload"]
    tokens = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if not tokens:
        return 0.0, "비어 있음"
    head = text.strip()
    penalty, hit_opener = 0, None
    for weak in lex["weak_openers"]:
        w = weak.strip(" ,")
        # the opener itself, optionally with a particle ("오늘은", "요즘은"), then a break
        if re.match(re.escape(w) + r"(?:은|는|도|에|에는)?(?=[\s,.!?~]|$)", head):
            penalty, hit_opener = cfg["opener_penalty"], w
            break
    starts = [a for _, _, a in ig_ko.concrete_spans(text)]
    for item in lex["stakes"]:
        if item["front"]:
            m = item["re"].search(text)
            if m:
                starts.append(m.start())
    payload = None
    if starts:
        first = min(starts)
        for i, (a, b) in enumerate(tokens):
            if a <= first < b or first < a:
                payload = i
                break
    if payload is None:
        base, where = 30.0, "앞으로 끌어올 핵심어(숫자, 이름, 손해)가 없음"
    elif payload <= cfg["best_index"]:
        base, where = 100.0, f"핵심어가 {payload + 1}번째 어절"
    elif payload <= cfg["ok_index"]:
        base, where = 70.0, f"핵심어가 {payload + 1}번째 어절, 더 앞으로 당길 수 있음"
    else:
        base, where = 40.0, f"핵심어가 {payload + 1}번째 어절, 너무 늦음"
    detail = where + (f"; 약한 시작 \"{hit_opener}\"" if hit_opener else "")
    return clamp(base - penalty), detail


def check_address_ko(text):
    """한 사람에게 하는 말인지. 한국어는 '당신'을 자주 생략하니 존댓말 명령과
    시청자에게 묻는 어미도 대상으로 칩니다."""
    a = ko_lexicon()["address_re"]
    if a["second_person"].search(text) or a["viewer_question"].search(text):
        return 100.0, "시청자에게 직접 말함"
    sents = re.split(r"(?<=[.!?])\s+|\n", text.strip())
    if any(a["imperative"].search(s.strip()) for s in sents if s.strip()):
        return 90.0, "권유나 명령 어미(~세요, ~하자)"
    if a["first_person"].search(text):
        return 70.0, "1인칭, 시청자는 등장하지 않음"
    return 35.0, "3인칭, 화면 앞에 아무도 없음"


def run_ko(text):
    results = {
        "LENGTH": check_length_ko(text),
        "SPECIFICITY": check_specificity_ko(text),
        "STAKES": check_stakes_ko(text),
        "FRONTLOAD": check_frontload_ko(text),
        "ADDRESS": check_address_ko(text),
    }
    hits = [d for d in ko_lexicon()["dealbreakers"] if d["re"].search(text)]
    flags = [d["message"] for d in hits]
    scores = [results[c][0] for c in CHECKS]
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4 - sum(d["penalty"] for d in hits)
    overall = clamp(overall)
    verdict = "STRONG" if overall >= 70 and min(scores) >= 55 and not flags else (
        "OK" if overall >= 50 else "WEAK")
    return results, overall, verdict, flags


def render_one_ko(text, results, overall, verdict, flags, out=sys.stdout):
    pad = ig_text.pad_width
    print("\n훅 점수  (텍스트 휴리스틱, 조회수나 바이럴 확률이 아님)", file=out)
    print("=" * 62, file=out)
    print(f"  \"{text.strip()}\"\n", file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {pad(LABELS_KO[name], 13)} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {pad('훅 점수', 13)} {bar(overall)} {overall:5.1f}   {VERDICT_KO[verdict]} ({verdict})",
          file=out)
    for f in flags:
        print(f"\n  치명적 문제  {f}", file=out)
    if verdict != "STRONG":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(f"\n  가장 약한 항목: {LABELS_KO[weakest]}. 이것부터 고치고 다시 돌리세요.", file=out)
    print("", file=out)


def render_table_ko(rows, out=sys.stdout):
    print("\n훅 순위  (텍스트 휴리스틱, 조회수나 바이럴 확률이 아님)\n" + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if ig_text.display_width(r["hook"]) <= 60 else \
            ig_text.cut_width(r["hook"], 57) + "..."
        print(f"{mark} {r['score']:5.1f} {ig_text.pad_width(VERDICT_KO[r['verdict']], 5)} {hook}",
              file=out)
        print(f"        가장 약한 항목: {LABELS_KO[r['weakest']]} "
              f"({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print(f"        치명적 문제: {f}", file=out)
    print("\n1위로 찍으세요. 1위가 50점 미만이면 아직 훅이 없는 겁니다.\n"
          "이 점수는 약한 훅을 걸러 내는 용도입니다. 어떤 훅이 뜰지는 얼굴, 편집, 소리,\n"
          "노출 대상이 정하고, 그건 리텐션 그래프로 확인하세요.\n", file=out)


def bar(score, width=24):
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render_one(text, results, overall, verdict, flags, out=sys.stdout):
    print("\nHOOK SCORE", file=out)
    print("=" * 62, file=out)
    print(f"  \"{text.strip()}\"\n", file=out)
    for name in CHECKS:
        score, detail = results[name]
        print(f"  {name:<13} {bar(score)} {score:5.1f}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    print(f"  {'HOOK SCORE':<13} {bar(overall)} {overall:5.1f}   {verdict}", file=out)
    for f in flags:
        print(f"\n  DEALBREAKER  {f}", file=out)
    if verdict != "STRONG":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(f"\n  Weakest property: {weakest}. Fix that one and re-run.", file=out)
    print("", file=out)


def render_table(rows, out=sys.stdout):
    print("\nHOOK RANKING\n" + "=" * 78, file=out)
    for i, r in enumerate(rows, 1):
        mark = "->" if i == 1 else "  "
        hook = r["hook"] if len(r["hook"]) <= 62 else r["hook"][:59] + "..."
        print(f"{mark} {r['score']:5.1f} {r['verdict']:<7} {hook}", file=out)
        print(f"        weakest: {r['weakest']} ({r['checks'][r['weakest']]['score']:.0f})", file=out)
        for f in r["flags"]:
            print(f"        dealbreaker: {f}", file=out)
    print("\nShoot the top one. If the top one is under 50, none of these are the hook.\n",
          file=out)


def resolve_locale(cli, text):
    """--locale, IG_LOCALE, profile, the text's language, en-US. See ig_locale."""
    if ig_locale is None:
        if cli and cli.lower() not in ("en", "en-us", "en_us"):
            print("--locale needs the shared skills/ig-i18n folder next to ig-reel.",
                  file=sys.stderr)
            sys.exit(2)
        return "en-US"
    return ig_locale.resolve_or_exit(cli, text).locale


def main():
    ap = argparse.ArgumentParser(description="Score a Reel hook on five properties.")
    ap.add_argument("input", nargs="?", default="-", help="file with one hook per line, or -")
    ap.add_argument("--hook", help="score a single hook given on the command line")
    ap.add_argument("--json", action="store_true")
    if ig_locale:
        ig_locale.add_argument(ap)
    else:
        ap.add_argument("--locale", default=None)
    args = ap.parse_args()

    if args.hook:
        lines = [args.hook]
    else:
        raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        print("nothing to score", file=sys.stderr)
        sys.exit(2)

    locale = resolve_locale(args.locale, "\n".join(lines))

    payload = []
    for line in lines:
        results, overall, verdict, flags = run(line, locale)
        payload.append({
            "hook": line,
            "checks": {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()},
            "weakest": min(CHECKS, key=lambda c: results[c][0]),
            "flags": flags,
            "score": round(overall, 1),
            "verdict": verdict,
            "locale": locale,
        })

    if args.json:
        print(json.dumps(payload if len(payload) > 1 else payload[0], indent=2, ensure_ascii=False))
        return

    if len(payload) == 1:
        results, overall, verdict, flags = run(lines[0], locale)
        (render_one_ko if locale == "ko-KR" else render_one)(lines[0], results, overall,
                                                            verdict, flags)
    else:
        (render_table_ko if locale == "ko-KR" else render_table)(
            sorted(payload, key=lambda r: -r["score"]))

    sys.exit(0 if max(p["score"] for p in payload) >= 70 else 1)


if __name__ == "__main__":
    main()
