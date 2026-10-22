"""ig-human in Korean: detection and correction are separate, plain Korean is
not treated as AI writing, and the score moves when the flags are fixed."""

import json
import unittest

from helpers import IsolatedConfig, fx, run, run_json


def humanize(text, **kw):
    _, d, _ = run_json("ig-human/humanize.py", ["-", "--locale", "ko-KR"], stdin=text, **kw)
    return d["text"], d["report"]


def detect(path, **kw):
    _, d, _ = run_json("ig-human/detect.py", [path, "--locale", "ko-KR"], **kw)
    return d


class Correction(unittest.TestCase):
    def test_double_passive_fixed(self):
        out, rep = humanize("업무가 자동으로 처리되어집니다. 결과가 보여집니다.")
        self.assertEqual(out.strip(), "업무가 자동으로 처리됩니다. 결과가 보입니다.")
        self.assertEqual(len(rep["lexical"]), 2)

    def test_invisible_and_quotes_fixed(self):
        out, rep = humanize("회의록​ 정리 “프롬프트” …")
        self.assertEqual(out.strip(), '회의록 정리 "프롬프트" ...')
        self.assertTrue(rep["invisible"])
        self.assertTrue(rep["typographic"])

    def test_flagged_phrases_are_never_rewritten(self):
        text = "혁신적인 게임 체인저입니다. 검색·추천·요약을 한 번에 — 결론적으로 강력합니다."
        out, rep = humanize(text)
        self.assertEqual(out.strip(), text)               # not a single character changed
        found = {s["find"] for s in rep["suggestions"]}
        self.assertTrue({"혁신적인", "게임 체인저", "결론적으로"} <= found)
        ids = {s["id"] for s in rep["structures"]}
        self.assertIn("middle-dot", ids)
        self.assertIn("dash", ids)

    def test_suggestions_point_at_lines(self):
        _, rep = humanize("첫 줄은 평범합니다.\n둘째 줄은 획기적인 변화입니다.")
        hit = [s for s in rep["suggestions"] if s["find"] == "획기적인"][0]
        self.assertEqual(hit["lines"], [2])
        self.assertTrue(hit["suggest"])

    def test_urls_untouched(self):
        out, _ = humanize("자세한 건 https://example.com/되어진다 참고. 처리되어진다.")
        self.assertIn("https://example.com/되어진다", out)
        self.assertIn("처리된다.", out)

    def test_allowlist(self):
        with IsolatedConfig(config={"humanize_allow": ["강력한"]}) as cfg:
            _, rep = humanize("강력한 기능입니다.", config_dir=cfg.path)
        self.assertEqual(rep["suggestions"], [])


class NotEverythingIsAI(unittest.TestCase):
    """Plain Korean must not be flagged just for being Korean."""

    def test_natural_casual_and_formal_are_clean(self):
        for name in ("draft_human.txt", "draft_formal_human.txt"):
            text = open(fx(name), encoding="utf-8").read()
            _, rep = humanize(text)
            self.assertEqual(rep["suggestions"], [], name)
            self.assertEqual(rep["structures"], [], name)
            self.assertNotEqual(detect(fx(name))["verdict"], "FLAGGED", name)

    def test_formal_register_is_not_a_tell(self):
        d = detect(fx("draft_formal_human.txt"))
        self.assertEqual(d["verdict"], "PASS")
        self.assertGreaterEqual(d["checks"]["VOICE"]["score"], 70)

    def test_single_connector_is_fine(self):
        _, rep = humanize("회의록은 녹음으로 남깁니다. 또한 담당자 이름을 먼저 부릅니다. 표는 노션에 붙입니다.")
        self.assertEqual(rep["structures"], [])

    def test_repetition_is_what_trips_it(self):
        text = ("이 기능은 업무를 줄일 수 있습니다. 또한 회의를 정리할 수 있습니다. "
                "또한 일정을 관리할 수 있습니다. 또한 보고서를 만들 수 있습니다. 또한 팀을 도울 수 있습니다.")
        _, rep = humanize(text)
        ids = {s["id"] for s in rep["structures"]}
        self.assertTrue({"can-do", "connectors", "same-ending"} <= ids, ids)

    def test_normal_uses_of_listed_words(self):
        # '이상으로' (beyond), '통해' and '가능' in their ordinary senses
        _, rep = humanize("기대 이상으로 빨랐습니다. 이메일을 통해 받았습니다. 주차가 가능합니다.")
        self.assertEqual(rep["suggestions"], [])


