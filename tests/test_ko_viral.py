"""ig-viral in Korean: Korean counts, per-row locale, Korean formulas."""

import pathlib
import tempfile
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

    def test_english_abbreviated_counts(self):
        for value, count in (("41.2K", 41200), ("1.2M", 1200000),
                             (" 2.5k ", 2500), ("1B", 1000000000)):
            with self.subTest(value=value):
                self.assertEqual(swipe.parse_count(value), count)

    def test_malformed_counts_are_rejected(self):
        for value in ("-12", "1,2", "41..2K", "1.2.3만", "12 views", "1e3",
                      "NaN", "inf", "true", True, False, "1/2", "1.2"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    swipe.parse_count(value)

    def test_counts_are_exact_beyond_decimal_context_precision(self):
        self.assertEqual(swipe.parse_count("12345678901234567890123456789"),
                         12345678901234567890123456789)
        with self.assertRaises(ValueError):
            swipe.parse_count("1.00000000000000000000000000001")


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


class Baselines(unittest.TestCase):
    header = "account\tfollowers\tmedian\tviews\thook\n"
    ranked = ("@top\t10K\t1000\t41.2K\tnobody tells you your first 30 reels flop\n"
              "@middle\t20K\t2000\t10K\tI lost $18,000 because of one missing contract\n"
              "@bottom\t5K\t1000\t900\tin this video I am going to show you my morning routine\n")
    references = ("@reference\t100\t\t1.2M\tsteal this four line follow up it took me two years\n"
                  "@unknown\t\t0\t200\thello\n")

    def test_reference_rows_cannot_change_ranking_or_analysis(self):
        code, a, err = run_json("ig-viral/swipe.py", stdin=self.header + self.ranked + self.references)
        _, only_ranked, _ = run_json("ig-viral/swipe.py", stdin=self.header + self.ranked)
        self.assertEqual(code, 0, err)
        self.assertEqual([r["account"] for r in a["reels"]], ["@top", "@middle", "@bottom"])
        self.assertEqual(a["reels"][0]["outlier"], 41.2)
        self.assertEqual(a["n"], 5)
        self.assertEqual(a["accounts"], 5)
        self.assertEqual(a["ranked_n"], 3)
        self.assertEqual(a["ranked_accounts"], 3)
        self.assertEqual(a["reference_n"], 2)
        self.assertEqual([r["account"] for r in a["references"]], ["@reference", "@unknown"])
        self.assertEqual(a["references"][0]["views_per_follower"], 12000)
        self.assertIsNone(a["references"][1]["views_per_follower"])
        for row in a["references"]:
            self.assertIsNone(row["baseline"])
            self.assertIsNone(row["outlier"])
        for key in ("top_formulas", "top_hook_score", "bottom_hook_score", "top_words",
                    "bottom_words", "unclassified"):
            self.assertEqual(a[key], only_ranked[key], key)

    def test_all_reference_rows_have_no_outlier_analysis(self):
        code, a, err = run_json("ig-viral/swipe.py", stdin=self.header + self.references)
        self.assertEqual(code, 0, err)
        self.assertEqual(a["baseline"], "account median")
        self.assertEqual(a["reels"], [])
        self.assertEqual(a["ranked_n"], 0)
        self.assertEqual(a["reference_n"], 2)
        self.assertEqual(a["top_formulas"], [])
        self.assertEqual(a["unclassified"], 0)
        for key in ("top_hook_score", "bottom_hook_score", "top_words", "bottom_words"):
            self.assertIsNone(a[key])

    def test_zero_views_are_kept_in_ranking_and_references(self):
        ranked = "@zero\t1000\t100\t0\t회의록 정리 방법\n"
        reference = "@reference\t1000\t\t0\t회의록 정리 방법\n"
        code, a, err = run_json("ig-viral/swipe.py", stdin=self.header + ranked + reference)
        self.assertEqual(code, 0, err)
        self.assertEqual(a["n"], 2)
        self.assertEqual(a["reels"][0]["outlier"], 0)
        self.assertEqual(a["references"][0]["views_per_follower"], 0)
        code, a, err = run_json("ig-viral/swipe.py", stdin=self.header + reference)
        self.assertEqual(code, 0, err)
        self.assertEqual(a["reference_n"], 1)

    def test_reference_report_explains_missing_medians_in_both_locales(self):
        for locale, label, ratio, guidance in (
                ("en-US", "REFERENCE ONLY", "views / followers", "Collect recent account medians"),
                ("ko-KR", "참고 목록", "조회수 / 팔로워 수", "최근 조회수 중앙값을 수집")):
            with self.subTest(locale=locale):
                code, out, err = run("ig-viral/swipe.py", ["--locale", locale],
                                     stdin=self.header + self.references)
                self.assertEqual(code, 0, err)
                for text in (label, ratio, guidance, "@reference", "@unknown"):
                    self.assertIn(text, out)
                self.assertNotIn("None", out)

    def test_relative_markdown_output_uses_report_locale_and_reference_section(self):
        for locale, title, label, ratio in (
                ("en-US", "# Swipe file", "REFERENCE ONLY", "views / followers"),
                ("ko-KR", "# 스와이프 파일", "참고 목록", "조회수 / 팔로워 수")):
            with self.subTest(locale=locale), tempfile.TemporaryDirectory() as tmp:
                code, a, err = run_json("ig-viral/swipe.py",
                                        ["--locale", locale, "--out", "swipe.md"],
                                        stdin=self.header + self.ranked + self.references, cwd=tmp)
                self.assertEqual(code, 0, err)
                markdown = pathlib.Path(tmp, "swipe.md").read_text(encoding="utf-8")
                self.assertIn(title, markdown)
                self.assertIn(label, markdown)
                self.assertIn(ratio, markdown)
                self.assertLess(markdown.index("@bottom"), markdown.index(label))
                self.assertGreater(markdown.index("@reference"), markdown.index(label))
                self.assertNotIn("None", markdown)
                self.assertEqual(a["reference_n"], 2)

    def test_reference_only_korean_hooks_select_korean_markdown_without_a_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run("ig-viral/swipe.py", ["--out", "swipe.md"],
                                 stdin="views\thook\n1.2만\t아무도 안 알려주는 이야기\n", cwd=tmp)
            self.assertEqual(code, 0, err)
            markdown = pathlib.Path(tmp, "swipe.md").read_text(encoding="utf-8")
            for content in (out, markdown):
                self.assertIn("스와이프 파일", content)
                self.assertIn("참고 목록", content)
                self.assertIn("최근 조회수 중앙값을 수집", content)
                self.assertIn("계산 불가", content)
                self.assertNotIn("None", content)
            self.assertIn("저장:", err)

    def test_invalid_numeric_rows_are_skipped_with_line_and_field_diagnostics(self):
        invalid = ("@bad_views\t10\t10\t41..2K\thello\n"
                   "@bad_median\t10\t-2\t100\thello\n"
                   "@bad_followers\tNaN\t10\t100\thello\n"
                   "@missing_views\t10\t10\t\thello\n")
        code, a, err = run_json("ig-viral/swipe.py", stdin="# collected today\n" + self.header + invalid + self.ranked)
        self.assertEqual(code, 0, err)
        self.assertEqual(a["n"], 3)
        for line, field in ((3, "views"), (4, "median"), (5, "followers"), (6, "views")):
            self.assertIn(f"line {line}", err)
            self.assertIn(field, err)
        code, out, err = run("ig-viral/swipe.py", stdin=self.header + invalid)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("no usable rows", err)

    def test_invalid_numeric_diagnostic_respects_korean_locale(self):
        code, out, err = run("ig-viral/swipe.py", ["--locale", "ko-KR"],
                             stdin="views\thook\n-10\t잘못된 숫자\n")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("2행 제외", err)
        self.assertIn("views", err)
        self.assertIn("숫자 형식", err)
        self.assertNotIn("no usable rows", err)


if __name__ == "__main__":
    unittest.main()
