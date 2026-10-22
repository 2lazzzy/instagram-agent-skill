"""Locale selection: explicit beats profile beats detection beats default."""

import os
import unittest

from helpers import IsolatedConfig, run, run_json, fx, SKILLS
import ig_locale


class Normalize(unittest.TestCase):
    def test_aliases(self):
        for raw in ("ko", "ko-KR", "ko_kr", "KO-KR", "korean", "한국어", "kr"):
            self.assertEqual(ig_locale.normalize(raw), "ko-KR", raw)
        for raw in ("en", "en-US", "en_us", "English"):
            self.assertEqual(ig_locale.normalize(raw), "en-US", raw)

    def test_unknown(self):
        self.assertIsNone(ig_locale.normalize("ja-JP"))
        self.assertIsNone(ig_locale.normalize(""))
        self.assertIsNone(ig_locale.normalize(None))

    def test_registry_lists_both(self):
        self.assertEqual(ig_locale.supported(), ["en-US", "ko-KR"])
        self.assertEqual(ig_locale.default_locale(), "en-US")


class Detect(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(ig_locale.detect("회의록 정리, 이제 5분이면 끝납니다"), "ko-KR")
        self.assertEqual(ig_locale.detect("Proposals used to take five hours"), "en-US")
        # Korean with product names is still Korean
        self.assertEqual(ig_locale.detect("Claude랑 Notion으로 회의록 자동화하기"), "ko-KR")
        # English with one Korean hashtag is still English
        self.assertEqual(ig_locale.detect("Steal this four line follow up. #자동화"), "en-US")
        self.assertIsNone(ig_locale.detect("123 456 🔥"))


class Priority(unittest.TestCase):
    def test_default_is_en(self):
        with IsolatedConfig():
            r = ig_locale.resolve(None, "")
            self.assertEqual((r.locale, r.source), ("en-US", "default"))

    def test_detected_when_nothing_set(self):
        with IsolatedConfig():
            self.assertEqual(ig_locale.resolve(None, "회의록 정리").locale, "ko-KR")
            self.assertEqual(ig_locale.resolve(None, "meeting notes").locale, "en-US")

    def test_voice_md_beats_detection(self):
        with IsolatedConfig(voice="- **Locale:** ko-KR\n"):
            r = ig_locale.resolve(None, "회의록")
            self.assertEqual((r.locale, r.source), ("ko-KR", "voice.md"))

    def test_config_beats_voice_md(self):
        with IsolatedConfig(config={"locale": "en-US"}, voice="- **Locale:** ko-KR\n"):
            self.assertEqual(ig_locale.resolve(None, "").source, "config.json")
            self.assertEqual(ig_locale.resolve(None, "").locale, "en-US")

    def test_env_beats_config(self):
        with IsolatedConfig(config={"locale": "en-US"}):
            os.environ["IG_LOCALE"] = "ko"
            try:
                r = ig_locale.resolve(None, "plain english")
            finally:
                os.environ.pop("IG_LOCALE")
            self.assertEqual((r.locale, r.source), ("ko-KR", "IG_LOCALE"))

    def test_cli_beats_everything(self):
        with IsolatedConfig(config={"locale": "ko-KR"}):
            os.environ["IG_LOCALE"] = "ko-KR"
            try:
                r = ig_locale.resolve("en", "회의록")
            finally:
                os.environ.pop("IG_LOCALE")
            self.assertEqual((r.locale, r.source), ("en-US", "--locale"))

    def test_unknown_cli_raises(self):
        with IsolatedConfig():
            with self.assertRaises(ValueError):
                ig_locale.resolve("ja-JP", "")

    def test_profile_mismatch_warns_but_obeys(self):
        with IsolatedConfig(config={"locale": "ko-KR"}):
            r = ig_locale.resolve(None, "This is a plain English caption about invoices.")
            self.assertEqual(r.locale, "ko-KR")
            self.assertIn("--locale en-US", r.warning)

    def test_unfilled_template_sets_nothing(self):
        with open(os.path.join(os.path.dirname(SKILLS), "templates", "voice.md"), encoding="utf-8") as fh:
            template = fh.read()
        with IsolatedConfig(voice=template):
            self.assertEqual(ig_locale.profile_locale(), (None, None))

    def test_korean_template_sets_korean(self):
        with open(os.path.join(os.path.dirname(SKILLS), "templates", "voice.ko-KR.md"),
                  encoding="utf-8") as fh:
            template = fh.read()
        with IsolatedConfig(voice=template):
            self.assertEqual(ig_locale.profile_locale()[0], "ko-KR")


class Resources(unittest.TestCase):
    def test_en_keeps_original_paths(self):
        d = os.path.join(SKILLS, "ig-reel")
        self.assertEqual(ig_locale.resource(d, "hooks.json", "en-US"), os.path.join(d, "hooks.json"))
        self.assertTrue(os.path.exists(ig_locale.resource(d, "hooks.json", "ko-KR")))

    def test_speech_rate_default_and_config(self):
        with IsolatedConfig():
            self.assertEqual(ig_locale.speech_rate("ko-KR"), ("spm", 330.0, "default"))
        with IsolatedConfig(config={"speech": {"ko-KR": {"spm": 290}}}):
            self.assertEqual(ig_locale.speech_rate("ko-KR"), ("spm", 290.0, "config.json"))


class CliBehaviour(unittest.TestCase):
    """The same order, seen from the command line."""

    def test_flag_forces_korean_on_english_text(self):
        _, d, _ = run_json("ig-reel/hookscore.py", ["--hook", "Stop scrolling", "--locale", "ko"])
        self.assertEqual(d["locale"], "ko-KR")

    def test_env_variable(self):
        _, d, _ = run_json("ig-reel/hookscore.py", ["--hook", "회의록 정리"],
                           env_extra={"IG_LOCALE": "en-US"})
        self.assertEqual(d["locale"], "en-US")

    def test_detection_without_flag(self):
        _, d, _ = run_json("ig-reel/hookscore.py", ["--hook", "회의록 정리, 이제 5분이면 끝납니다"])
        self.assertEqual(d["locale"], "ko-KR")
        _, d, _ = run_json("ig-reel/hookscore.py", ["--hook", "Proposals take twenty minutes now"])
        self.assertEqual(d["locale"], "en-US")

    def test_profile_locale_from_config(self):
        with IsolatedConfig(config={"locale": "ko-KR"}) as cfg:
            code, out, err = run("ig-caption/caption.py", [fx("caption.txt", "en")],
                                 config_dir=cfg.path)
        self.assertIn("캡션 검사", out)
        self.assertIn("--locale en-US", err)          # the mismatch is visible

    def test_invalid_locale_exits_2(self):
        for script, args in (("ig-reel/hookscore.py", ["--hook", "x"]),
                             ("ig-reel/beats.py", [fx("script.txt", "en")]),
                             ("ig-caption/caption.py", [fx("caption.txt", "en")]),
                             ("ig-human/humanize.py", [fx("draft_slop.txt", "en")]),
                             ("ig-human/detect.py", [fx("draft_slop.txt", "en")]),
                             ("ig-viral/swipe.py", [fx("swipe.tsv", "en")])):
            code, _, err = run(script, args + ["--locale", "xx-YY"])
            self.assertEqual(code, 2, script)
            self.assertIn("Supported", err, script)


if __name__ == "__main__":
    unittest.main()
