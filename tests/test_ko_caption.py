"""ig-caption in Korean: hashtags, width-based cut, asks, mixed text, emoji."""

import unittest

from helpers import IsolatedConfig, fx, run, run_json


def lint(text, *args, **kw):
    _, a, _ = run_json("ig-caption/caption.py", ["-", "--locale", "ko-KR"] + list(args),
                       stdin=text, **kw)
    return a, {c["check"]: c for c in a["checks"]}


class Hashtags(unittest.TestCase):
    def test_hangul_hashtags_recognised(self):
        a, _ = lint("회의록 정리 방법입니다.\n\n#업무자동화 #회의록 #AI활용")
        self.assertEqual(a["hashtags"], ["#업무자동화", "#회의록", "#AI활용"])

    def test_hashtag_ends_at_punctuation(self):
        a, _ = lint("끝.\n\n#업무자동화, #회의록!")
        self.assertEqual(a["hashtags"], ["#업무자동화", "#회의록"])

    def test_cap_is_enforced(self):
        a, c = lint("본문.\n\n#가 #나 #다 #라 #마 #바")
        self.assertEqual(c["HASHTAGS"]["status"], "FAIL")
        self.assertEqual(a["verdict"], "FIX")

    def test_korean_filler_tags(self):
        _, c = lint("본문.\n\n#업무자동화 #맞팔 #좋아요반사")
        self.assertEqual(c["HASHTAGS"]["status"], "WARN")
        self.assertIn("#맞팔", c["HASHTAGS"]["detail"])

    def test_english_locale_keeps_old_ascii_rule(self):
        """Unchanged on purpose: en-US output must stay byte-identical to v1.0."""
        _, a, _ = run_json("ig-caption/caption.py", ["-", "--locale", "en-US"],
                           stdin="Body text here.\n\n#freelance #자동화")
        self.assertEqual(a["hashtags"], ["#freelance"])


class Window(unittest.TestCase):
    def test_cut_by_display_width(self):
        text = "가" * 100
        a, c = lint(text)
        self.assertEqual(len(a["visible"]), 62)          # 125 width units / 2
        self.assertTrue(a["truncated"])
        self.assertEqual(c["FIRST LINE"]["status"], "WARN")

    def test_cut_by_chars_on_request(self):
        a, _ = lint("가" * 100, "--truncate-unit", "chars")
        self.assertEqual(len(a["visible"]), 100)
        self.assertFalse(a["truncated"])

    def test_mixed_korean_english_emoji(self):
        text = "Claude로 회의록 5분 정리 👩‍💻 " + "a" * 100
        a, _ = lint(text)
        from ig_text import display_width
        self.assertLessEqual(display_width(a["visible"]), 125)
        self.assertTrue(a["visible"].startswith("Claude로 회의록 5분 정리 👩‍💻"))

    def test_concrete_window(self):
        _, c = lint("회의록 정리를 5분 만에 끝내는 방법")
        self.assertEqual(c["HOOK IS CONCRETE"]["status"], "PASS")
        _, c = lint("일을 더 편하게 만드는 방법")
        self.assertEqual(c["HOOK IS CONCRETE"]["status"], "WARN")


class FirstLine(unittest.TestCase):
    def test_greeting_and_announcement(self):
        for text in ("안녕하세요! 오늘도 좋은 하루", "오늘은 회의록 자동화에 대해 알아보겠습니다",
                     "혹시 회의록 정리 때문에 야근하신 적 있으신가요?"):
            _, c = lint(text)
            self.assertEqual(c["FIRST LINE"]["status"], "WARN", text)

    def test_hashtag_first_fails(self):
        _, c = lint("#업무자동화 회의록 정리")
        self.assertEqual(c["FIRST LINE"]["status"], "FAIL")


