"""The pack still installs and is invoked the way v1.0 was, and every skill
has its Korean resources."""

import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT, SKILLS, fx, run
from golden_cases import GOLDEN

ORIGINAL_SKILL_NAMES = ["ig-audit", "ig-caption", "ig-carousel", "ig-comment", "ig-dm",
                        "ig-human", "ig-plan", "ig-profile", "ig-reel", "ig-reply",
                        "ig-repurpose", "ig-story", "ig-viral"]
SKILL_NAMES = sorted(ORIGINAL_SKILL_NAMES + ["ig-help"])
V1 = "d03c56b"     # the last upstream commit before the i18n work


def frontmatter(path):
    text = open(path, encoding="utf-8").read()
    _, fm, _ = text.split("---", 2)
    return fm, text


class Layout(unittest.TestCase):
    def test_fourteen_skills_and_a_library(self):
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
                  os.path.join(ROOT, "README.md"),
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
        self.assertIn("Jake Schincariol", open(os.path.join(ROOT, "README.md")).read())
        self.assertIn("Made by Jake Schincariol", open(os.path.join(ROOT, "README.en.md")).read())

    def test_help_catalogs_cover_each_available_skill_once(self):
        available = {os.path.basename(os.path.dirname(p))
                     for p in glob.glob(os.path.join(SKILLS, "*", "SKILL.md"))}
        for relative in ("SKILL.md", "locales/ko-KR/guide.md"):
            path = os.path.join(SKILLS, "ig-help", relative)
            with open(path, encoding="utf-8") as fh:
                commands = re.findall(r"^\| `/([a-z0-9-]+)` \|", fh.read(), re.M)
            self.assertCountEqual(commands, available, relative)

    def test_help_reference_links_resolve(self):
        path = os.path.join(SKILLS, "ig-help", "SKILL.md")
        with open(path, encoding="utf-8") as fh:
            links = re.findall(r"\]\(([^)]+\.md)\)", fh.read())
        self.assertTrue(links)
        for link in links:
            self.assertTrue(os.path.isfile(os.path.join(os.path.dirname(path), link)), link)


