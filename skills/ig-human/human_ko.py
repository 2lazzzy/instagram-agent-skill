#!/usr/bin/env python3
"""
human_ko.py - the Korean half of the humanizer, shared by humanize.py and
detect.py when they run with --locale ko-KR.

The English humanizer rewrites a lot automatically, because English slop has
plain-word replacements that keep the sentence intact. Korean does not work
that way: swapping a phrase changes the ending, the politeness level and often
the meaning. So the Korean side is split in two and the line between the two
halves is the whole design:

  FIXED       invisible characters, curly quotes and ellipses, and double
              passives (되어진다 -> 된다). Grammar-level, meaning-preserving.
  FLAGGED     everything else: marketing hype, translationese, stock openers
              and closers, connector chains, repeated sentence endings,
              repeated CTAs, the middle dot (·) and the dash (—). Listed with
              the line it is on and a suggestion. Nothing here is rewritten.

A flag is a candidate, not a verdict. Ordinary Korean is not on the lists
(통해, 또한 once, 가능하다 in its normal sense), and the checks that count
patterns only fire on repetition, so a single connector or one formal ending
never trips them.
"""

import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEX_KO = os.path.join(HERE, "locales", "ko-KR", "slop.json")
LEX_EN = os.path.join(HERE, "slop.json")
sys.path.insert(0, os.path.join(HERE, "..", "ig-i18n"))
import ig_ko      # noqa: E402
import ig_locale  # noqa: E402
from humanize import invisible_count

HANGUL = re.compile(r"[가-힣]")


def _flex(phrase):
    """A literal phrase where any run of spaces may be zero or more spaces,
    because Korean spacing in real captions is inconsistent."""
    return r"\s*".join(re.escape(p) for p in phrase.split())


def load_lexicon(path=LEX_KO):
    with open(path, encoding="utf-8") as fh:
        lex = json.load(fh)
    with open(LEX_EN, encoding="utf-8") as fh:
        lex["invisible"] = json.load(fh)["invisible"]    # language-neutral
    allow = {a.strip() for a in ig_locale.load_config().get("humanize_allow", []) if a.strip()}
    lex["allowed"] = sorted(allow)
    lex["terms"] = [t for t in lex["terms"] if t["find"] not in allow]
    for t in lex["terms"]:
        t["re"] = re.compile(t.get("regex") or _flex(t["find"]))
    for a in lex["auto"]:
        a["re"] = re.compile(_flex(a["find"]))
    for s in lex["structures"]:
        s["re"] = re.compile(s["regex"])
    return lex


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


# --------------------------------------------------------------------------
# the fixing half

def pass_typographic(text, lex):
    hits = []
    for entry in lex["typographic"]:
        n = text.count(entry["from"])
        if n:
            hits.append({"name": f"{entry['from']} {entry['name']}", "count": n, "to": entry["to"]})
            text = text.replace(entry["from"], entry["to"])
    return text, hits


def pass_auto(text, lex):
    hits = []
    for entry in sorted(lex["auto"], key=lambda e: len(e["find"]), reverse=True):
        found = entry["re"].findall(text)
        if found:
            hits.append({"find": entry["find"], "replace": entry["replace"],
                         "count": len(found), "family": entry["family"]})
            text = entry["re"].sub(entry["replace"], text)
    return text, hits


# --------------------------------------------------------------------------
# the flagging half

def find_terms(text, lex):
    out = []
    for t in lex["terms"]:
        ms = list(t["re"].finditer(text))
        if ms:
            out.append({"find": t["find"], "family": t["family"], "suggest": t["suggest"],
                        "count": len(ms), "lines": sorted({line_of(text, m.start()) for m in ms})})
    return out


def _sentences(text):
    return ig_ko.sentences(text)