class Asks(unittest.TestCase):
    def test_keyword_ask(self):
        a, c = lint("본문.\n\n댓글에 '회의록' 남겨 주세요.")
        self.assertEqual(a["asks"], ["댓글 키워드"])
        self.assertEqual(c["ONE ASK"]["status"], "PASS")

    def test_two_asks_warn(self):
        a, c = lint("본문.\n\n저장해 두세요. 팔로우하고 다음 편도 보세요.")
        self.assertEqual(len(a["asks"]), 2)
        self.assertEqual(c["ONE ASK"]["status"], "WARN")

    def test_mixed_language_ask_counted_once(self):
        a, _ = lint("본문.\n\nDM 주세요. DM me for the file.")
        self.assertEqual(a["asks"], ["DM"])

    def test_comment_below_is_one_general_request(self):
        for text in ("Comment below.", "본문. Comment below!", "comment BELOW"):
            a, c = lint(text)
            self.assertEqual(a["asks"], ["댓글 요청"], text)
            self.assertEqual(c["ONE ASK"]["status"], "PASS", text)

    def test_explicit_english_keywords_are_still_recognised(self):
        for text in ('Comment "GUIDE" below.', 'Comment the word below.',
                     'Comment GUIDE to get the file.'):
            a, c = lint(text)
            self.assertEqual(a["asks"], ["댓글 키워드"], text)
            self.assertEqual(c["ONE ASK"]["status"], "PASS", text)

    def test_link_in_caption(self):
        _, c = lint("자세한 건 example.co.kr/guide 참고")
        self.assertEqual(c["LINKS"]["status"], "WARN")


class Misc(unittest.TestCase):
    def test_emoji_counted_as_seen(self):
        a, _ = lint("좋아요 👍🏻 개발 👩‍💻 한국 🇰🇷")
        self.assertEqual(a["emoji"], 3)

    def test_search_terms_ignore_spacing(self):
        _, c = lint("업무자동화로 회의록 정리하기", "--keywords", "업무 자동화,회의록 정리,노션 템플릿")
        self.assertEqual(c["SEARCH TERMS"]["status"], "WARN")
        self.assertIn("2/3", c["SEARCH TERMS"]["detail"])

    def test_paragraph_wall(self):
        wall = "회의록을 정리하는 방법은 여러 가지가 있습니다. " * 12
        _, c = lint(wall)
        self.assertEqual(c["PARAGRAPHS"]["status"], "WARN")
        _, c = lint(open(fx("caption_ko.txt"), encoding="utf-8").read())
        self.assertEqual(c["PARAGRAPHS"]["status"], "PASS")

    def test_platform_numbers_are_configurable(self):
        text = "본문.\n\n#가 #나 #다 #라 #마 #바"
        _, c = lint(text, "--hashtag-limit", "10")
        self.assertEqual(c["HASHTAGS"]["status"], "PASS")
        with IsolatedConfig(config={"platform": {"hashtag_limit": 3, "caption_limit": 10}}) as cfg:
            a, c = lint("본문은 열 자를 넘깁니다.\n\n#가 #나 #다 #라", config_dir=cfg.path)
        self.assertEqual(c["HASHTAGS"]["status"], "FAIL")
        self.assertEqual(c["LENGTH"]["status"], "FAIL")
        self.assertEqual(a["limit"], 10)

    def test_render_is_korean(self):
        code, out, _ = run("ig-caption/caption.py", [fx("caption_ko.txt"), "--locale", "ko-KR"])
        self.assertIn("피드에 보이는 부분", out)
        self.assertIn("판정", out)
        for english in ("WHAT THE FEED SHOWS", "VERDICT", "PASS  LENGTH"):
            self.assertNotIn(english, out)


class KeywordAskForms(unittest.TestCase):
    """The comment-keyword ask in the forms people actually write (2026-10-22 comparison report)."""

    def test_conditional_and_polite_forms(self):
        for text in ("댓글에 '회의록' 남기면 보내드려요", "댓글에 '회의록' 남겨 주시면 보내드려요",
                     "댓글로 회의록 적으면 링크 드려요", "댓글에 '프롬프트'라고 달면 DM 드려요"):
            a, c = lint(text)
            self.assertEqual(c["ONE ASK"]["status"], "PASS", text)
            self.assertIn("댓글", c["ONE ASK"]["detail"], text)

    def test_with_save_it_is_two_asks(self):
        _, c = lint("저장해 두세요\n댓글에 '회의록' 남기면 보내드려요")
        self.assertEqual(c["ONE ASK"]["status"], "WARN")


if __name__ == "__main__":
    unittest.main()
