#!/usr/bin/env python3
"""
ig_locale.py - decide which locale a tool runs in, and find that locale's files.

Shared by every script in the pack. Standard library only, nothing is
uploaded, nothing is written unless a caller asks for it explicitly.

Resolution order, first one that is set wins:

  1. --locale on the command line                       (explicit)
  2. IG_LOCALE environment variable                     (explicit)
  3. "locale" in ~/.claude/instagram/config.json        (user profile)
  4. a "Locale:" line in ~/.claude/instagram/voice.md   (user profile)
  5. the language the text itself is written in         (detected)
  6. en-US                                              (default)

Steps 5 and 6 are why nothing changes for an existing English user: with no
flag, no variable and no profile entry, English text resolves to en-US exactly
as before. When a profile locale disagrees with text that is clearly in the
other language, the tool still follows the profile (it was set on purpose) but
prints one warning line to stderr so the mismatch is visible.

IG_CONFIG_DIR overrides ~/.claude/instagram, which the tests use so they never
read the real profile.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(HERE, "locales.json")

_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")
_VOICE_LOCALE = re.compile(
    r"(?im)^\s*[-*]?\s*\*{0,2}\s*(?:locale|language|언어)[^:\n]{0,20}:\s*\*{0,2}\s*"
    r"([A-Za-z]{2}(?:[-_][A-Za-z]{2})?|한국어|영어)\b")

_registry = None


def registry():
    global _registry
    if _registry is None:
        with open(REGISTRY_PATH, encoding="utf-8") as fh:
            _registry = json.load(fh)
    return _registry


def supported():
    return list(registry()["locales"])


def default_locale():
    return registry()["default"]


def normalize(code):
    """'ko', 'ko_kr', 'KO-KR', '한국어' -> 'ko-KR'. Unknown -> None."""
    if not code:
        return None
    raw = str(code).strip()
    if raw == "영어":
        raw = "en"
    low = raw.lower().replace("_", "-")
    for canon, meta in registry()["locales"].items():
        if low == canon.lower() or low in [a.lower() for a in meta.get("aliases", [])]:
            return canon
    return None


def config_dir():
    return os.path.expanduser(os.environ.get("IG_CONFIG_DIR") or "~/.claude/instagram")


def load_config():
    """config.json from the profile folder, or {} if it is missing or broken."""
    path = os.path.join(config_dir(), "config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(updates):
    """Merge `updates` into config.json. Only called on an explicit --save."""
    data = load_config()
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    os.makedirs(config_dir(), exist_ok=True)
    path = os.path.join(config_dir(), "config.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return path


def profile_locale():
    """(locale, source) from config.json, then voice.md. (None, None) if unset."""
    loc = normalize(load_config().get("locale"))
    if loc:
        return loc, "config.json"
    try:
        with open(os.path.join(config_dir(), "voice.md"), encoding="utf-8") as fh:
            m = _VOICE_LOCALE.search(fh.read())
        if m and normalize(m.group(1)):
            return normalize(m.group(1)), "voice.md"
    except OSError:
        pass
    return None, None


def hangul_share(text):
    """Share of Hangul syllables among all letters. None if there are no letters."""
    h = len(_HANGUL.findall(text or ""))
    l = len(_LATIN.findall(text or ""))
    return None if h + l == 0 else h / (h + l)


def detect(text):
    """The locale the text is written in, or None if it has no letters."""
    share = hangul_share(text)
    if share is None:
        return None
    return "ko-KR" if share >= registry()["detect"]["hangul_share_for_ko"] else "en-US"


class Resolution:
    def __init__(self, locale, source, warning=None):
        self.locale, self.source, self.warning = locale, source, warning

    def __repr__(self):
        return f"Resolution({self.locale!r}, {self.source!r})"


def resolve(cli=None, text=None):
    """Apply the resolution order. Raises ValueError on an unknown locale."""
    if cli:
        loc = normalize(cli)
        if not loc:
            raise ValueError(f"unknown locale {cli!r}. Supported: {', '.join(supported())}")
        return Resolution(loc, "--locale")
    env = os.environ.get("IG_LOCALE")
    if env:
        loc = normalize(env)
        if not loc:
            raise ValueError(f"IG_LOCALE={env!r} is not a supported locale. "
                             f"Supported: {', '.join(supported())}")
        return Resolution(loc, "IG_LOCALE")
    loc, source = profile_locale()
    if loc:
        seen = detect(text) if text else None
        share = hangul_share(text) if text else None
        warning = None
        if seen and seen != loc and share is not None and (share >= 0.6 or share <= 0.02):
            warning = (f"note: locale {loc} from {source}, but the text looks {seen}. "
                       f"Pass --locale {seen} to analyse it as {seen}.")
        return Resolution(loc, source, warning)
    seen = detect(text) if text else None
    if seen:
        return Resolution(seen, "detected")
    return Resolution(default_locale(), "default")


def add_argument(parser):
    parser.add_argument(
        "--locale", default=None,
        help="en-US or ko-KR (also ko, en). Default: IG_LOCALE, then the profile "
             "in ~/.claude/instagram, then the language of the text, then en-US.")


def resolve_or_exit(cli, text):
    """resolve() for a CLI: prints the warning, exits 2 on an unknown locale."""
    try:
        res = resolve(cli, text)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    if res.warning:
        print(res.warning, file=sys.stderr)
    return res


def resource(skill_dir, name, locale):
    """Path to a data file for `locale`. en-US keeps the original location
    (skill_dir/name); every other locale lives in skill_dir/locales/<code>/name."""
    if locale == "en-US":
        return os.path.join(skill_dir, name)
    return os.path.join(skill_dir, "locales", locale, name)


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def speech_rate(locale):
    """(unit, rate, source). The profile's calibrated rate beats the default."""
    meta = registry()["locales"][locale]["speech"]
    unit = meta["unit"]
    saved = (load_config().get("speech") or {}).get(locale) or {}
    if isinstance(saved.get(unit), (int, float)) and saved[unit] > 0:
        return unit, float(saved[unit]), "config.json"
    return unit, float(meta["rate"]), "default"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Show which locale the pack would use.")
    add_argument(ap)
    ap.add_argument("--text", default="", help="sample text, for detection")
    a = ap.parse_args()
    r = resolve_or_exit(a.locale, a.text)
    print(json.dumps({"locale": r.locale, "source": r.source,
                      "config_dir": config_dir(), "supported": supported()},
                     ensure_ascii=False, indent=2))