def computed_structures(text, lex):
    """Patterns that only mean something when they repeat."""
    flags = []
    sents = _sentences(text)

    # Every sentence ending the same way.
    ends = [ig_ko.final_word(s) for s in sents]
    ends = [e for e in ends if e]
    if len(ends) >= 4:
        top, n = max(((e, ends.count(e)) for e in set(ends)), key=lambda x: x[1])
        if n / len(ends) >= 0.6 and n >= 4:
            flags.append({"id": "same-ending", "name": f"같은 말로 끝나는 문장 ('{top}' {n}/{len(ends)}문장)",
                          "count": n, "fix": "몇 문장은 끝을 바꾸세요. 질문, 짧은 명사문, 다른 어미를 섞으면 "
                                             "읽는 리듬이 생깁니다. 존댓말 수준은 그대로 둬도 됩니다."})

    # '~할 수 있습니다' stacked up.
    can = len(re.findall(r"수\s*(?:있습니다|있어요|있다|있죠)", text))
    if can >= 3:
        flags.append({"id": "can-do", "name": f"'~할 수 있습니다' {can}번", "count": can,
                      "fix": "가능하다고 말하지 말고 하세요: '~됩니다', '~하면 끝입니다'."})

    # Sentence-initial connectors chained.
    conn = 0
    for s in sents:
        head = s.lstrip(" -\"'(")
        if any(re.match(re.escape(c) + r"(?:[,\s]|$)", head) for c in lex["connectors"]):
            conn += 1
    if conn >= 3 or (len(sents) >= 4 and conn >= 2 and conn / len(sents) >= 0.4):
        flags.append({"id": "connectors", "name": f"문장 첫머리 연결어 {conn}번 ('또한', '이를 통해' 류)",
                      "count": conn, "fix": "연결어를 지워도 뜻이 통하면 지우세요. 순서가 이미 연결입니다."})

    # The same opener three times.
    heads = [ig_ko.eojeol(s)[0] for s in sents if ig_ko.eojeol(s)]
    for h in set(heads):
        if heads.count(h) >= 3 and len(h) >= 2:
            flags.append({"id": "same-opener", "name": f"같은 말로 시작하는 문장 {heads.count(h)}개 ('{h}')",
                          "count": heads.count(h), "fix": "시작을 바꾸거나 문장을 합치세요."})
            break

    # CTA repeated.
    ctas = sum(len(re.findall(_flex(c), text)) for c in lex["cta"])
    kinds = sum(1 for c in lex["cta"] if re.search(_flex(c), text))
    if ctas >= 4 or kinds >= 3:
        flags.append({"id": "cta-repeat", "name": f"요청 반복 ({kinds}종류 {ctas}번)", "count": ctas,
                      "fix": "요청은 하나만. 여러 개를 부탁하면 하나도 안 합니다."})

    # The same urging phrase over and over ('지금 바로 ~하세요' three times).
    push = len(re.findall(r"지금\s*바로|당장|서둘러", text))
    if push >= 2:
        flags.append({"id": "push-repeat", "name": f"재촉 문구 반복 ('지금 바로' 류 {push}번)", "count": push,
                      "fix": "재촉은 한 번도 많습니다. 하나만 남기고, 무엇부터 하면 되는지 첫 단계를 쓰세요."})

    # Exclamation marks on most lines.
    bang = sum(1 for s in sents if s.rstrip().endswith("!"))
    if bang >= 3 and bang / max(len(sents), 1) >= 0.4:
        flags.append({"id": "exclaim", "name": f"느낌표로 끝나는 문장 {bang}개", "count": bang,
                      "fix": "느낌표는 하나만 남기세요. 다 강조하면 아무것도 강조되지 않습니다."})

    # Uniform sentence length.
    lens = [ig_ko.length_units(s) for s in sents if ig_ko.length_units(s) > 4]
    if len(lens) >= 4:
        mean = sum(lens) / len(lens)
        cv = statistics.pstdev(lens) / mean if mean else 0
        if cv < 0.25:                    # lower than English's 0.35, see check_burstiness
            flags.append({"id": "uniform", "name": f"문장 길이가 고름 (변동 {cv:.2f})", "count": len(lens),
                          "fix": "한 문장은 반으로 자르고, 다른 하나는 길게 두세요. 기계는 고르게 씁니다."})
    return flags


def scan_structures(text, lex):
    flags = []
    for s in lex["structures"]:
        ms = list(s["re"].finditer(text))
        if ms:
            flags.append({"id": s["id"], "name": s["name"], "count": len(ms), "fix": s["fix"],
                          "lines": sorted({line_of(text, m.start()) for m in ms})})
    return flags + computed_structures(text, lex)


def humanize(text, lex, pass_invisible, protect_urls, restore_urls):
    """Fix what is safe, flag the rest. The three helpers come from
    humanize.py so URL protection and the invisible pass are shared code."""
    text, urls = protect_urls(text)
    text, inv = pass_invisible(text, lex)
    text, typo = pass_typographic(text, lex)
    text, auto = pass_auto(text, lex)
    text = restore_urls(text, urls)
    return text.strip() + "\n", {
        "invisible": inv,
        "typographic": typo,
        "lexical": auto,
        "suggestions": find_terms(text, lex),
        "structures": scan_structures(text, lex),
    }


# --------------------------------------------------------------------------
# the five checks, Korean measurements

def clamp(n):
    return max(0.0, min(100.0, n))


def scale(value, human, machine):
    if human == machine:
        return 50.0
    return clamp((value - machine) / (human - machine) * 100)


PERSON = re.compile(r"(?<![가-힣])(?:저는|저도|제가|저희|나는|내가|나도|우리|여러분|당신|제|저|나|내)(?=\s|$|[,.!?])")
SPOKEN = re.compile(r"근데|그냥|진짜|사실|솔직히|거든요|더라고요|더라구요|잖아요|네요|던데|는데요|ㅋㅋ|ㅎㅎ|ㅠㅠ")


