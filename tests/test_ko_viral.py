"""ig-viral in Korean: Korean counts, per-row locale, Korean formulas."""

import unittest

from helpers import fx, run, run_json
import swipe


class Counts(unittest.TestCase):
    def test_korean_units(self):
        self.assertEqual(swipe.parse_count("41.2만"), 412000)
        self.assertEqual(swipe.parse_count("1.5천"), 1500)
        self.assertEqual(swipe.parse_count("3억"), 300000000)
        self.assertEqual(swipe.parse_count("1,200만"), 12000000)

    def test_english_counts_unchanged(self):
        self.assertEqual(swipe.parse_count("412,000"), 412000)
        self.assertEqual(swipe.parse_count("12000"), 12000)
        self.assertIsNone(swipe.parse_count(""))


class Rows(unittest.TestCase):
    def test_mixed_batch_reads_each_row_in_its_language(self):
        _, a, _ = run_json("ig-viral/swipe.py", [fx("swipe_mixed.tsv")])
        by_account = {r["account"]: r for r in a["reels"]}
        self.assertEqual(a["locale"], "mixed")
        self.assertEqual(by_account["@dev_a"]["locale"], "ko-KR")
        self.assertEqual(by_account["@dev_a"]["formula_id"], 3)
        self.assertEqual(by_account["@dev_c"]["formula_id"], 5)
        self.assertEqual(by_account["@en_d"]["locale"], "en-US")
        self.assertEqual(by_account["@en_d"]["formula_id"], 3)
        self.assertEqual(by_account["@dev_a"]["views"], 412000)
        self.assertEqual(by_account["@dev_a"]["baseline"], 3000)

    def test_greeting_hook_scores_low(self):
        _, a, _ = run_json("ig-viral/swipe.py", [fx("swipe_mixed.tsv")])
        greet = [r for r in a["reels"] if r["account"] == "@dev_b"][0]
        self.assertLess(greet["hook_score"], 30)
        self.assertIsNone(greet["formula_id"])

    def test_forced_locale(self):
        _, a, _ = run_json("ig-viral/swipe.py", [fx("swipe_mixed.tsv"), "--locale", "ko-KR"])
        self.assertEqual({r["locale"] for r in a["reels"]}, {"ko-KR"})

    def test_korean_report(self):
        code, out, _ = run("ig-viral/swipe.py", [fx("swipe_mixed.tsv"), "--locale", "ko-KR"])
        self.assertIn("스와이프 파일", out)
        self.assertIn("조회수 예측이 아닙니다", out)


if __name__ == "__main__":
    unittest.main()
