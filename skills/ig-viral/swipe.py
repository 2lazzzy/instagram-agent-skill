#!/usr/bin/env python3
"""
swipe.py - rank reels you collected by how far they beat their own account,
name the hook formula each one used, and write the swipe file.

The point of this script is one correction: raw views are not evidence. A
2,000,000-follower account doing 400,000 views had a quiet day. A 4,000-
follower account doing 400,000 views found something. This ranks on the
multiple over the account's own baseline, which is the only version of
"went viral" that tells you anything you can copy.

Input is a tab-separated file you fill in while you browse, one reel per row,
with a header line naming the columns:

    account   followers   median   views    hook
    @someone  48000       11000    412000   nobody tells you your first 30 flop

`median` is that account's typical recent views and is the better baseline.
If you only have `followers`, leave median out and the script says so.
`hook` is the first line of the reel, spoken or on screen, in their words.

Usage
  python3 swipe.py captured.tsv
  python3 swipe.py captured.tsv --out ~/.claude/instagram/swipe.md
  python3 swipe.py captured.tsv --json
  python3 swipe.py captured_ko.tsv --locale ko-KR

Korean (ko-KR) and mixed batches
  Korean hooks are named with the Korean formulas in
  ig-reel/locales/ko-KR/hooks.json (same ids as English) and scored with the
  Korean hook panel. Korean view counts are understood as written on the
  screen: 41.2만, 1.5천, 3억. With --locale (or IG_LOCALE) every row is read in
  that locale; without it each row is read in the language its hook is
  written in, so one swipe file can hold Korean and English accounts.
"""

import argparse
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = os.path.join(HERE, "..", "ig-reel", "hooks.json")
WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+")

try:                                              # optional: score the hooks too
    sys.path.insert(0, os.path.join(HERE, "..", "ig-reel"))
    from hookscore import run as score_hook       # noqa: E402
except Exception:                                 # ig-viral copied on its own
    score_hook = None
sys.path.insert(0, os.path.join(HERE, "..", "ig-i18n"))
try:                                              # shared locale code; optional for en-US
    import ig_locale
    import ig_text
except ImportError:
    ig_locale = ig_text = None


def _pad(text, width):
    """Left-justify by display width, so Korean formula names line up.
    Identical to str.ljust for ASCII, which keeps English output unchanged."""
    if ig_text is None:
        return f"{text:<{width}}"
    return ig_text.pad_width(ig_text.cut_width(text, width), width)
HOOKS_KO = os.path.join(HERE, "..", "ig-reel", "locales", "ko-KR", "hooks.json")
KO_UNITS = {"천": 1000, "만": 10000, "억": 100000000}


def load_formulas(path):
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception:
        return None
    by_id = {h["id"]: h for h in d["hooks"]}
    order = d.get("classify_order") or sorted(by_id)
    return [(by_id[i]["id"], by_id[i]["name"],
             re.compile(by_id[i]["match"], re.IGNORECASE)) for i in order if i in by_id]


def classify(hook, formulas):
    if not formulas:
        return None, "unclassified"
    for fid, name, pattern in formulas:
        if pattern.search(hook):
            return fid, name
    return None, "unclassified"


def parse_count(cell):
    """'412,000' -> 412000 (as before). Korean screen counts too:
    '41.2만' -> 412000, '1.5천' -> 1500, '3억' -> 300000000."""
    cell = cell or ""
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([천만억])", cell)
    if m:
        return int(round(float(m.group(1).replace(",", "")) * KO_UNITS[m.group(2)]))
    digits = re.sub(r"[^\d]", "", cell)
    return int(digits) if digits else None


