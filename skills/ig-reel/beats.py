#!/usr/bin/env python3
"""
beats.py - turn a Reel script into a timed beat sheet before you record it.

Estimates how long each line takes to say, stacks them into timecodes, and
flags the four things that kill a Reel in the edit: a hook that runs past the
three-second mark, a beat long enough for the viewer to leave, a run of lines
with nothing concrete in them, and a total length that does not match what you
said you were making.

The timings are an estimate from word count at a words-per-minute rate. They
are close enough to plan an edit and not a substitute for recording it. Set
your own rate with --wpm once you have timed yourself reading a script out
loud: most people land between 150 and 200, and the default here is 165.

Usage
  python3 beats.py script.txt
  python3 beats.py script.txt --target 30
  python3 beats.py script.txt --wpm 185 --target 45
  pbpaste | python3 beats.py -
  python3 beats.py script.txt --json
  python3 beats.py script_ko.txt --locale ko-KR --target 30
  python3 beats.py script_ko.txt --locale ko-KR --calibrate 27.4 --save

Korean (ko-KR)
  Words per minute means little in Korean, where particles and endings are
  glued onto words. The ko-KR model counts spoken syllables instead: Hangul
  syllables, numbers expanded to how they are said (2026 is 이천이십육, five
  syllables), Latin words and acronyms as a Korean speaker says them (AI is
  에이아이), plus short pauses at commas and sentence ends. The default rate,
  330 syllables a minute, is an estimate and not a measurement of you. Record
  one script, pass its real length to --calibrate, and --save stores your rate
  in ~/.claude/instagram/config.json so every later run uses it.

  It also checks burned-in subtitles: Korean on-screen text is read at a
  different speed than it is spoken (--cps, characters per second, default
  12), so a beat whose subtitle cards would leave the screen before they can
  be read gets flagged.
"""

import argparse
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ig-i18n"))
try:                                     # shared locale code; optional for en-US
    import ig_locale
    import ig_ko
except ImportError:                      # ig-reel copied without ig-i18n
    ig_locale = ig_ko = None

WORD_RE = re.compile(r"[A-Za-z0-9$%'’-]+")
SENT_RE = re.compile(r"[^.!?]+[.!?]*")
CONCRETE_RE = re.compile(r"\$\s?\d|\b\d[\d,.]*\b|(?<!^)\b[A-Z][a-z]{2,}\b", re.MULTILINE)
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "of", "to", "in", "on", "for",
    "with", "that", "this", "it", "is", "are", "was", "were", "be", "been",
    "you", "your", "i", "my", "me", "we", "our", "they", "them", "he", "she",
    "so", "just", "not", "no", "do", "did", "does", "have", "has", "had",
    "will", "can", "at", "as", "by", "from", "out", "up", "off", "one", "all",
}

HOOK_WINDOW = 3.0        # seconds. Past this, the thumb has already decided.
MAX_BEAT = 4.0           # seconds on one idea with no change on screen.
ABSTRACT_RUN = 3         # beats in a row with nothing checkable in them.


def words(text):
    # "$18,000" is one word when it is spoken, so it is one word here too.
    return WORD_RE.findall(re.sub(r"(?<=\d),(?=\d)", "", text))


def pretty(token):
    """Put the thousands separator back for display."""
    return re.sub(r"(\d)(?=(\d{3})+$)", r"\1,", token)


def tc(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:04.1f}"


def split_beats(raw, wps):
    """One line is one beat, unless a line is too long to be one."""
    beats = []
    for line in [l.strip() for l in raw.splitlines()]:
        if not line:
            continue
        if len(words(line)) / wps <= MAX_BEAT * 1.5:
            beats.append(line)
            continue
        # Long paragraph: break it at sentence ends so the timings mean
        # something, and let the report say it was split.
        parts = [p.strip() for p in SENT_RE.findall(line) if p.strip()]
        buf = ""
        for part in parts:
            candidate = (buf + " " + part).strip()
            if buf and len(words(candidate)) / wps > MAX_BEAT:
                beats.append(buf)
                buf = part
            else:
                buf = candidate
        if buf:
            beats.append(buf)
    return beats


