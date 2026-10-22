"""
English regression cases.

Every case here was run against the original v1.0 scripts (before any i18n
work) and its output was frozen in tests/golden/en/. The test suite re-runs the
same commands and requires the same output, so the English behaviour cannot
drift silently.

Regenerate only on purpose:  python3 tests/golden_cases.py --write
"""

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
FIX = os.path.join(ROOT, "tests", "fixtures", "en")
GOLDEN = os.path.join(ROOT, "tests", "golden", "en")

# name, script (relative to skills/), argv (fixture names are resolved), is_json
CASES = [
    ("hookscore_rank", "ig-reel/hookscore.py", ["hooks.txt"], False),
    ("hookscore_rank_json", "ig-reel/hookscore.py", ["hooks.txt", "--json"], True),
    ("hookscore_one", "ig-reel/hookscore.py",
     ["--hook", "I lost $18,000 because of one missing contract."], False),
    ("hookscore_one_json", "ig-reel/hookscore.py",
     ["--hook", "Hey guys, today I wanted to talk about content strategy", "--json"], True),
    ("beats_target", "ig-reel/beats.py", ["script.txt", "--target", "30"], False),
    ("beats_wpm_json", "ig-reel/beats.py", ["script.txt", "--wpm", "185", "--json"], True),
    ("caption_good", "ig-caption/caption.py",
     ["caption.txt", "--keywords", "client contracts,freelance pricing"], False),
    ("caption_bad", "ig-caption/caption.py", ["caption_bad.txt"], False),
    ("caption_bad_json", "ig-caption/caption.py", ["caption_bad.txt", "--json"], True),
    ("humanize_slop", "ig-human/humanize.py", ["draft_slop.txt", "--report"], False),
    ("humanize_slop_json", "ig-human/humanize.py", ["draft_slop.txt", "--json"], True),
    ("detect_slop", "ig-human/detect.py", ["draft_slop.txt"], False),
    ("detect_human_json", "ig-human/detect.py", ["draft_human.txt", "--json"], True),
    ("detect_compare", "ig-human/detect.py", ["draft_slop.txt", "draft_human.txt"], False),
    ("swipe", "ig-viral/swipe.py", ["swipe.tsv"], False),
    ("swipe_json", "ig-viral/swipe.py", ["swipe.tsv", "--json"], True),
]


def clean_env(config_dir):
    env = dict(os.environ)
    env.pop("IG_LOCALE", None)
    env["IG_CONFIG_DIR"] = config_dir      # never read the real ~/.claude/instagram
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_case(script, argv, config_dir):
    args = [os.path.join(FIX, a) if os.path.exists(os.path.join(FIX, a)) else a for a in argv]
    proc = subprocess.run([sys.executable, os.path.join(SKILLS, script)] + args,
                          capture_output=True, text=True, encoding="utf-8",
                          env=clean_env(config_dir), cwd=ROOT)
    return proc.returncode, proc.stdout, proc.stderr


def strip_locale(obj):
    """The i18n work adds a `locale` field to JSON output. It is the only
    permitted difference, so it is removed before comparing."""
    if isinstance(obj, dict):
        return {k: strip_locale(v) for k, v in obj.items() if k != "locale"}
    if isinstance(obj, list):
        return [strip_locale(v) for v in obj]
    return obj


def write():
    os.makedirs(GOLDEN, exist_ok=True)
    with tempfile.TemporaryDirectory() as cfg:
        for name, script, argv, _ in CASES:
            code, out, err = run_case(script, argv, cfg)
            with open(os.path.join(GOLDEN, name + ".json"), "w", encoding="utf-8") as fh:
                json.dump({"code": code, "stdout": out, "stderr": err}, fh,
                          ensure_ascii=False, indent=1)
            print(f"{name:<24} exit {code}")


if __name__ == "__main__":
    if "--write" in sys.argv:
        write()
    else:
        print(__doc__)
