"""Korean text utilities: numbers read aloud, syllables, concreteness, width."""

import unittest

import helpers  # noqa: F401  (puts skills/ig-i18n on sys.path)
import ig_ko
import ig_text


class Numbers(unittest.TestCase):
    def test_read_int(self):
        cases = {"0": "영", "1": "일", "10": "십", "11": "십일", "20": "이십", "105": "백오",
                 "2026": "이천이십육", "10000": "만", "18000": "만팔천", "20000": "이만",
                 "3500000": "삼백오십만", "100000000": "일억", "120000000": "일억이천만"}
        for raw, said in cases.items():
            self.assertEqual(ig_ko.read_number(raw), said, raw)

    def test_commas_decimals_leading_zero(self):
        self.assertEqual(ig_ko.read_number("18,000"), "만팔천")
        self.assertEqual(ig_ko.read_number("3.5"), "삼점오")
        self.assertEqual(ig_ko.read_number("010"), "공일공")


class Syllables(unittest.TestCase):
    def test_hangul_only(self):
        self.assertEqual(ig_ko.spoken_syllables("회의록 정리")[0], 5)

    def test_numbers_are_expanded(self):
        total, parts = ig_ko.spoken_syllables("2026년")
        self.assertEqual(parts["number"], 5)      # 이천이십육
        self.assertEqual(total, 6)
        self.assertEqual(ig_ko.spoken_syllables("30%")[0], 2 + 3)   # 삼십 퍼센트
        self.assertEqual(ig_ko.spoken_syllables("$20")[0], 2 + 2)   # 이십 달러
        self.assertEqual(ig_ko.spoken_syllables("10K")[0], 1)       # 만

    def test_latin_estimates(self):
        exact = {"AI": 4, "GPT": 3, "API": 5, "Notion": 2, "Claude": 3, "ChatGPT": 4,
                 "Slack": 2, "Excel": 2}
        for word, n in exact.items():
            self.assertEqual(ig_ko.latin_syllables(word), n, word)
        # rough words: within one syllable of how they are said
        for word, said in {"Python": 3, "Figma": 3, "iPhone": 3, "Google": 2}.items():
            self.assertLessEqual(abs(ig_ko.latin_syllables(word) - said), 1, word)

    def test_mixed_line(self):
        total, parts = ig_ko.spoken_syllables("Claude한테 회의록 맡기면 5분")
        self.assertEqual(parts, {"hangul": 9, "number": 1, "latin": 3, "symbol": 0})
        self.assertEqual(total, 13)

    def test_emoji_and_jamo_are_silent(self):
        self.assertEqual(ig_ko.spoken_syllables("좋아요 👍 ㅋㅋ")[0], 3)

    def test_pauses(self):
        self.assertAlmostEqual(ig_ko.pause_seconds("하나, 둘. 셋"), 0.15 + 0.3)
        self.assertAlmostEqual(ig_ko.pause_seconds("하나 둘 셋", final=True), 0.3)
        self.assertEqual(ig_ko.pause_seconds("하나, 둘.", scale=0), 0)

    def test_speech_seconds_scales_with_rate(self):
        slow = ig_ko.speech_seconds("회의록 정리 자동화", 240, pause_scale=0)
        fast = ig_ko.speech_seconds("회의록 정리 자동화", 480, pause_scale=0)
        self.assertAlmostEqual(slow, 2 * fast)
        self.assertAlmostEqual(fast, 8 / 8.0)


class Tokens(unittest.TestCase):
    def test_strip_josa(self):
        self.assertEqual(ig_ko.strip_josa("계약서에서는"), "계약서")
        self.assertEqual(ig_ko.strip_josa("회의록을"), "회의록")
        self.assertEqual(ig_ko.strip_josa("Claude한테"), "Claude")
        self.assertEqual(ig_ko.strip_josa("5분이면"), "5분")
        self.assertEqual(ig_ko.strip_josa("나는"), "나는")       # too short to strip
        self.assertEqual(ig_ko.strip_josa("손으로"), "손으로")   # never a broken stem

    def test_content_words_ignore_particles(self):
        a = set(ig_ko.content_words("회의록 정리에 걸리던 1시간"))
        b = set(ig_ko.content_words("회의록을 정리하면 끝"))
        self.assertIn("회의록", a & b)

    def test_final_word(self):
        self.assertEqual(ig_ko.final_word("이 설정은 꼭 바꾸세요!"), "바꾸세요")
        self.assertEqual(ig_ko.final_word("끝입니다 🎉"), "끝입니다")


class Concrete(unittest.TestCase):
    def kinds(self, text):
        return [k for k, _ in ig_ko.concrete(text)]

    def test_kinds(self):
        self.assertEqual(self.kinds("30분"), ["time"])
        self.assertEqual(self.kinds("18,000원"), ["money"])
        self.assertEqual(self.kinds("73%"), ["percent"])
        self.assertEqual(self.kinds("세 가지"), ["count"])
        self.assertEqual(self.kinds("삼십 분"), ["number"])
        self.assertEqual(self.kinds("Notion"), ["name"])
        self.assertEqual(self.kinds("노션"), ["name"])
        self.assertEqual(self.kinds("연봉"), ["money"])

    def test_generic_words_are_not_concrete(self):
        for text in ("요즘 AI가 정말 다양한 분야에서 쓰입니다", "세상이 바뀝니다", "한 번 해 보세요",
                     "네가 해", "SNS 마케팅"):
            self.assertEqual(ig_ko.concrete(text), [], text)

    def test_overlaps_counted_once(self):
        self.assertEqual(len(ig_ko.concrete("월급 300만 원")), 2)   # 월급 + 300만 원


class Width(unittest.TestCase):
    def test_display_width(self):
        self.assertEqual(ig_text.display_width("abc"), 3)
        self.assertEqual(ig_text.display_width("회의록"), 6)
        self.assertEqual(ig_text.display_width("AI 자동화"), 9)
        self.assertEqual(ig_text.display_width("👩‍💻"), 2)

    def test_emoji_clusters(self):
        self.assertEqual(len(ig_text.emoji_clusters("👩‍💻 👍🏻 🇰🇷 ✅ ❤️")), 5)
        self.assertEqual(ig_text.emoji_clusters("→ 화살표는 이모지가 아님"), [])

    def test_cut_and_wrap(self):
        self.assertEqual(ig_text.cut_width("회의록정리", 5), "회의")
        lines = ig_text.wrap_width("회의록 정리를 자동화하는 가장 쉬운 방법", 12)
        self.assertTrue(all(ig_text.display_width(l) <= 12 for l in lines))
        self.assertEqual("".join(lines).replace(" ", ""), "회의록정리를자동화하는가장쉬운방법")


if __name__ == "__main__":
    unittest.main()