def analyse(raw, wpm=165, target=None):
    wps = wpm / 60.0
    beats = split_beats(raw, wps)
    if not beats:
        return None

    rows, clock = [], 0.0
    for i, text in enumerate(beats):
        n = len(words(text))
        dur = n / wps
        rows.append({
            "n": i + 1,
            "start": round(clock, 2),
            "dur": round(dur, 2),
            "words": n,
            "text": text,
            "concrete": len(CONCRETE_RE.findall(text)),
            "label": "",
            "flags": [],
        })
        clock += dur
    total = clock

    # Label the structural positions a Reel is actually built around.
    for r in rows:
        if r["n"] == 1 or r["start"] + r["dur"] <= HOOK_WINDOW:
            r["label"] = "HOOK"
    rows[-1]["label"] = "CTA" if rows[-1]["label"] != "HOOK" else "HOOK/CTA"
    half = total / 2
    for r in rows:
        if not r["label"] and r["start"] <= half < r["start"] + r["dur"]:
            r["label"] = "MID"

    notes = []
    if rows[0]["dur"] > HOOK_WINDOW:
        rows[0]["flags"].append(f"hook runs {rows[0]['dur']:.1f}s, past the {HOOK_WINDOW:.0f}s mark")
        notes.append(f"Beat 1 takes {rows[0]['dur']:.1f}s to say. Cut it to "
                     f"{int(HOOK_WINDOW * wps)} words or fewer, or the hook lands after "
                     "the decision has been made.")
    if rows[0]["concrete"] == 0:
        notes.append("Beat 1 has no number and no name in it. Hooks without something "
                     "checkable are the ones that get scrolled.")

    for r in rows:
        if r["dur"] > MAX_BEAT:
            r["flags"].append(f"{r['dur']:.1f}s on one beat")
    long_beats = [r["n"] for r in rows if r["dur"] > MAX_BEAT]
    if long_beats:
        notes.append(f"Beat(s) {', '.join(map(str, long_beats))} run past {MAX_BEAT:.0f}s. "
                     "Either split the line or change what is on screen inside it. "
                     "A static frame is where people leave.")

    run, start = 0, None
    for r in rows:
        if r["concrete"] == 0:
            run += 1
            start = start if start is not None else r["n"]
            if run == ABSTRACT_RUN:
                notes.append(f"Beats {start}-{r['n']} have nothing concrete in them. "
                             "Put a number, a name or a price in one of them.")
        else:
            run, start = 0, None

    # Does the last line hand you back to the first one?
    first = {w.lower() for w in words(rows[0]["text"]) if w.lower() not in STOPWORDS}
    last = {w.lower() for w in words(rows[-1]["text"]) if w.lower() not in STOPWORDS}
    loop = sorted(pretty(w) for w in first & last)
    if loop:
        notes.append(f"Loops: the last beat repeats \"{', '.join(loop[:3])}\" from the hook. "
                     "Second watches are free reach.")
    else:
        notes.append("No loop. The last beat shares no word with the hook, so the video "
                     "ends flat. Echoing one word from beat 1 is the cheapest replay you get.")

    if target:
        delta = total - target
        if abs(delta) <= target * 0.1:
            notes.append(f"Length is on target ({total:.1f}s against {target}s).")
        elif delta > 0:
            notes.append(f"{delta:.1f}s over target. Cut about {int(delta * wps)} words.")
        else:
            notes.append(f"{-delta:.1f}s under target. Either add {int(-delta * wps)} words "
                         "or shoot it short. Short is usually right.")

    return {
        "wpm": wpm, "target": target,
        "total_seconds": round(total, 2),
        "total_words": sum(r["words"] for r in rows),
        "beats": rows,
        "notes": notes,
    }


# --------------------------------------------------------------------------
# ko-KR

SUB_LINE_CHARS = 16      # Korean characters per subtitle line, a common upper bound
SUB_LINES = 2            # lines per subtitle card
SUB_CPS = 12.0           # characters a viewer reads per second (default, estimate)


def _ko_dur(text, spm, pause_scale):
    return ig_ko.speech_seconds(text, spm, pause_scale, final=True)


