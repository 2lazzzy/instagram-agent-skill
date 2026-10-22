"""The same scenario in English and Korean should be judged the same way.

Each pair below says the same thing in both languages. The Korean panel is not
a translation of the English one, so absolute scores differ; what must hold is
the direction: the same hook wins, the same caption fails for the same reason,
the same draft is flagged, and the same script is about as long.
"""

import unittest

from helpers import fx, run_json

HOOK_PAIRS = [
    # (english, korean) - strong first, then deliberately bad
    ("Stop formatting meeting notes by hand. Three shortcuts do it.",
     "회의록 손으로 정리하지 마세요. 단축키 세 가지면 됩니다."),
    ("Hey guys, today I wanted to talk about productivity",
     "안녕하세요 여러분, 오늘은 생산성에 대해 이야기해 보겠습니다"),
]

CAPTIONS = {
    "too_many_tags": ("Meeting notes in five minutes.\n\n#a #b #c #d #e #f",
                      "회의록 5분 정리법.\n\n#가 #나 #다 #라 #마 #바"),
    "link": ("Template at www.example.com/notes for the steps.",
             "템플릿은 www.example.com/notes 에 있습니다."),
    "two_asks": ("Notes in five minutes.\n\nSave this and follow for more.",
                 "회의록 5분 정리.\n\n저장해 두세요. 팔로우하고 다음 편도 보세요."),
    "clean": ("Meeting notes in 5 minutes with Claude.\n\nComment NOTES and I will send the prompt.",
              "Claude로 회의록 5분 정리.\n\n댓글에 '회의록' 남겨 주세요."),
    # 2026-10-22 comparison report: '남기면' (the most common Korean form) was not read as an ask,
    # so the same caption got WARN in English and PASS in Korean
    "save_and_keyword": ("Notes in five minutes.\n\nSave this for your next meeting\nComment NOTES and I'll send you the prompt",
                         "회의록 5분 정리.\n\n저장해 두고 다음 회의 때 써 보세요\n댓글에 '회의록' 남기면 프롬프트 보내드려요"),
}

SCRIPTS = (
    "Meeting notes used to take an hour.\nRecord the call and upload the file.\n"
    "Ask for decisions, owners and deadlines in a table.\nPaste the table into Notion.\n"
    "Meeting notes, done in five minutes.\n",
    "회의록 정리에 한 시간이 걸렸습니다.\n회의를 녹음하고 파일을 올립니다.\n"
    "결정 사항, 담당자, 마감일을 표로 달라고 합니다.\n그 표를 노션에 붙입니다.\n"
    "회의록 정리, 5분이면 끝납니다.\n",
)


def hook(text, loc):
    _, d, _ = run_json("ig-reel/hookscore.py", ["--hook", text, "--locale", loc])
    return d


def caption(text, loc):
    _, d, _ = run_json("ig-caption/caption.py", ["-", "--locale", loc], stdin=text)
    return d, {c["check"]: c["status"] for c in d["checks"]}


class SameVerdicts(unittest.TestCase):
    def test_hook_ranking_agrees(self):
        for loc, i in (("en-US", 0), ("ko-KR", 1)):
            good = hook(HOOK_PAIRS[0][i], loc)
            bad = hook(HOOK_PAIRS[1][i], loc)
            self.assertGreater(good["score"], bad["score"] + 30, loc)
            self.assertEqual(bad["verdict"], "WEAK", loc)
            self.assertEqual(good["flags"], [], loc)
            self.assertTrue(bad["flags"], loc)

    def test_dealbreaker_kinds_agree(self):
        en = hook("Stop scrolling! In this video I'm going to show you my setup 🔥", "en-US")
        ko = hook("스크롤 멈추세요! 오늘 영상에서는 제 세팅을 보여 드리겠습니다 🔥", "ko-KR")
        self.assertEqual(len(en["flags"]), 3)
        self.assertEqual(len(ko["flags"]), 3)

    def test_caption_checks_agree(self):
        for name, (en_text, ko_text) in CAPTIONS.items():
            en, en_c = caption(en_text, "en-US")
            ko, ko_c = caption(ko_text, "ko-KR")
            for check in ("HASHTAGS", "LINKS", "ONE ASK"):
                self.assertEqual(en_c[check], ko_c[check], f"{name}: {check}")
            self.assertEqual(en["verdict"] == "FIX", ko["verdict"] == "FIX", name)

    def test_script_lengths_are_comparable(self):
        _, en, _ = run_json("ig-reel/beats.py", ["-", "--locale", "en-US"], stdin=SCRIPTS[0])
        _, ko, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR"], stdin=SCRIPTS[1])
        self.assertEqual(len(en["beats"]), len(ko["beats"]))
        ratio = ko["total_seconds"] / en["total_seconds"]
        self.assertTrue(0.7 <= ratio <= 1.4, f"ko/en length ratio {ratio:.2f}")
        self.assertEqual(en["beats"][0]["label"], ko["beats"][0]["label"])

    def test_detector_direction_agrees(self):
        for loc, slop, human in (("en-US", fx("draft_slop.txt", "en"), fx("draft_human.txt", "en")),
                                 ("ko-KR", fx("draft_slop.txt"), fx("draft_human.txt"))):
            _, both, _ = run_json("ig-human/detect.py", [slop, human, "--locale", loc])
            self.assertEqual(both[0]["verdict"], "FLAGGED", loc)
            self.assertGreater(both[1]["human_score"], both[0]["human_score"] + 25, loc)
            self.assertNotEqual(both[1]["verdict"], "FLAGGED", loc)


if __name__ == "__main__":
    unittest.main()
