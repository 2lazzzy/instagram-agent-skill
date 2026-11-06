#!/usr/bin/env python3
"""
humanize.py - strip the machine fingerprint out of a draft.

Three passes, in this order:

  1. INVISIBLE   delete or normalise stray characters: zero-width joiners,
                 word joiners, soft hyphens,
                 BOMs, Unicode tag characters, non-breaking and narrow spaces.
                 Emoji joiners are preserved because they form visible content.
  2. TYPOGRAPHIC em dash -> comma, en dash -> hyphen, curly quotes -> straight,
                 ellipsis -> three dots, bullet -> hyphen.
  3. LEXICAL     replace the slop lexicon in slop.json with plain words,
                 preserving capitalisation, numbers, URLs and @mentions.

Structural tells (rule-of-three, "not just X, it's Y", hashtag walls) are
REPORTED, never auto-rewritten - rewriting a sentence's shape needs judgement,
so that is the model's job, not a regex's.

Usage
  python3 humanize.py draft.txt
  python3 humanize.py draft.txt --report
  pbpaste | python3 humanize.py - --report
  python3 humanize.py draft.txt --json
  python3 humanize.py draft.txt -o clean.txt
  python3 humanize.py draft_ko.txt --locale ko-KR --report

Korean (ko-KR)
  Detection and correction are split. Only meaning-preserving fixes run
  automatically (invisible characters, curly quotes, double passives such as
  되어진다 -> 된다). Hype, translationese, stock openers and closers, connector
  chains, repeated endings and CTAs, the middle dot and the dash are listed
  with their line numbers and a suggestion, and never rewritten. Lexicon:
  locales/ko-KR/slop.json. Logic: human_ko.py.
"""

import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
LEX = os.path.join(HERE, "slop.json")
sys.path.insert(0, os.path.join(HERE, "..", "ig-i18n"))
try:                                     # shared locale code; optional for en-US
    import ig_locale
except ImportError:                      # ig-human copied without ig-i18n
    ig_locale = None

URL_RE = re.compile(
    r"https?://\S+|www\.\S+|\S+@\S+\.\S+"
    r"|(?<![\w@])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,63}"
    r"(?::\d+)?(?:[/?#][^\s<>\"']*)?"
    r"|(?<![\w@])@[a-z0-9_][a-z0-9_.]*", re.IGNORECASE)
# Punctuation ends a sentence only before whitespace or the end of the text,
# optionally after closing quotes/brackets. Decimal and domain dots stay inside.
SENT_RE = re.compile(r"[^\n]+?(?:[.!?]+[\"'”’)\]]*(?=\s|$)|(?=\n|$))")

# Keep this local so the English tools still work without ig-i18n. Include
# the arrow components used in horizontal and vertical head-shaking emoji.
_PICTO = (r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF"
          r"\u2194\u2195\u231A-\u231B\u23E9-\u23FA\u3030\u303D\u3297\u3299]")
_EMOJI_PART = _PICTO + r"[\uFE0F\U0001F3FB-\U0001F3FF]*"
_EMOJI_JOINED = re.compile(_EMOJI_PART + r"(?:\u200D" + _EMOJI_PART + r")+")


def emoji_joiner_positions(text):
    """ZWJs that join emoji are visible content, not hidden text artefacts."""
    return {m.start() + i for m in _EMOJI_JOINED.finditer(text)
            for i, ch in enumerate(m.group()) if ch == "\u200d"}


def invisible_count(text):
    protected = emoji_joiner_positions(text)
    return sum(1 for i, ch in enumerate(text)
               if unicodedata.category(ch) == "Cf" and i not in protected)


def load_lexicon(path=LEX):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _cp(spec):
    """'U+200B' -> '\\u200b';  'U+E0000-U+E007F' -> (start, end)."""
    if "-" in spec:
        a, b = spec.split("-")
        return (int(a[2:], 16), int(b[2:], 16))
    return int(spec[2:], 16)


