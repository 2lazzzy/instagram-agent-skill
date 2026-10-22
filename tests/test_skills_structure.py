"""The pack still installs and is invoked the way v1.0 was, and every skill
has its Korean resources."""

import glob
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from helpers import ROOT, SKILLS, fx, run
from golden_cases import GOLDEN

SKILL_NAMES = ["ig-audit", "ig-caption", "ig-carousel", "ig-comment", "ig-dm", "ig-human",
               "ig-plan", "ig-profile", "ig-reel", "ig-reply", "ig-repurpose", "ig-story",
               "ig-viral"]
V1 = "d03c56b"     # the last upstream commit before the i18n work


def frontmatter(path):
    text = open(path, encoding="utf-8").read()
    _, fm, _ = text.split("---", 2)
    return fm, text


class Layout(unittest.TestCase):
    def test_thirteen_skills_and_a_library(self):
        found = sorted(os.path.basename(os.path.dirname(p))
                       for p in glob.glob(os.path.join(SKILLS, "*", "SKILL.md")))
        self.assertEqual(found, SKILL_NAMES)
        self.assertFalse(os.path.exists(os.path.join(SKILLS, "ig-i18n", "SKILL.md")))

    def test_frontmatter(self):
        for name in SKILL_NAMES:
            fm, _ = frontmatter(os.path.join(SKILLS, name, "SKILL.md"))
            self.assertIn(f"name: {name}\n", fm)
            self.assertIn("description: >-", fm)
            self.assertIn("ko-KR", fm)

    def test_language_section_and_guides(self):
        style = os.path.join(SKILLS, "ig-i18n", "style-ko-KR.md")
        self.assertTrue(os.path.getsize(style) > 500)
        for name in SKILL_NAMES:
            _, text = frontmatter(os.path.join(SKILLS, name, "SKILL.md"))
            self.assertIn("## Language (en-US, ko-KR)", text, name)
            self.assertIn("locales/ko-KR/guide.md", text, name)
            guide = os.path.join(SKILLS, name, "locales", "ko-KR", "guide.md")
            body = open(guide, encoding="utf-8").read()
            self.assertIn("style-ko-KR.md", body, name)
            self.assertGreater(len(body), 800, name)

    def test_korean_docs_avoid_middle_dot_and_dash(self):
        paths = glob.glob(os.path.join(SKILLS, "*", "locales", "ko-KR", "guide.md"))
        paths += [os.path.join(SKILLS, "ig-i18n", "style-ko-KR.md"),
                  os.path.join(ROOT, "README.ko.md"), os.path.join(ROOT, "docs", "i18n.md"),
                  os.path.join(ROOT, "templates", "voice.ko-KR.md")]
        for p in paths:
            if not os.path.exists(p):
                continue
            for n, line in enumerate(open(p, encoding="utf-8"), 1):
                if "가운뎃점" in line or "줄표" in line or "middle dot" in line.lower():
                    continue            # the rule itself names the characters
                self.assertNotIn("·", line, f"{p}:{n}")
                self.assertNotIn("—", line, f"{p}:{n}")

    def test_plugin_manifests(self):
        plugin = json.load(open(os.path.join(ROOT, ".claude-plugin", "plugin.json")))
        market = json.load(open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")))
        self.assertEqual(plugin["name"], "instagram-agent")
        self.assertEqual(plugin["author"]["name"], "Jake Schincariol")
        self.assertEqual(plugin["license"], "MIT")
        self.assertEqual(market["plugins"][0]["name"], "instagram-agent")

    def test_license_and_credit_kept(self):
        self.assertIn("Jake Schincariol", open(os.path.join(ROOT, "LICENSE")).read())
        self.assertIn("Made by Jake Schincariol", open(os.path.join(ROOT, "README.md")).read())


@unittest.skipUnless(shutil.which("git"), "git not available")
class EnglishSkillTextKept(unittest.TestCase):
    """Every line of each v1.0 SKILL.md is still there, in the same order.
    The i18n work only inserted lines; it did not rewrite English guidance."""

    def test_v1_lines_are_a_subsequence(self):
        for name in SKILL_NAMES:
            proc = subprocess.run(["git", "show", f"{V1}:skills/{name}/SKILL.md"], cwd=ROOT,
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                self.skipTest("v1.0 commit not in this checkout")
            old = proc.stdout.splitlines()
            new = open(os.path.join(SKILLS, name, "SKILL.md"), encoding="utf-8").read().splitlines()
            it = iter(new)
            missing = [l for l in old if not any(l == n for n in it)]
            self.assertEqual(missing, [], name)


class Install(unittest.TestCase):
    """The README install (cp -r skills/ig-* ~/.claude/skills/) must carry the
    shared ig-i18n folder, and a skill copied alone must still work in English."""

    def test_documented_copy_brings_the_library(self):
        with tempfile.TemporaryDirectory() as dest:
            for path in glob.glob(os.path.join(SKILLS, "ig-*")):
                shutil.copytree(path, os.path.join(dest, os.path.basename(path)))
            self.assertTrue(os.path.exists(os.path.join(dest, "ig-i18n", "ig_locale.py")))
            code, out, _ = run(os.path.join(dest, "ig-reel", "hookscore.py"),
                               ["--hook", "회의록 정리, 이제 5분이면 끝납니다", "--locale", "ko-KR"])
            self.assertEqual(code in (0, 1), True)
            self.assertIn("훅 점수", out)

    def test_single_skill_copied_alone_still_runs_english(self):
        cases = [("ig-reel", "hookscore.py", ["hooks.txt"], "hookscore_rank"),
                 ("ig-reel", "beats.py", ["script.txt", "--target", "30"], "beats_target"),
                 ("ig-caption", "caption.py", ["caption.txt", "--keywords",
                                                "client contracts,freelance pricing"], "caption_good"),
                 ("ig-human", "detect.py", ["draft_slop.txt"], "detect_slop")]
        for skill, script, args, golden in cases:
            with tempfile.TemporaryDirectory() as dest:
                shutil.copytree(os.path.join(SKILLS, skill), os.path.join(dest, skill),
                                ignore=shutil.ignore_patterns("__pycache__"))
                argv = [fx(a, "en") if a.endswith((".txt", ".tsv")) else a for a in args]
                code, out, _ = run(os.path.join(dest, skill, script), argv)
                gold = json.load(open(os.path.join(GOLDEN, golden + ".json"), encoding="utf-8"))
                self.assertEqual(out, gold["stdout"], f"{skill}/{script} alone")
                self.assertEqual(code, gold["code"])
                code, _, err = run(os.path.join(dest, skill, script), argv + ["--locale", "ko-KR"])
                self.assertEqual(code, 2, f"{skill}/{script} alone with ko-KR")
                self.assertIn("ig-i18n", err)


if __name__ == "__main__":
    unittest.main()