def read_rows(path):
    raw = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    lines = [l for l in raw.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not lines:
        return []
    head = [c.strip().lower() for c in lines[0].split("\t")]
    if "views" in head and "hook" in head:
        cols, body = head, lines[1:]
    else:
        cols, body = ["account", "followers", "views", "hook"], lines
    rows = []
    for line in body:
        cells = line.split("\t")
        if len(cells) < len(cols):
            cells += [""] * (len(cols) - len(cells))
        r = dict(zip(cols, [c.strip() for c in cells]))
        try:
            r["views"] = parse_count(r.get("views", "")) or 0
        except ValueError:
            continue
        for k in ("followers", "median"):
            r[k] = parse_count(r.get(k, "") or "")
        if r["views"] and r.get("hook"):
            rows.append(r)
    return rows


def row_locale(hook, forced):
    """The locale one row is read in: forced, else the hook's own language."""
    if forced:
        return forced
    if ig_locale is None:
        return "en-US"
    return ig_locale.detect(hook) or ig_locale.profile_locale()[0] or "en-US"


def analyse(rows, formulas, formulas_by_locale=None, forced=None):
    used_median = any(r.get("median") for r in rows)
    for r in rows:
        loc = row_locale(r["hook"], forced)
        r["locale"] = loc
        base = r.get("median") or r.get("followers") or 0
        r["baseline"] = base
        r["outlier"] = round(r["views"] / base, 2) if base else None
        use = (formulas_by_locale or {}).get(loc, formulas) if loc != "en-US" else formulas
        r["formula_id"], r["formula"] = classify(r["hook"], use)
        if loc == "ko-KR":
            r["words"] = len(r["hook"].split())                 # eojeol
        else:
            r["words"] = len(WORD_RE.findall(r["hook"]))
        if score_hook:
            _, overall, verdict, _ = score_hook(r["hook"], loc)
            r["hook_score"], r["hook_verdict"] = round(overall, 1), verdict
        else:
            r["hook_score"], r["hook_verdict"] = None, None
    ranked = sorted(rows, key=lambda r: -(r["outlier"] or 0))
    third = max(1, len(ranked) // 3)
    top, bottom = ranked[:third], ranked[-third:]

    def med(items, key):
        vals = [i[key] for i in items if i.get(key) is not None]
        return round(statistics.median(vals), 1) if vals else None

    counts = {}
    for r in top:
        counts[r["formula"]] = counts.get(r["formula"], 0) + 1
    locales = sorted({r["locale"] for r in ranked})
    return {
        "locale": locales[0] if len(locales) == 1 else "mixed",
        "baseline": "account median" if used_median else "follower count",
        "n": len(ranked),
        "accounts": len({r.get("account", "") for r in ranked}),
        "reels": ranked,
        "top_formulas": sorted(counts.items(), key=lambda kv: -kv[1]),
        "top_hook_score": med(top, "hook_score"),
        "bottom_hook_score": med(bottom, "hook_score"),
        "top_words": med(top, "words"),
        "bottom_words": med(bottom, "words"),
        "unclassified": sum(1 for r in ranked if r["formula"] == "unclassified"),
    }


def render(a, out=sys.stdout):
    head = (f"SWIPE FILE  ·  {a['n']} reels  ·  {a['accounts']} accounts  ·  "
            f"baseline: {a['baseline']}")
    print("\n" + head, file=out)
    print("=" * max(len(head), 78), file=out)
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "   ?"
        score = f"{r['hook_score']:.0f}" if r["hook_score"] is not None else " -"
        fid = f"#{r['formula_id']:<2}" if r["formula_id"] else "-  "
        print(f"  {mult:>7}  hook {score:>3}  {fid} {_pad(r['formula'][:22], 22)} "
              f"{r.get('account', '')[:16]:<16} {r['views']:>9,}", file=out)
        print(f"           \"{r['hook'][:96]}\"", file=out)
    print("-" * max(len(head), 78), file=out)
    print("WHAT IS WORKING IN THIS BATCH", file=out)
    if a["top_formulas"]:
        print("  top third by outlier:  "
              + ", ".join(f"{n} x{c}" for n, c in a["top_formulas"][:4]), file=out)
    if a["top_hook_score"] is not None:
        print(f"  median hook score:     top {a['top_hook_score']:.0f}  "
              f"vs bottom {a['bottom_hook_score']:.0f}", file=out)
    print(f"  median hook length:    top {a['top_words']} words  "
          f"vs bottom {a['bottom_words']} words", file=out)
    print(f"  unclassified:          {a['unclassified']} of {a['n']}. Read those by hand, "
          "they are where a formula you do not have yet is hiding.", file=out)
    print("\n  A hand-collected batch is evidence, not proof. Twelve reels shows you "
          "nothing;\n  forty across six accounts shows you something. Collect more before "
          "you believe it.\n", file=out)


def render_ko(a, out=sys.stdout):
    head = (f"스와이프 파일  |  릴스 {a['n']}개  |  계정 {a['accounts']}개  |  "
            f"기준: {'계정 중앙값' if a['baseline'] == 'account median' else '팔로워 수'}")
    print("\n" + head, file=out)
    print("=" * 78, file=out)
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "   ?"
        score = f"{r['hook_score']:.0f}" if r["hook_score"] is not None else " -"
        fid = f"#{r['formula_id']:<2}" if r["formula_id"] else "-  "
        name = r["formula"] if r["formula"] != "unclassified" else "미분류"
        print(f"  {mult:>7}  훅 {score:>3}  {fid} {_pad(name, 22)} "
              f"{r.get('account', '')[:16]:<16} {r['views']:>11,}", file=out)
        print(f"           \"{r['hook'][:60]}\"", file=out)
    print("-" * 78, file=out)
    print("이번 묶음에서 통하는 것", file=out)
    if a["top_formulas"]:
        print("  배수 상위 1/3:      "
              + ", ".join(f"{('미분류' if n == 'unclassified' else n)} x{c}"
                          for n, c in a["top_formulas"][:4]), file=out)
    if a["top_hook_score"] is not None:
        print(f"  훅 점수 중앙값:     상위 {a['top_hook_score']:.0f}  "
              f"vs 하위 {a['bottom_hook_score']:.0f}", file=out)
    print(f"  훅 길이 중앙값:     상위 {a['top_words']}어절  vs 하위 {a['bottom_words']}어절", file=out)
    print(f"  미분류:             {a['n']}개 중 {a['unclassified']}개. 직접 읽어 보세요. "
          "아직 목록에 없는 공식이 거기 숨어 있습니다.", file=out)
    print("\n  손으로 모은 묶음은 증거이지 증명이 아닙니다. 12개로는 아무것도 말할 수 없고,"
          "\n  계정 6개에 걸친 40개쯤은 돼야 뭔가 보입니다. 믿기 전에 더 모으세요."
          "\n  훅 점수는 텍스트 휴리스틱이지 조회수 예측이 아닙니다.\n", file=out)


def to_markdown(a):
    lines = ["# Swipe file", "",
             f"{a['n']} reels across {a['accounts']} accounts. "
             f"Ranked by multiple over {a['baseline']}.", ""]
    for r in a["reels"]:
        mult = f"{r['outlier']:.1f}x" if r["outlier"] else "?"
        lines += [f"## {mult}  {r['formula']}  ({r.get('account', '')})",
                  f"- views: {r['views']:,}  baseline: {r['baseline']:,}",
                  f"- hook score: {r['hook_score']}  words: {r['words']}",
                  f"- hook: \"{r['hook']}\"", ""]
    return "\n".join(lines) + "\n"


def report_locale(a, forced):
    """The language the report is printed in: the batch's own locale, or for a
    mixed batch the forced locale, then the profile, then English."""
    if a["locale"] != "mixed":
        return a["locale"]
    if forced:
        return forced
    return (ig_locale.profile_locale()[0] if ig_locale else None) or "en-US"


def main():
    ap = argparse.ArgumentParser(description="Rank collected reels by outlier multiple.")
    ap.add_argument("input", nargs="?", default="-", help="TSV file, or - for stdin")
    ap.add_argument("--hooks", default=HOOKS, help="path to ig-reel/hooks.json")
    ap.add_argument("--out", help="also write the swipe file as markdown here")
    ap.add_argument("--json", action="store_true")
    if ig_locale:
        ig_locale.add_argument(ap)
    else:
        ap.add_argument("--locale", default=None)
    args = ap.parse_args()

    forced = None
    if args.locale or os.environ.get("IG_LOCALE"):
        if ig_locale is None:
            print("--locale needs the shared skills/ig-i18n folder.", file=sys.stderr)
            sys.exit(2)
        forced = ig_locale.resolve_or_exit(args.locale, "").locale

    rows = read_rows(args.input)
    if not rows:
        print("no usable rows. Need a tab-separated file with at least views and hook.",
              file=sys.stderr)
        sys.exit(2)
    formulas = load_formulas(args.hooks)
    ko_formulas = load_formulas(HOOKS_KO)
    a = analyse(rows, formulas, {"ko-KR": ko_formulas}, forced)
    if not formulas:
        print("note: hooks.json not found, formulas not named. Pass --hooks.", file=sys.stderr)
    if score_hook is None:
        print("note: hookscore.py not importable, hook scores skipped.", file=sys.stderr)

    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    elif report_locale(a, forced) == "ko-KR":
        render_ko(a)
    else:
        render(a)
    if args.out:
        path = os.path.expanduser(args.out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(to_markdown(a))
        print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