def split_beats_ko(raw, spm, pause_scale):
    beats = []
    for line in [l.strip() for l in raw.splitlines()]:
        if not line:
            continue
        if _ko_dur(line, spm, pause_scale) <= MAX_BEAT * 1.5:
            beats.append(line)
            continue
        parts = [p.strip() for p in re.split(r"(?<=[.!?…])\s+", line) if p.strip()]
        buf = ""
        for part in parts:
            candidate = (buf + " " + part).strip()
            if buf and _ko_dur(candidate, spm, pause_scale) > MAX_BEAT:
                beats.append(buf)
                buf = part
            else:
                buf = candidate
        if buf:
            beats.append(buf)
    return beats


def subtitle_check(text, dur, cps):
    """Burned-in subtitle cards for one beat, and whether they can be read in
    the time the line takes to say."""
    chars = len(re.sub(r"\s", "", text))
    per_card = SUB_LINE_CHARS * SUB_LINES
    cards = max(1, math.ceil(chars / per_card))
    read = (chars / cards) / cps
    shown = dur / cards
    return {"chars": chars, "cards": cards, "read_seconds": round(read, 2),
            "shown_seconds": round(shown, 2), "too_fast": read > shown + 0.2}


def analyse_ko(raw, spm, target=None, pause_scale=1.0, cps=SUB_CPS, rate_source="default"):
    beats = split_beats_ko(raw, spm, pause_scale)
    if not beats:
        return None
    sps = spm / 60.0
    rows, clock = [], 0.0
    for i, text in enumerate(beats):
        syl, parts = ig_ko.spoken_syllables(text)
        dur = _ko_dur(text, spm, pause_scale)
        rows.append({
            "n": i + 1,
            "start": round(clock, 2),
            "dur": round(dur, 2),
            "syllables": syl,
            "pause": round(ig_ko.pause_seconds(text, pause_scale, final=True), 2),
            "text": text,
            "concrete": len(ig_ko.concrete(text)),
            "subtitle": subtitle_check(text, dur, cps),
            "label": "",
            "flags": [],
        })
        clock += dur
    total = clock

    for r in rows:
        if r["n"] == 1 or r["start"] + r["dur"] <= HOOK_WINDOW:
            r["label"] = "HOOK"
    rows[-1]["label"] = "CTA" if rows[-1]["label"] != "HOOK" else "HOOK/CTA"
    half = total / 2
    for r in rows:
        if not r["label"] and r["start"] <= half < r["start"] + r["dur"]:
            r["label"] = "MID"

    notes = []
    if rows[0]["dur"] > HOOK_WINDOW:
        rows[0]["flags"].append(f"훅이 {rows[0]['dur']:.1f}초, {HOOK_WINDOW:.0f}초를 넘김")
        notes.append(f"첫 비트를 말하는 데 {rows[0]['dur']:.1f}초가 걸립니다. "
                     f"{int(HOOK_WINDOW * sps)}음절 이하로 줄이세요. 아니면 넘길지 말지 "
                     "정한 뒤에 훅이 나옵니다.")
    if rows[0]["concrete"] == 0:
        notes.append("첫 비트에 숫자도 이름도 없습니다. 확인할 수 있는 게 없는 훅이 "
                     "가장 많이 넘겨집니다.")

    for r in rows:
        if r["dur"] > MAX_BEAT:
            r["flags"].append(f"한 비트에 {r['dur']:.1f}초")
        if r["subtitle"]["too_fast"]:
            sub = r["subtitle"]
            r["flags"].append(f"자막 {sub['chars']}자: 읽는 데 {sub['read_seconds']:.1f}초, "
                              f"화면에는 {sub['shown_seconds']:.1f}초")
    long_beats = [r["n"] for r in rows if r["dur"] > MAX_BEAT]
    if long_beats:
        notes.append(f"{', '.join(map(str, long_beats))}번 비트가 {MAX_BEAT:.0f}초를 넘습니다. "
                     "문장을 나누거나 그 안에서 화면을 바꾸세요. 멈춘 화면에서 이탈합니다.")
    fast = [r["n"] for r in rows if r["subtitle"]["too_fast"]]
    if fast:
        notes.append(f"{', '.join(map(str, fast))}번 비트는 자막이 읽히기 전에 넘어갑니다. "
                     "자막을 말보다 짧게 줄이거나(요약 자막), 그 비트를 천천히 말하세요.")

    run, start = 0, None
    for r in rows:
        if r["concrete"] == 0:
            run += 1
            start = start if start is not None else r["n"]
            if run == ABSTRACT_RUN:
                notes.append(f"{start}~{r['n']}번 비트에 구체적인 게 없습니다. "
                             "숫자, 이름, 금액 중 하나를 넣으세요.")
        else:
            run, start = 0, None

    first = set(ig_ko.content_words(rows[0]["text"]))
    last = set(ig_ko.content_words(rows[-1]["text"]))
    loop = sorted(first & last)
    if loop:
        notes.append(f"루프: 마지막 비트가 훅에 나온 말을 다시 씁니다 ({', '.join(loop[:3])}). "
                     "다시 보기는 공짜 도달입니다.")
    else:
        notes.append("루프 없음. 마지막 비트가 훅과 겹치는 말이 없어 밋밋하게 끝납니다. "
                     "첫 비트의 단어 하나를 다시 말하는 게 가장 싼 재생입니다.")

    if target:
        delta = total - target
        if abs(delta) <= target * 0.1:
            notes.append(f"길이가 목표에 맞습니다 ({target}초 목표에 {total:.1f}초).")
        elif delta > 0:
            notes.append(f"목표보다 {delta:.1f}초 깁니다. 약 {int(delta * sps)}음절을 덜어 내세요.")
        else:
            notes.append(f"목표보다 {-delta:.1f}초 짧습니다. 약 {int(-delta * sps)}음절을 더하거나 "
                         "짧게 찍으세요. 대개 짧은 쪽이 맞습니다.")
    if rate_source == "default":
        notes.append(f"시간은 추정치입니다. 분당 {spm:.0f}음절은 기본값이지 실측이 아닙니다. "
                     "한 번 녹음해서 --calibrate 초 --save 로 내 속도를 저장하세요.")

    return {
        "locale": "ko-KR",
        "spm": spm, "rate_source": rate_source, "pause_scale": pause_scale, "cps": cps,
        "target": target,
        "total_seconds": round(total, 2),
        "total_syllables": sum(r["syllables"] for r in rows),
        "total_pause_seconds": round(sum(r["pause"] for r in rows), 2),
        "beats": rows,
        "notes": notes,
        "estimate": True,
    }