@unittest.skipUnless(shutil.which("git"), "git not available")
class EnglishSkillTextKept(unittest.TestCase):
    """Keep original workflow sections and tool names while permitting corrected
    instructions, such as ending an insufficient-text check without rewriting."""

    def test_original_workflow_sections_and_tools_are_kept(self):
        for name in ORIGINAL_SKILL_NAMES:
            proc = subprocess.run(["git", "show", f"{V1}:skills/{name}/SKILL.md"], cwd=ROOT,
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                self.skipTest("v1.0 commit not in this checkout")
            with open(os.path.join(SKILLS, name, "SKILL.md"), encoding="utf-8") as fh:
                new = fh.read()
            headings = re.findall(r"^#{1,6} .+$", proc.stdout, re.M)
            it = iter(re.findall(r"^#{1,6} .+$", new, re.M))
            missing = [heading for heading in headings if not any(heading == h for h in it)]
            self.assertEqual(missing, [], name)
            old_tools = set(re.findall(r"\b[\w-]+\.py\b", proc.stdout))
            self.assertTrue(old_tools <= set(re.findall(r"\b[\w-]+\.py\b", new)), name)


class Install(unittest.TestCase):
    """The README install (cp -r skills/ig-* ~/.claude/skills/) must carry the
    shared ig-i18n folder, and a skill copied alone must still work in English."""

    def test_documented_copy_brings_the_library(self):
        for doc in ("README.md", "README.en.md"):
            with open(os.path.join(ROOT, doc), encoding="utf-8") as fh:
                block = next(b for b in re.findall(r"```bash\n(.*?)```", fh.read(), re.S)
                             if "git clone " in b)
            # The repository is already fetched. Exercise the remaining install
            # instructions against a fresh profile directory, not the real home.
            commands = "\n".join(line for line in block.splitlines()
                                 if not line.startswith("git clone "))
            with tempfile.TemporaryDirectory() as work:
                os.symlink(ROOT, os.path.join(work, "instagram-agent-skill"))
                commands = commands.replace("~/", shlex.quote(work) + "/")
                proc = subprocess.run(["bash", "-e", "-c", commands], cwd=work,
                                      capture_output=True, text=True)
                self.assertEqual(proc.returncode, 0, doc + ": " + proc.stderr)
                dest = os.path.join(work, ".claude", "skills")
                self.assertTrue(os.path.exists(os.path.join(dest, "ig-i18n", "ig_locale.py")))
                self.assertTrue(os.path.isfile(os.path.join(dest, "ig-help", "SKILL.md")))
                self.assertTrue(os.path.isfile(os.path.join(
                    dest, "ig-help", "locales", "ko-KR", "guide.md")))
                code, out, _ = run(os.path.join(dest, "ig-reel", "hookscore.py"),
                                   ["--hook", "회의록 정리, 이제 5분이면 끝납니다", "--locale", "ko-KR"])
                self.assertIn(code, (0, 1))
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


class IntegrationHarness(unittest.TestCase):
    """Check the runner's success/failure handling without calling a model."""

    def _run_case(self, case):
        mock = r'''#!/usr/bin/env python3
import json, os, sys
case = os.environ["IG_INTEGRATION_CASE"]
ko = "--locale ko-KR" in sys.argv[-1]
if case in ("process_error", "error_text"):
    print("휴리스틱 점수를 계산할 수 없습니다." if ko else
          "Cannot run hookscore.py; no hook score was computed.")
    sys.exit(7 if case == "process_error" else 0)
locale = "ko-KR" if ko else "en-US"
rows = [{"hook": ("회의록 정리 " if ko else "Organize meeting notes ") + str(i),
         "locale": "en-US" if case == "wrong_locale" else locale,
         "score": 80.0, "verdict": "STRONG",
         "checks": {k: {"score": 80.0, "detail": "checked"} for k in
                    ["LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"]}}
        for i in range(3)]
if case == "invalid_score":
    rows[0]["score"] = "not scored"
output = ("\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
          if case == "multiple_documents" else json.dumps(rows, ensure_ascii=False))
if case != "no_tool":
    print(json.dumps({"type": "assistant", "message": {"content": [{
        "type": "tool_use", "id": "score-1", "name": "Bash", "input": {
            "command": "python3 /plugin/skills/ig-reel/hookscore.py hooks.txt --json --locale " + locale}}]}}))
    print(json.dumps({"type": "user", "message": {"content": [{
        "type": "tool_result", "tool_use_id": "score-1", "is_error": case == "tool_error",
        "content": output}]}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "휴리스틱 훅 점수입니다." if ko else "Hook scores are ready."}))
'''
        with tempfile.TemporaryDirectory() as work:
            mock_path = os.path.join(work, "claude")
            with open(mock_path, "w", encoding="utf-8") as fh:
                fh.write(mock.replace("#!/usr/bin/env python3", "#!" + sys.executable, 1))
            os.chmod(mock_path, 0o755)
            env = dict(os.environ, PATH=work + os.pathsep + os.environ.get("PATH", ""),
                       TMPDIR=work, IG_INTEGRATION_CASE=case)
            return subprocess.run(["bash", os.path.join(ROOT, "tests/integration/claude_cli.sh")],
                                  env=env, capture_output=True, text=True)

    def test_failures_and_unscored_responses_do_not_pass(self):
        for case in ("process_error", "error_text", "no_tool", "tool_error",
                     "wrong_locale", "invalid_score"):
            with self.subTest(case=case):
                proc = self._run_case(case)
                self.assertNotEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_successful_scoring_events_pass(self):
        for case in ("success", "multiple_documents"):
            with self.subTest(case=case):
                proc = self._run_case(case)
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