class Detection(unittest.TestCase):
    def test_slop_is_flagged(self):
        d = detect(fx("draft_slop.txt"))
        self.assertEqual(d["verdict"], "FLAGGED")
        self.assertEqual(d["checks"]["SLOP DENSITY"]["score"], 0.0)

    def test_rewrite_moves_the_score(self):
        _, both, _ = run_json("ig-human/detect.py", [fx("draft_slop.txt"),
                                                     fx("draft_slop_rewritten.txt"), "--locale", "ko-KR"])
        before, after = both
        self.assertGreaterEqual(after["human_score"] - before["human_score"], 30)
        self.assertNotEqual(after["verdict"], "FLAGGED")

    def test_humanize_alone_does_not_pretend(self):
        """Korean humanize only fixes the safe things, so the score barely
        moves until a person rewrites the flagged lines. That is the design."""
        clean, _ = humanize(open(fx("draft_slop.txt"), encoding="utf-8").read())
        _, d, _ = run_json("ig-human/detect.py", ["-", "--locale", "ko-KR"], stdin=clean)
        self.assertEqual(d["verdict"], "FLAGGED")

    def test_fingerprint_counts_dot_and_dash(self):
        _, d, _ = run_json("ig-human/detect.py", ["-", "--locale", "ko-KR"],
                           stdin="검색·추천·요약 — 한 번에 됩니다.")
        self.assertLess(d["checks"]["FINGERPRINT"]["score"], 50)

    def test_report_is_korean(self):
        code, _, err = run("ig-human/humanize.py", [fx("draft_slop.txt"), "--locale", "ko-KR",
                                                     "--report"])
        self.assertIn("다듬기 보고서", err)
        self.assertIn("자동 수정 안 함", err)
        self.assertNotIn("SLOP LEXICON", err)

    def test_lexicon_is_well_formed(self):
        lex = json.load(open(fx("../../../skills/ig-human/locales/ko-KR/slop.json"), encoding="utf-8"))
        for entry in lex["auto"]:
            self.assertTrue(entry["replace"])
        for entry in lex["terms"]:
            self.assertNotIn("replace", entry)        # terms are never auto-replaced
            self.assertTrue(entry["suggest"])


class AddedAfterComparison(unittest.TestCase):
    """2026-10-22 comparison report: hype and translationese the first lexicon missed, and repeated urging."""

    def test_new_terms_are_flagged_not_rewritten(self):
        text = "역대급 변화입니다. 무조건 써야 합니다. 자동화함으로써 시간이 줄어듭니다. 이는 매우 중요한 포인트입니다. 모르면 손해입니다."
        out, rep = humanize(text)
        found = {s["find"] for s in rep["suggestions"]}
        self.assertTrue({"역대급", "무조건", "함으로써", "이는 매우 중요한", "모르면 손해"} <= found, found)
        self.assertEqual(out.strip(), text)

    def test_urging_repeated(self):
        _, rep = humanize("지금 바로 시작해 보세요! 지금 바로 저장하세요! 지금 바로 공유하세요!")
        self.assertIn("push-repeat", {s["id"] for s in rep["structures"]})

    def test_ordinary_uses_stay_clean(self):
        _, rep = humanize("무조건 반사처럼 손이 갔습니다. 지금 바로 옆자리에 앉아 있어요. 연습함 덕분에 익숙해졌습니다.")
        found = {s["find"] for s in rep["suggestions"]}
        self.assertFalse(found & {"무조건", "함으로써"}, found)
        self.assertNotIn("push-repeat", {s["id"] for s in rep["structures"]})


if __name__ == "__main__":
    unittest.main()