def render_ko(a, out=sys.stdout):
    src = "보정값" if a["rate_source"] == "config.json" else "추정 기본값"
    head = (f"비트 시트  |  {a['total_syllables']}음절  |  약 {a['total_seconds']:.1f}초 "
            f"(분당 {a['spm']:.0f}음절, {src})" + (f"  |  목표 {a['target']}초" if a["target"] else ""))
    print("\n" + head, file=out)
    print("=" * 72, file=out)
    for r in a["beats"]:
        label = f"{r['label']:<8}" if r["label"] else " " * 8
        print(f"  {tc(r['start'])}  {r['dur']:4.1f}s  {label}{r['text']}", file=out)
        for f in r["flags"]:
            print(f"  {'':>6}  {'':>5}  {'':<8}^ {f}", file=out)
    print("-" * 72, file=out)
    for n in a["notes"]:
        print(f"  - {n}", file=out)
    print("", file=out)


def calibrate(raw, seconds, locale, pause_scale=1.0):
    """The rate this speaker actually talks at, from one real recording."""
    if locale == "ko-KR":
        syl = sum(ig_ko.spoken_syllables(l)[0] for l in raw.splitlines() if l.strip())
        pauses = sum(ig_ko.pause_seconds(l, pause_scale, final=True)
                     for l in raw.splitlines() if l.strip())
        speaking = max(seconds - pauses, 0.1)
        return "spm", round(syl / speaking * 60, 1), {"syllables": syl, "pause_seconds": round(pauses, 2)}
    n = len(words(raw))
    return "wpm", round(n / seconds * 60, 1), {"words": n}