def protect_urls(text):
    """Protect links, email addresses and account mentions from rewriting."""
    found = []

    def stash(m):
        found.append(m.group(0))
        return f"\x00URL{len(found) - 1}\x00"

    return URL_RE.sub(stash, text), found


def restore_urls(text, found):
    for i, url in enumerate(found):
        text = text.replace(f"\x00URL{i}\x00", url)
    return text


def pass_invisible(text, lex):
    """Delete or space-normalise invisible characters. Returns (text, hits)."""
    hits = []
    for entry in lex["invisible"]:
        cp = _cp(entry["cp"])
        if isinstance(cp, tuple):
            pattern = "[" + re.escape(chr(cp[0])) + "-" + re.escape(chr(cp[1])) + "]"
        else:
            pattern = re.escape(chr(cp))
        protected = emoji_joiner_positions(text)
        n = sum(1 for m in re.finditer(pattern, text) if m.start() not in protected)
        if n:
            hits.append({"name": entry["cp"] + " " + entry["name"], "count": n,
                         "action": entry["action"]})
            replacement = "" if entry["action"] == "delete" else " "
            text = re.sub(pattern, lambda m: m.group() if m.start() in protected else replacement, text)
    # Preserve emoji joiners; other remaining format characters are artefacts.
    protected = emoji_joiner_positions(text)
    stray = [i for i, c in enumerate(text) if unicodedata.category(c) == "Cf" and i not in protected]
    if stray:
        hits.append({"name": "other invisible format chars", "count": len(stray),
                     "action": "delete"})
        text = "".join(c for i, c in enumerate(text)
                       if unicodedata.category(c) != "Cf" or i in protected)
    return text, hits


def pass_typographic(text, lex):
    hits = []
    for entry in lex["typographic"]:
        ch = entry["from"]
        n = text.count(ch)
        if not n:
            continue
        hits.append({"name": f"{ch} {entry['name']}", "count": n, "to": entry["to"].strip() or "(space)"})
        if ch == "—":
            # " word — word " and "word—word" both collapse to a comma + space.
            text = re.sub(r"\s*—\s*", ", ", text)
        elif ch == "–":
            text = re.sub(r"\s*–\s*(?=\d)", "-", text)      # 5–10  -> 5-10
            text = re.sub(r"\s+–\s+", ", ", text)            # used as em dash
            text = text.replace("–", "-")
        else:
            text = text.replace(ch, entry["to"])
    # A comma inserted before existing punctuation reads wrong.
    text = re.sub(r",\s*([,;:!?]|\.(?!\d))", r"\1", text)
    text = re.sub(r",\s*\n", "\n", text)
    return text, hits


