#!/usr/bin/env python3
"""
detect.py - a five-check panel that scores how machine-written a draft looks.

What this is:  five local heuristics modelled on the signals public AI
detectors actually measure - sentence-length variation, concreteness, stock
vocabulary, typographic fingerprint, and voice. Every score is computed on
your machine from the text alone. Nothing is uploaded.

What this is NOT:  GPTZero, Originality, Copyleaks, Winston or Turnitin.
It does not call their APIs and it cannot promise their verdict. It catches
the things they all key on, which is why fixing them tends to move their
numbers too - but the only honest claim is the one on this line.

Each assessable check returns a HUMAN score from 0 to 100. Higher is better.
Checks without enough text return None. If any check is unavailable, the
overall score is None and the verdict is INSUFFICIENT: the check is complete,
and short comments should keep their requested length instead of chasing PASS.

Usage
  python3 detect.py draft.txt
  pbpaste | python3 detect.py -
  python3 detect.py draft.txt --json
  python3 detect.py before.txt after.txt      # compare two drafts
  python3 detect.py draft_ko.txt --locale ko-KR

Korean (ko-KR)
  The same five checks with Korean measurements: sentence length in
  syllables, concreteness per 100 eojeol (Korean whitespace tokens) using
  Korean numbers, units and names, the Korean lexicon in
  locales/ko-KR/slop.json, the middle dot and dash in the fingerprint, and a
  VOICE check built on sentence-ending variety rather than contractions,
  because Korean has no contractions and a formal ending (합니다) is a register,
  not a tell. Thresholds mirror the English panel and are not calibrated
  against any detector.
"""

import argparse
import json
import os
import re
import statistics
import sys
from humanize import SENT_RE, invisible_count

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "slop.json")
sys.path.insert(0, os.path.join(HERE, "..", "ig-i18n"))
try:                                     # shared locale code; optional for en-US
    import ig_locale
except ImportError:                      # ig-human copied without ig-i18n
    ig_locale = None

WORD_RE = re.compile(r"[A-Za-z']+")
CONTRACTIONS = re.compile(r"\b\w+'(?:s|t|re|ve|ll|d|m)\b", re.IGNORECASE)
PRONOUNS = re.compile(r"\b(i|me|my|mine|we|us|our|you|your)\b", re.IGNORECASE)
NUMBERS = re.compile(r"\b\d[\d,.]*%?\b|\$\d")
PROPER = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)


def clamp(n):
    return max(0.0, min(100.0, n))


def scale(value, human, machine):
    """Map value onto 0-100 where `human` -> 100 and `machine` -> 0."""
    if human == machine:
        return 50.0
    return clamp((value - machine) / (human - machine) * 100)


def sentences(text):
    return [s.strip() for s in SENT_RE.findall(text) if len(s.split()) > 2]


def words(text):
    return WORD_RE.findall(text)


def check_burstiness(text):
    """Humans vary sentence length hard. Models write even."""
    lens = [len(s.split()) for s in sentences(text)]
    if len(lens) < 4:
        return None, "fewer than 4 assessable sentences; cannot judge"
    mean = statistics.mean(lens)
    cv = statistics.pstdev(lens) / mean if mean else 0
    score = scale(cv, human=0.70, machine=0.22)
    return score, f"variation {cv:.2f} across {len(lens)} sentences (want 0.55+)"


def check_specificity(text):
    """Numbers, names and concrete nouns. Slop is abstract."""
    w = words(text)
    if len(w) < 25:
        return None, "fewer than 25 words; cannot judge"
    per100 = 100 / len(w)
    hits = len(NUMBERS.findall(text)) + len(set(PROPER.findall(text)))
    density = hits * per100
    score = scale(density, human=6.0, machine=0.5)
    return score, f"{hits} concrete markers, {density:.1f} per 100 words (want 4+)"


def check_slop(text, lex):
    """Stock vocabulary density against the lexicon."""
    w = words(text)
    if not w:
        return None, "no words to assess"
    hits, found = 0, []
    for entry in lex["words"] + lex["phrases"]:
        pattern = re.compile(r"\b" + re.escape(entry["find"]).replace(r"\ ", r"\s+") + r"\b",
                             re.IGNORECASE)
        n = len(pattern.findall(text))
        if n:
            hits += n
            found.append(entry["find"])
    density = hits * 100 / len(w)
    score = scale(density, human=0.0, machine=4.0)
    detail = f"{hits} stock terms, {density:.1f} per 100 words"
    if found:
        detail += " (" + ", ".join(sorted(found)[:4]) + (", ..." if len(found) > 4 else "") + ")"
    return score, detail


