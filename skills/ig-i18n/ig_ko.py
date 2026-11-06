#!/usr/bin/env python3
"""
ig_ko.py - Korean text analysis shared by the ko-KR tools.

Korean does not work like English in the three places the English tools lean
on hardest, so each one gets its own model here instead of a translated regex:

  WORDS      Korean glues particles and endings onto words ("계약서에서는"),
             so a whitespace token (어절) carries more than an English word
             and "words per minute" means little. Timing counts syllables.

  NUMBERS    Numbers are said in Korean ("2026년" is 이천이십육 년, five
             syllables, not one word), with Korean units: 만, 억, 원, 분.
             Concreteness counts digits, Sino-Korean number words with a unit
             ("삼십 분"), native numbers with a counter ("세 가지"), money
             words, Latin product names (Notion, GPT) and Korean-spelled
             names from the known_names list.

  SPEECH     The spoken length of a line is estimated from syllables, with
             numbers expanded to how they are read, Latin words and acronyms
             converted to the syllables a Korean speaker uses for them
             ("AI" is 에이아이), and short pauses at commas and sentence ends.

Every number this module produces is an estimate from text. Nothing here has
been fitted to recordings of this user; beats.py --calibrate exists for that.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(HERE, "locales", "ko-KR.json")

HANGUL_RE = re.compile(r"[가-힣]")
JAMO_RE = re.compile(r"[ㄱ-ㆎ]")
SINO_DIGITS = "영일이삼사오육칠팔구"

_data = None


def data():
    global _data
    if _data is None:
        with open(DATA_PATH, encoding="utf-8") as fh:
            _data = json.load(fh)
    return _data


# --------------------------------------------------------------------------
# numbers, read aloud

def _read4(n):
    out = ""
    for value, unit in ((1000, "천"), (100, "백"), (10, "십"), (1, "")):
        d, n = divmod(n, value)
        if d == 0:
            continue
        out += (unit if d == 1 and unit else SINO_DIGITS[d] + unit)
    return out


def read_int(n):
    """1 -> 일, 10 -> 십, 2026 -> 이천이십육, 18000 -> 만팔천, 3500000 -> 삼백오십만."""
    n = int(n)
    if n == 0:
        return "영"
    groups, units = [], ["", "만", "억", "조", "경"]
    i = 0
    while n and i < len(units):
        n, g = divmod(n, 10000)
        if g:
            word = _read4(g)
            if units[i] == "만" and g == 1:
                word = ""                   # 만, not 일만
            groups.append(word + units[i])
        i += 1
    return "".join(reversed(groups))


def read_number(token):
    """How a written figure is said. '18,000' -> 만팔천, '3.5' -> 삼점오,
    '010' -> 공일공 (a leading zero is read digit by digit)."""
    t = token.replace(",", "")
    if not t:
        return ""
    if "." in t:
        whole, frac = t.split(".", 1)
        return read_number(whole or "0") + "점" + "".join(SINO_DIGITS[int(c)] for c in frac if c.isdigit())
    if len(t) > 1 and t.startswith("0"):
        return "".join("공" if c == "0" else SINO_DIGITS[int(c)] for c in t if c.isdigit())
    return read_int(t)


# --------------------------------------------------------------------------
# syllables of Latin words, as a Korean speaker says them

_DIGRAPHS = ("ch", "sh", "th", "ph", "wh", "ck", "gh")
_LATIN_SPLIT = re.compile(r"[A-Z]{2,}(?=[A-Z][a-z]|[^A-Za-z]|$)|[A-Z]?[a-z]+|[A-Z]")


def latin_syllables(word):
    """'AI' -> 4 (에이아이), 'GPT' -> 3, 'Notion' -> 2, 'Claude' -> 3,
    'ChatGPT' -> 4. A rough estimate, close enough to time a line."""
    letters = data()["speech"]["letter_syllables"]
    total = 0
    for part in _LATIN_SPLIT.findall(word):
        if part.isupper():                       # an acronym, spelled out
            total += sum(letters.get(c, 1) for c in part)
            continue
        low = part.lower()
        if len(low) == 1:
            total += letters.get(low.upper(), 1)
            continue
        body = low
        if len(body) > 2 and body.endswith("e") and not body.endswith("le") \
                and body[-2] not in "aeiouy":
            body = body[:-1]                     # silent e
        groups = len(re.findall(r"[aeiouy]+", body)) or 1
        start = re.match(r"[^aeiouy]+", low)
        if start and len(start.group(0)) >= 2 and start.group(0)[:2] not in _DIGRAPHS:
            groups += 1                           # slack -> 슬랙
        if re.search(r"(?:s|z|x|f|v|sh|ch|ge|dge|th|d|de|ce|se)$", low) and not low.endswith("ss"):
            groups += 1                           # claude -> 클로드
        total += groups
    return max(1, total)


# --------------------------------------------------------------------------
# spoken length

_NUM_TOKEN = re.compile(r"([$₩])?\s?(\d[\d,]*(?:\.\d+)?)\s?([%KkMm](?![A-Za-z]))?")
_LATIN_TOKEN = re.compile(r"[A-Za-z]+")
_NATIVE_COUNTER = re.compile(
    r"[ \t]*(?:~[ \t]*\d[\d,]*(?:\.\d+)?[ \t]*)?"
    r"(시간|가지|마리|군데|개|명|번|살|시|줄|장|달|권|곳|편|통|건|잔|판)"
    r"(?=$|[^가-힣]|[은는이가을를의에로만도와과나요]|으로|보다|처럼|한테|하고|부터|까지|마다|씩|짜리|밖에|라도|쯤|뿐)")
_NATIVE_ONES = ("", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉")
_NATIVE_TENS = ("", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔")


def _read_count(figure, following):
    """Native readings for ordinary 1–99 counts; other figures stay Sino-Korean.

    A trailing unit also applies to the first number in a range (5~7개).
    Hours above 12 use the 24-hour clock reading. This is a counter heuristic,
    not a parser that distinguishes every numbered label from a count.
    """
    if not re.fullmatch(r"[1-9]\d?", figure):
        return None
    counter = _NATIVE_COUNTER.match(following)
    n = int(figure)
    if not counter or (counter.group(1) == "시" and n > 12):
        return None
    if n == 20:
        return "스무"
    tens, ones = divmod(n, 10)
    return _NATIVE_TENS[tens] + _NATIVE_ONES[ones]


def spoken_syllables(text):
    """(total, parts). parts counts where the syllables came from, so a test
    or a report can show its working."""
    sym = data()["speech"]["symbols"]
    parts = {"hangul": 0, "number": 0, "latin": 0, "symbol": 0}
    work = text

    def num(m):
        cur, figure, suffix = m.group(1), m.group(2), m.group(3)
        value = figure
        if suffix and suffix in "Kk":
            value = str(int(float(figure.replace(",", "")) * 1000))
        elif suffix and suffix in "Mm":
            value = str(int(float(figure.replace(",", "")) * 1000000))
        said = None
        ordinal = m.start(2) > 0 and text[m.start(2) - 1] == "제"
        if not cur and not suffix and not ordinal:
            said = _read_count(figure, text[m.end(2):])
        if said is None:
            said = read_number(value)
        n = len(said)
        if cur:
            n += sym.get(cur, 1)
        if suffix == "%":
            n += sym["%"]
        parts["number"] += n
        return " "

    work = _NUM_TOKEN.sub(num, work)

    def lat(m):
        parts["latin"] += latin_syllables(m.group(0))
        return " "

    work = _LATIN_TOKEN.sub(lat, work)
    parts["hangul"] = len(HANGUL_RE.findall(work))
    for ch in ("&", "+"):
        parts["symbol"] += work.count(ch) * sym[ch]
    # Keep compact ranges; allow spaces only between numeric endpoints, so
    # an expressive "안녕하세요~ 다음 문장" or a line break adds no speech.
    parts["symbol"] += len(re.findall(
        r"(?<=\S)~(?=\S)|(?<=\d)[ \t]*~[ \t]*(?=\d)", text)) * sym["~"]
    return sum(parts.values()), parts


def pause_seconds(text, scale=1.0, final=False):
    """Short pauses at commas, sentence ends and ellipses. `final` adds the
    stop at the end of the line even when it has no full stop, because a line
    break in a script is a sentence break when it is said."""
    p = data()["speech"]["pause"]
    ell = len(re.findall(r"\.{3}|…", text))
    stripped = re.sub(r"\.{3}|…", " ", text)
    ends = len(re.findall(r"[.!?]+(?=\s|$)", stripped.strip()))
    commas = len(re.findall(r"[,，、]", stripped))
    if final and not re.search(r"[.!?…]\s*$", text.strip()):
        ends += 1
    total = commas * p["comma"] + ends * p["sentence"] + ell * p["ellipsis"]
    return total * scale


def speech_seconds(text, spm, pause_scale=1.0, final=False):
    syl, _ = spoken_syllables(text)
    return syl / (spm / 60.0) + pause_seconds(text, pause_scale, final)


# --------------------------------------------------------------------------
# tokens, particles, sentences

_PUNCT_EDGE = re.compile(r"^[\"'“”‘’()\[\]{}<>「」『』,.!?…:;~·\-]+|[\"'“”‘’()\[\]{}<>「」『』,.!?…:;~·\-]+$")


def eojeol(text):
    """Whitespace tokens with the punctuation trimmed off their edges."""
    out = []
    for tok in text.split():
        t = _PUNCT_EDGE.sub("", tok)
        if t:
            out.append(t)
    return out


def strip_josa(token):
    """'계약서에서는' -> '계약서'. Only strips when a stem of two or more
    syllables (or a Latin or digit stem) is left, so '나는' stays '나는'."""
    for j in sorted(data()["josa"], key=len, reverse=True):
        if token.endswith(j) and len(token) > len(j):
            stem = token[:-len(j)]
            if len(HANGUL_RE.findall(stem)) >= 2 or re.search(r"[A-Za-z0-9]", stem):
                return stem
            return token            # the longest particle left too little: keep the
    return token                    # word whole ('손으로' must not become '손으')


def content_words(text):
    """Stems worth comparing between two lines: two or more Hangul syllables,
    or any Latin word or figure, minus the stopwords."""
    stop = set(data()["stopwords"])
    out = []
    for tok in eojeol(text):
        stem = strip_josa(tok)
        if stem in stop or tok in stop:
            continue
        if len(HANGUL_RE.findall(stem)) >= 2 or re.search(r"[A-Za-z]{2,}|\d", stem):
            out.append(stem.lower())
    return out


_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


def sentences(text, min_syllables=3):
    out = []
    for s in _SENT_SPLIT.split(text):
        s = s.strip()
        if s and len(HANGUL_RE.findall(s)) + len(re.findall(r"[A-Za-z]+|\d+", s)) >= min_syllables:
            out.append(s)
    return out


def length_units(sentence):
    """Sentence length for burstiness: Hangul syllables plus Latin words and
    figures, each counted once."""
    return len(HANGUL_RE.findall(sentence)) + len(re.findall(r"[A-Za-z]+|\d[\d,.]*", sentence))


def ending(sentence, size=2):
    """The last `size` Hangul syllables, which is where Korean sentences
    repeat themselves ('...습니다', '...수 있습니다')."""
    syl = HANGUL_RE.findall(sentence)
    return "".join(syl[-size:]) if syl else ""


def final_word(sentence):
    """The last eojeol of a sentence without punctuation: '끝납니다',
    '있습니다'. Comparing whole final words, not the last two syllables, is
    what keeps formal Korean (합니다체) from looking monotonous: every
    sentence ends in -니다, but natural ones end in different verbs."""
    toks = eojeol(re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", " ", sentence))
    return toks[-1] if toks else ""


# --------------------------------------------------------------------------
# concreteness

def _alt(words):
    return "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True))


_cache = {}


def _patterns():
    if _cache:
        return _cache
    d = data()
    _cache["digit"] = re.compile(
        r"[$₩]\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:%|퍼센트|프로|[Kk](?![A-Za-z])|"
        r"[xX](?![A-Za-z])|만\s?원|억\s?원|천\s?원|원|만|억|천|달러|"
        + _alt(d["sino_counters"]) + r")?")
    _cache["sino"] = re.compile(
        r"(?<![가-힣])(?:[이삼사오육칠팔구]?(?:십|백|천|만|억))+[일이삼사오육칠팔구]?\s?(?:"
        + _alt(d["sino_counters"]) + r")")
    _cache["native"] = re.compile(
        r"(?<![가-힣])(?:" + _alt(d["native_numbers"]) + r")\s?(?:" + _alt(d["native_counters"]) + r")")
    _cache["money"] = re.compile(r"(?:" + _alt(d["money_words"]) + r")")
    _cache["name_latin"] = re.compile(r"(?<![A-Za-z])[A-Za-z][A-Za-z0-9.+#]*[A-Za-z0-9+#]|(?<![A-Za-z0-9])[A-Z](?![A-Za-z])")
    _cache["name_ko"] = re.compile(r"(?:" + _alt(d["known_names"]) + r")")
    return _cache


def concrete(text):
    """Every concrete marker in the text as (kind, surface). Kinds: number,
    money, time, percent, count, name. Overlaps are counted once."""
    return [(kind, surface) for kind, surface, _ in concrete_spans(text)]


def concrete_spans(text):
    """concrete(), with the character offset where each marker starts."""
    p = _patterns()
    taken = [False] * (len(text) + 1)
    found = []

    def claim(m, kind):
        a, b = m.span()
        if b <= a or any(taken[a:b]):
            return
        for i in range(a, b):
            taken[i] = True
        found.append((kind, m.group(0).strip(), a))

    for m in p["digit"].finditer(text):
        s = m.group(0)
        if re.search(r"[$₩원]|달러|만\s?원|억", s):
            kind = "money"
        elif re.search(r"%|퍼센트|프로", s):
            kind = "percent"
        elif re.search(r"분|초|시간|일|주|개월|년|달", s):
            kind = "time"
        else:
            kind = "number"
        claim(m, kind)
    for m in p["sino"].finditer(text):
        claim(m, "money" if m.group(0).endswith("원") else "number")
    for m in p["native"].finditer(text):
        claim(m, "count")
    for m in p["name_ko"].finditer(text):
        claim(m, "name")
    for m in p["money"].finditer(text):
        claim(m, "money")
    generic = {g.lower() for g in data().get("generic_latin", [])}
    for m in p["name_latin"].finditer(text):
        w = m.group(0)
        if len(w) == 1 or w.lower() in generic:   # 'AI', 'SNS' and stray letters
            continue                              # are not names
        claim(m, "name")
    return sorted(found, key=lambda f: f[2])


def is_korean(text, threshold=0.3):
    h = len(HANGUL_RE.findall(text))
    l = len(re.findall(r"[A-Za-z]", text))
    return h + l > 0 and h / (h + l) >= threshold