def _match_case(src, repl):
    if not repl:
        return repl
    if src.isupper() and len(src) > 1:
        return repl.upper()
    if src[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def pass_lexical(text, lex):
    """Replace slop words and phrases. Longest first so phrases win."""
    hits = []
    entries = sorted(lex["phrases"] + lex["words"],
                     key=lambda e: len(e["find"]), reverse=True)
    for entry in entries:
        find = entry["find"]
        pattern = re.compile(r"\b" + re.escape(find).replace(r"\ ", r"\s+") + r"\b",
                             re.IGNORECASE)
        found = pattern.findall(text)
        if not found:
            continue
        hits.append({"find": find, "replace": entry["replace"] or "(deleted)",
                     "count": len(found), "family": entry["family"]})
        text = pattern.sub(lambda m: _match_case(m.group(0), entry["replace"]), text)
    # Clean up after deletions. Deleting a whole clause leaves orphaned
    # punctuation behind ("system. ." or a line that now opens on a comma),
    # and that reads worse than the slop did.
    text = re.sub(r"[ \t]{2,}", " ", text)
    # A leading decimal point is part of a number, not orphaned punctuation.
    text = re.sub(r"(?m)^[ \t]*(?:(?:[,;:]|\.(?!\d))+[ \t]*)+", "", text)
    text = re.sub(r"(?m)^[ \t](?=\S)", "", text)       # one space left by a deletion.
                                                      # Deeper indents are deliberate.
    text = re.sub(r"\s+([,;:!?]|\.(?!\d))", r"\1", text)
    text = re.sub(r",\s*([,;:!?]|\.(?!\d))", r"\1", text)  # an em dash became a comma,
                                                      # then the clause after it went
    text = text.replace("...", "\x00ELL\x00")          # protect real ellipses
    text = re.sub(r"\.\s*(?:\.(?!\d))+", ".", text)
    text = re.sub(r"([!?])\s*\.(?!\d)", r"\1", text)
    text = text.replace("\x00ELL\x00", "...")
    text = re.sub(r"(?m)^[ \t]+$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # An em dash that became a comma, followed by a sentence connective, leaves
    # a splice ("is important, also, it's proof"). Promote it to a full stop.
    text = re.sub(r",\s*(also|so|still|basically|in the end)\s*,\s*",
                  lambda m: ". " + m.group(1)[0].upper() + m.group(1)[1:] + ", ", text)
    return text, hits


def scan_structures(text, lex):
    flags = []
    for s in lex["structures"]:
        try:
            pattern = re.compile(s["regex"], re.MULTILINE)
        except re.error:
            continue
        found = pattern.findall(text)
        if found:
            flags.append({"name": s["name"], "count": len(found), "fix": s["fix"]})
    # Sentence-length uniformity is structural too.
    lens = [len(s.split()) for s in SENT_RE.findall(text) if len(s.split()) > 2]
    if len(lens) >= 4:
        mean = sum(lens) / len(lens)
        var = sum((n - mean) ** 2 for n in lens) / len(lens)
        cv = (var ** 0.5) / mean if mean else 0
        if cv < 0.35:
            flags.append({
                "name": f"Uniform sentence length (variation {cv:.2f})",
                "count": len(lens),
                "fix": "Break one sentence in half. Let another run long. Machines write even.",
            })
    return flags


def restore_capitals(original, text):
    """Deleting an opener leaves the next word lower case.

    Only fix it for writers who capitalise their sentences in the first place:
    a deliberately lower-case voice is a style, not an artefact, and shouting
    over it would be exactly the kind of thing this script exists to stop.
    """
    starts = re.findall(r"(?:^|[.!?]\s+|\n)\s*([A-Za-z])", original)
    if not starts or sum(1 for c in starts if c.isupper()) * 2 < len(starts):
        return text
    return re.sub(r"(?:^|(?<=[.!?] )|(?<=[.!?]\n)|(?<=\n))\s*([a-z])",
                  lambda m: m.group(0)[:-1] + m.group(1).upper(), text)


def humanize(text, lex):
    raw_for_case = text
    text, urls = protect_urls(text)
    text, inv = pass_invisible(text, lex)
    text, typo = pass_typographic(text, lex)
    text, lexi = pass_lexical(text, lex)
    text = restore_capitals(raw_for_case, text)
    text = restore_urls(text, urls)
    return text.strip() + "\n", {
        "invisible": inv,
        "typographic": typo,
        "lexical": lexi,
        "structures": scan_structures(text, lex),
    }


def render_report(report, out=sys.stderr):
    def head(title):
        print(f"\n{title}\n" + "-" * len(title), file=out)

    total = sum(h["count"] for h in report["invisible"]) \
        + sum(h["count"] for h in report["typographic"]) \
        + sum(h["count"] for h in report["lexical"])

    head("HUMANIZE REPORT")
    print(f"{total} machine artefacts removed, "
          f"{len(report['structures'])} structural tells flagged for rewrite", file=out)

    if report["invisible"]:
        head("1. INVISIBLE CHARACTERS")
        for h in report["invisible"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['action']}", file=out)
    if report["typographic"]:
        head("2. TYPOGRAPHY")
        for h in report["typographic"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['to']}", file=out)
    if report["lexical"]:
        head("3. SLOP LEXICON")
        for h in report["lexical"]:
            print(f"  {h['count']:>3}x  {h['find']}  -> {h['replace']}   [{h['family']}]", file=out)
    if report["structures"]:
        head("4. STRUCTURAL TELLS  (not auto-fixed - rewrite these yourself)")
        for h in report["structures"]:
            print(f"  {h['count']:>3}x  {h['name']}\n        {h['fix']}", file=out)
    if not any(report.values()):
        head("CLEAN")
        print("  Nothing to strip.", file=out)
    print("", file=out)


def render_report_ko(report, out=sys.stderr):
    def head(title):
        print(f"\n{title}\n" + "-" * 40, file=out)

    fixed = sum(h["count"] for h in report["invisible"]) \
        + sum(h["count"] for h in report["typographic"]) \
        + sum(h["count"] for h in report["lexical"])
    head("다듬기 보고서")
    print(f"자동 수정 {fixed}곳, 확인할 표현 {len(report['suggestions'])}종, "
          f"구조 신호 {len(report['structures'])}개", file=out)
    print("자동 수정은 뜻이 바뀌지 않는 것만 합니다. 나머지는 후보일 뿐 판정이 아닙니다.", file=out)
    if report["invisible"]:
        head("1. 보이지 않는 문자 (삭제함)")
        for h in report["invisible"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['action']}", file=out)
    if report["typographic"]:
        head("2. 문장부호 (바꿈)")
        for h in report["typographic"]:
            print(f"  {h['count']:>3}x  {h['name']}  -> {h['to']}", file=out)
    if report["lexical"]:
        head("3. 이중 피동 (바꿈)")
        for h in report["lexical"]:
            print(f"  {h['count']:>3}x  {h['find']}  -> {h['replace']}", file=out)
    if report["suggestions"]:
        head("4. 확인할 표현 (자동 수정 안 함)")
        for h in report["suggestions"]:
            lines = ", ".join(map(str, h["lines"][:5]))
            print(f"  {h['count']:>3}x  {h['find']}  [{h['family']}]  {lines}번째 줄\n"
                  f"        제안: {h['suggest']}", file=out)
    if report["structures"]:
        head("5. 구조 신호 (자동 수정 안 함, 직접 고치세요)")
        for h in report["structures"]:
            where = f"  {', '.join(map(str, h['lines'][:5]))}번째 줄" if h.get("lines") else ""
            print(f"  {h['count']:>3}x  {h['name']}{where}\n        {h['fix']}", file=out)
    if not any(report.values()):
        head("깨끗함")
        print("  고칠 것도, 확인할 것도 없습니다.", file=out)
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
    ap = argparse.ArgumentParser(description="Strip the machine fingerprint out of a draft.")
    ap.add_argument("input", nargs="?", default="-", help="file, or - for stdin")
    ap.add_argument("-o", "--out", help="write cleaned text here instead of stdout")
    ap.add_argument("--report", action="store_true", help="print what changed, to stderr")
    ap.add_argument("--json", action="store_true", help="emit {text, report} as JSON")
    ap.add_argument("--lexicon", default=None, help="path to slop.json")
    if ig_locale:
        ig_locale.add_argument(ap)
    else:
        ap.add_argument("--locale", default=None)
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    locale = resolve_locale(args.locale, raw)
    if locale == "ko-KR":
        import human_ko
        lex = human_ko.load_lexicon(args.lexicon or human_ko.LEX_KO)
        clean, report = human_ko.humanize(raw, lex, pass_invisible, protect_urls, restore_urls)
        render = render_report_ko
    else:
        lex = load_lexicon(args.lexicon or LEX)
        clean, report = humanize(raw, lex)
        render = render_report

    if args.json:
        print(json.dumps({"text": clean, "report": report, "locale": locale},
                         indent=2, ensure_ascii=False))
        return
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(clean)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(clean)
    if args.report:
        render(report)


if __name__ == "__main__":
    main()