def render(a, out=sys.stdout):
    head = (f"BEAT SHEET  ·  {a['total_words']} words  ·  ~{a['total_seconds']:.1f}s "
            f"at {a['wpm']} wpm" + (f"  ·  target {a['target']}s" if a["target"] else ""))
    print("\n" + head, file=out)
    print("=" * max(len(head), 72), file=out)
    for r in a["beats"]:
        label = f"{r['label']:<8}" if r["label"] else " " * 8
        print(f"  {tc(r['start'])}  {r['dur']:4.1f}s  {label}{r['text']}", file=out)
        for f in r["flags"]:
            print(f"  {'':>6}  {'':>5}  {'':<8}^ {f}", file=out)
    print("-" * max(len(head), 72), file=out)
    for n in a["notes"]:
        print(f"  - {n}", file=out)
    print("", file=out)


def main():
    ap = argparse.ArgumentParser(description="Time a Reel script into a beat sheet.")
    ap.add_argument("input", nargs="?", default="-", help="script file, or - for stdin")
    ap.add_argument("--wpm", type=float, default=None, help="speaking rate (default 165)")
    ap.add_argument("--target", type=float, help="target length in seconds")
    ap.add_argument("--json", action="store_true")
    if ig_locale:
        ig_locale.add_argument(ap)
    else:
        ap.add_argument("--locale", default=None)
    ap.add_argument("--spm", type=float, default=None,
                    help="ko-KR: syllables per minute (default: your calibrated rate, else 330)")
    ap.add_argument("--pause-scale", type=float, default=1.0,
                    help="ko-KR: multiply the comma and sentence pauses (0 for a jump-cut edit)")
    ap.add_argument("--cps", type=float, default=SUB_CPS,
                    help="ko-KR: subtitle reading speed, characters per second (default 12)")
    ap.add_argument("--calibrate", type=float, metavar="SECONDS",
                    help="the real length of a recording of this script; prints your rate")
    ap.add_argument("--save", action="store_true",
                    help="with --calibrate: store the rate in ~/.claude/instagram/config.json")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    locale = resolve_locale(args.locale, raw)

    if args.calibrate:
        if not raw.strip() or args.calibrate <= 0:
            print("--calibrate needs a non-empty script and a length in seconds", file=sys.stderr)
            sys.exit(2)
        unit, rate, basis = calibrate(raw, args.calibrate, locale, args.pause_scale)
        result = {"locale": locale, "unit": unit, "rate": rate, "seconds": args.calibrate, **basis}
        if args.save and ig_locale:
            result["saved_to"] = ig_locale.save_config({"speech": {locale: {unit: rate}}})
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)

    if locale == "ko-KR":
        if args.spm:
            spm, source = args.spm, "--spm"
        else:
            _, spm, source = ig_locale.speech_rate("ko-KR")
        a = analyse_ko(raw, spm=spm, target=args.target, pause_scale=args.pause_scale,
                       cps=args.cps, rate_source=source)
    else:
        wpm = args.wpm
        if wpm is None:
            wpm = 165
            if ig_locale:
                _, saved, source = ig_locale.speech_rate("en-US")
                if source == "config.json":
                    wpm = saved
        a = analyse(raw, wpm=wpm, target=args.target)
        if a:
            a["locale"] = "en-US"
    if not a:
        print("empty script", file=sys.stderr)
        sys.exit(2)
    if args.json:
        print(json.dumps(a, indent=2, ensure_ascii=False))
    else:
        (render_ko if locale == "ko-KR" else render)(a)
    sys.exit(0)


def resolve_locale(cli, text):
    """--locale, IG_LOCALE, profile, the text's language, en-US. See ig_locale."""
    if ig_locale is None:
        if cli and cli.lower() not in ("en", "en-us", "en_us"):
            print("--locale needs the shared skills/ig-i18n folder next to ig-reel.",
                  file=sys.stderr)
            sys.exit(2)
        return "en-US"
    return ig_locale.resolve_or_exit(cli, text).locale


if __name__ == "__main__":
    main()