def check_fingerprint(text):
    """Characters a phone keyboard does not produce."""
    if not text.strip():
        return None, "empty; cannot judge"
    invisible = invisible_count(text)
    em = text.count("—")
    curly = sum(text.count(c) for c in "‘’“”")
    ellip = text.count("…")
    nbsp = sum(text.count(c) for c in "   ")
    total = invisible * 4 + em * 2 + curly + ellip + nbsp
    per1k = total * 1000 / max(len(text), 1)
    score = scale(per1k, human=0.0, machine=12.0)
    detail = (f"{invisible} invisible, {em} em dash, {curly} curly quote, "
              f"{ellip} ellipsis, {nbsp} hard space")
    return score, detail


def check_voice(text, lex):
    """Contractions, person, and the shapes models default to."""
    w = words(text)
    if len(w) < 25:
        return None, "fewer than 25 words; cannot judge"
    per100 = 100 / len(w)
    contractions = len(CONTRACTIONS.findall(text)) * per100
    person = len(PRONOUNS.findall(text)) * per100
    tells = 0
    names = []
    for s in lex["structures"]:
        try:
            n = len(re.compile(s["regex"], re.MULTILINE).findall(text))
        except re.error:
            continue
        if n:
            tells += n
            names.append(s["id"])
    bullets = [len(b.split()) for b in re.findall(r"(?m)^\s*[-*•]\s+(.+)$", text)]
    uniform = (len(bullets) >= 3 and statistics.pstdev(bullets) < 1.6)
    score = (scale(contractions, human=3.0, machine=0.0) * 0.35
             + scale(person, human=8.0, machine=1.0) * 0.35
             + clamp(100 - tells * 22) * 0.30)
    if uniform:
        score -= 12
        names.append("uniform-bullets")
    detail = (f"{contractions:.1f} contractions, {person:.1f} personal pronouns "
              f"per 100 words, {tells} structural tell(s)")
    if names:
        detail += " [" + ", ".join(names[:4]) + "]"
    return clamp(score), detail


CHECKS = ["BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE"]


def run(text, lex):
    results = {}
    results["BURSTINESS"] = check_burstiness(text)
    results["SPECIFICITY"] = check_specificity(text)
    results["SLOP DENSITY"] = check_slop(text, lex)
    results["FINGERPRINT"] = check_fingerprint(text)
    results["VOICE"] = check_voice(text, lex)
    scores = [results[c][0] for c in CHECKS]
    if any(s is None for s in scores):
        return results, None, "INSUFFICIENT"
    # The weakest check drags the verdict: a detector only needs one signal.
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4
    verdict = "PASS" if overall >= 70 and min(scores) >= 55 else (
        "REVIEW" if overall >= 50 else "FLAGGED")
    return results, overall, verdict


def bar(score, width=24):
    if score is None:
        return " " * width
    filled = round(score / 100 * width)
    return "#" * filled + "." * (width - filled)