def check_burstiness(text):
    lens = [ig_ko.length_units(s) for s in _sentences(text)]
    lens = [n for n in lens if n > 2]
    if len(lens) < 4:
        return None, "평가할 문장이 4개 미만이라 판단 불가"
    mean = statistics.mean(lens)
    cv = statistics.pstdev(lens) / mean if mean else 0
    # Korean sentences measured in syllables vary less than English ones measured
    # in words, so the band is lower than English's 0.22-0.70. Uncalibrated.
    return scale(cv, human=0.55, machine=0.15), f"{len(lens)}문장 길이 변동 {cv:.2f} (0.45 이상 권장)"


def check_specificity(text):
    toks = ig_ko.eojeol(text)
    if len(toks) < 15:
        return None, "어절이 15개 미만이라 판단 불가"
    hits = len(ig_ko.concrete(text))
    density = hits * 100 / len(toks)
    return scale(density, human=6.0, machine=0.5), \
        f"구체 표현 {hits}개, 어절 100개당 {density:.1f}개 (4 이상 권장)"


def check_slop(text, lex):
    toks = ig_ko.eojeol(text)
    if not toks:
        return None, "평가할 어절이 없어 판단 불가"
    terms = find_terms(text, lex)
    auto = sum(len(a["re"].findall(text)) for a in lex["auto"])
    hits = sum(t["count"] for t in terms) + auto
    density = hits * 100 / len(toks)
    detail = f"상투 표현 {hits}개, 어절 100개당 {density:.1f}개"
    names = sorted({t["find"] for t in terms})
    if names:
        detail += " (" + ", ".join(names[:4]) + (", ..." if len(names) > 4 else "") + ")"
    return scale(density, human=0.0, machine=6.0), detail


def check_fingerprint(text):
    if not text.strip():
        return None, "비어 있어 판단 불가"
    invisible = invisible_count(text)
    dash = len(re.findall(r"—|―", text))
    dot = len(re.findall(r"[가-힣A-Za-z0-9]\s?·\s?[가-힣A-Za-z0-9]", text))
    curly = sum(text.count(c) for c in "‘’“”")
    ellip = text.count("…")
    nbsp = sum(text.count(c) for c in "   ")
    total = invisible * 4 + dash * 2 + dot * 2 + curly + ellip + nbsp
    per1k = total * 1000 / max(len(text), 1)
    return scale(per1k, human=0.0, machine=12.0), \
        (f"보이지 않는 문자 {invisible}, 줄표 {dash}, 가운뎃점 나열 {dot}, "
         f"둥근 따옴표 {curly}, 말줄임표 문자 {ellip}, 고정 공백 {nbsp}")


def check_voice(text, lex):
    toks = ig_ko.eojeol(text)
    if len(toks) < 15:
        return None, "어절이 15개 미만이라 판단 불가"
    sents = _sentences(text)
    ends = [ig_ko.final_word(s) for s in sents]
    ends = [e for e in ends if e]
    variety = len(set(ends)) / len(ends) if len(ends) >= 3 else 0.7
    presence = (len(PERSON.findall(text)) + len(SPOKEN.findall(text))) * 100 / len(toks)
    tells = scan_structures(text, lex)
    n_tells = sum(1 for _ in tells)
    score = (scale(variety, human=0.8, machine=0.3) * 0.40
             + scale(presence, human=4.0, machine=0.0) * 0.25
             + clamp(100 - n_tells * 22) * 0.35)
    detail = (f"문장 끝 다양성 {variety:.2f}, 사람 냄새(1인칭, 구어) 어절 100개당 {presence:.1f}, "
              f"구조 신호 {n_tells}개")
    if tells:
        detail += " [" + ", ".join(t["id"] for t in tells[:4]) + "]"
    return clamp(score), detail


CHECKS = ["BURSTINESS", "SPECIFICITY", "SLOP DENSITY", "FINGERPRINT", "VOICE"]
LABELS = {"BURSTINESS": "문장 리듬", "SPECIFICITY": "구체성", "SLOP DENSITY": "상투 표현",
          "FINGERPRINT": "문자 흔적", "VOICE": "목소리"}
VERDICTS = {"PASS": "통과", "REVIEW": "검토", "FLAGGED": "의심", "INSUFFICIENT": "판정 보류"}


def run(text, lex):
    results = {
        "BURSTINESS": check_burstiness(text),
        "SPECIFICITY": check_specificity(text),
        "SLOP DENSITY": check_slop(text, lex),
        "FINGERPRINT": check_fingerprint(text),
        "VOICE": check_voice(text, lex),
    }
    scores = [results[c][0] for c in CHECKS]
    if any(s is None for s in scores):
        return results, None, "INSUFFICIENT"
    overall = statistics.mean(scores) * 0.6 + min(scores) * 0.4
    verdict = "PASS" if overall >= 70 and min(scores) >= 55 else (
        "REVIEW" if overall >= 50 else "FLAGGED")
    return results, overall, verdict