def render(results, overall, verdict, label=None, out=sys.stdout):
    title = "AI DETECTION PANEL" + (f"  -  {label}" if label else "")
    print("\n" + title, file=out)
    print("=" * max(len(title), 62), file=out)
    for name in CHECKS:
        score, detail = results[name]
        shown = "N/A" if score is None else f"{score:5.1f}"
        print(f"  {name:<13} {bar(score)} {shown}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    shown = "N/A" if overall is None else f"{overall:5.1f}"
    print(f"  {'HUMAN SCORE':<13} {bar(overall)} {shown}   {verdict}", file=out)
    if verdict == "INSUFFICIENT":
        print("\n  Check complete: too little text for an overall verdict. "
              "Keep the requested length; do not expand or repeatedly rewrite for a score.", file=out)
    elif verdict != "PASS":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(f"\n  Weakest signal: {weakest}. Fix that first.", file=out)
    print("", file=out)


def render_ko(results, overall, verdict, label=None, out=sys.stdout):
    import human_ko
    import ig_text
    title = "AI 문체 점검 (로컬 휴리스틱, 탐지기 판정 아님)" + (f"  -  {label}" if label else "")
    print("\n" + title, file=out)
    print("=" * 62, file=out)
    for name in CHECKS:
        score, detail = results[name]
        shown = "판단 불가" if score is None else f"{score:5.1f}"
        print(f"  {ig_text.pad_width(human_ko.LABELS[name], 13)} {bar(score)} {shown}", file=out)
        print(f"  {'':<13} {detail}", file=out)
    print("-" * 62, file=out)
    shown = "판단 불가" if overall is None else f"{overall:5.1f}"
    print(f"  {ig_text.pad_width('사람 점수', 13)} {bar(overall)} {shown}   "
          f"{human_ko.VERDICTS[verdict]} ({verdict})", file=out)
    if verdict == "INSUFFICIENT":
        print("\n  검사 완료: 분량이 부족해 전체 판정을 보류합니다. "
              "요청한 길이를 유지하고, 점수를 위해 늘리거나 반복해서 고치지 마세요.", file=out)
    elif verdict != "PASS":
        weakest = min(CHECKS, key=lambda c: results[c][0])
        print(f"\n  가장 약한 신호: {human_ko.LABELS[weakest]}. 이것부터 고치세요.", file=out)
    print("", file=out)


def resolve_locale(cli, text):
    """--locale, IG_LOCALE, profile, the text's language, en-US. See ig_locale."""
    if ig_locale is None:
        if cli and cli.lower() not in ("en", "en-us", "en_us"):
            print("--locale needs the shared skills/ig-i18n folder next to ig-human.",
                  file=sys.stderr)
            sys.exit(2)
        return "en-US"
    return ig_locale.resolve_or_exit(cli, text).locale


def main():
    ap = argparse.ArgumentParser(description="Score how machine-written a draft looks.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("compare", nargs="?", help="second file, to show before/after")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--lexicon", default=None)
    if ig_locale:
        ig_locale.add_argument(ap)
    else:
        ap.add_argument("--locale", default=None)
    args = ap.parse_args()

    read = lambda p: sys.stdin.read() if p == "-" else open(p, encoding="utf-8").read()

    targets = [(args.input, read(args.input))]
    if args.compare:
        targets.append((args.compare, read(args.compare)))

    locale = resolve_locale(args.locale, "\n".join(t for _, t in targets))
    if locale == "ko-KR":
        import human_ko
        lex = human_ko.load_lexicon(args.lexicon or human_ko.LEX_KO)
        score, show = human_ko.run, render_ko
    else:
        lex = json.load(open(args.lexicon or LEX, encoding="utf-8"))
        score, show = run, render

    payload = []
    for name, text in targets:
        results, overall, verdict = score(text, lex)
        payload.append({
            "source": name,
            "checks": {k: {"score": round(v[0], 1) if v[0] is not None else None,
                           "detail": v[1]} for k, v in results.items()},
            "human_score": round(overall, 1) if overall is not None else None,
            "verdict": verdict,
            "locale": locale,
        })

    if args.json:
        print(json.dumps(payload if args.compare else payload[0], indent=2,
                         ensure_ascii=locale == "en-US"))
        return

    for (name, text), p in zip(targets, payload):
        results, overall, verdict = score(text, lex)
        show(results, overall, verdict, label=os.path.basename(name) if args.compare else None)
    if args.compare:
        a, b = payload
        if a["human_score"] is None or b["human_score"] is None:
            note = "점수 비교 불가: 판정 보류인 초안이 있습니다" if locale == "ko-KR" else (
                "scores not comparable: at least one draft is INSUFFICIENT")
            print(f"  {a['verdict']}  ->  {b['verdict']}   ({note})\n")
        else:
            delta = b["human_score"] - a["human_score"]
            print(f"  {a['human_score']:.1f} {a['verdict']}  ->  "
                  f"{b['human_score']:.1f} {b['verdict']}   ({delta:+.1f})\n")

    sys.exit(0 if payload[-1]["verdict"] in ("PASS", "INSUFFICIENT") else 1)


if __name__ == "__main__":
    main()
