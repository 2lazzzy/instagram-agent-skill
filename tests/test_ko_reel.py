"""ig-reel in Korean: hook scoring, formula classification, beat timing."""

import json
import os
import unittest

from helpers import IsolatedConfig, SKILLS, fx, run, run_json
import hookscore
import swipe

HOOKS_EN = os.path.join(SKILLS, "ig-reel", "hooks.json")
HOOKS_KO = os.path.join(SKILLS, "ig-reel", "locales", "ko-KR", "hooks.json")


def score(text):
    results, overall, verdict, flags = hookscore.run(text, "ko-KR")
    return {k: v[0] for k, v in results.items()}, overall, verdict, flags


def read_tsv(name):
    rows = []
    with open(fx(name), encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                i, hook = line.rstrip("\n").split("\t")
                rows.append((int(i), hook))
    return rows


class HookFile(unittest.TestCase):
    def test_same_formulas_as_english(self):
        en = json.load(open(HOOKS_EN, encoding="utf-8"))
        ko = json.load(open(HOOKS_KO, encoding="utf-8"))
        self.assertEqual([h["id"] for h in en["hooks"]], [h["id"] for h in ko["hooks"]])
        self.assertEqual(en["classify_order"], ko["classify_order"])
        for e, k in zip(en["hooks"], ko["hooks"]):
            self.assertEqual(e["name"], k["name_en"])
            for field in ("name", "template", "example", "on_screen", "best_for", "trap",
                          "adaptation", "match"):
                self.assertTrue(k.get(field), f"#{k['id']} missing {field}")

    def test_korean_examples_do_not_invent_or_use_dots(self):
        ko = json.load(open(HOOKS_KO, encoding="utf-8"))
        for h in ko["hooks"]:
            for field in ("template", "example", "on_screen"):
                self.assertNotIn("·", h[field])
                self.assertNotIn("—", h[field])
            self.assertNotIn("써 보니", h["example"])


class Classify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = swipe.load_formulas(HOOKS_KO)

    def test_every_formula_on_the_tuning_set(self):
        rows = read_tsv("hooks_classify.tsv")
        self.assertEqual({i for i, _ in rows}, set(range(1, 27)))
        for i, hook in rows:
            self.assertEqual(swipe.classify(hook, self.f)[0], i, hook)

    def test_held_out_set(self):
        """Written after tuning. Measured, so the bar is a floor, not 100%."""
        rows = read_tsv("hooks_heldout.tsv")
        got = [(i, swipe.classify(h, self.f)[0]) for i, h in rows]
        right = sum(1 for i, g in got if g == i)
        wrong = sum(1 for i, g in got if g is not None and g != i)
        self.assertGreaterEqual(right / len(rows), 0.75)
        self.assertLessEqual(wrong, 2)

    def test_abstains_on_plain_sentences(self):
        for text in ("요즘 AI가 다양한 분야에서 활용되고 있습니다.", "오늘은 날씨가 좋네요",
                     "회의 끝나고 정리하는 습관"):
            self.assertIsNone(swipe.classify(text, self.f)[0], text)

    def test_english_classifier_untouched_by_korean(self):
        en = swipe.load_formulas(HOOKS_EN)
        self.assertEqual(swipe.classify("Nobody tells you that your first 30 reels flop", en)[0], 3)
        self.assertIsNone(swipe.classify("아무도 안 알려주는데", en)[0])


class HookScore(unittest.TestCase):
    def test_english_frontload_recognizes_names_after_the_first_word(self):
        _, result, _ = run_json("ig-reel/hookscore.py", [
            "--hook", "Use Notion to organize your daily notes", "--locale", "en-US"])
        self.assertEqual(result["checks"]["FRONTLOAD"]["score"], 100)
        self.assertEqual(result["score"], 55.4)
        self.assertEqual(result["verdict"], "OK")
        late = hookscore.check_frontload("Organize all the notes you take each day with Notion")
        self.assertEqual(late[0], 40)
        self.assertEqual(hookscore.check_frontload("Organize all the notes you take")[0], 30)
        self.assertEqual(hookscore.check_frontload("Use notion to organize your notes")[0], 30)

    def test_greeting_and_preamble_are_dealbreakers(self):
        _, overall, verdict, flags = score("안녕하세요 여러분! 오늘은 업무 자동화에 대해 알아보겠습니다.")
        self.assertEqual(verdict, "WEAK")
        self.assertEqual(len(flags), 2)
        self.assertLess(overall, 20)

    def test_stop_scroll_emoji_hype(self):
        _, _, verdict, flags = score("스크롤 멈추세요! 이거 모르면 손해입니다 🔥")
        self.assertEqual(verdict, "WEAK")
        self.assertEqual(len(flags), 3)

    def test_hashtag_in_hook(self):
        self.assertTrue(score("회의록 정리 5분이면 끝 #업무자동화")[3])

    def test_hype_does_not_fire_on_plain_verbs(self):
        self.assertEqual(score("이 설정이 속도에 영향을 미쳤습니다")[3], [])

    def test_strong_hook(self):
        checks, overall, verdict, flags = score("엑셀 수식 외우지 마세요. 단축키 세 가지면 됩니다.")
        self.assertEqual(verdict, "STRONG")
        self.assertEqual(flags, [])
        self.assertEqual(checks["SPECIFICITY"], 100.0)    # 엑셀, 세 가지: two markers
        self.assertEqual(checks["ADDRESS"], 90.0)         # ~세요

    def test_korean_numbers_count_as_specific(self):
        for text in ("삼십 분이면 끝납니다", "하루 30분이면 끝납니다", "단축키 세 가지",
                     "월 9,900원짜리 도구", "Notion으로 끝냅니다"):
            self.assertGreater(score(text)[0]["SPECIFICITY"], 15, text)
        self.assertEqual(score("이걸로 일이 훨씬 편해집니다")[0]["SPECIFICITY"], 15)

    def test_stakes_match_conjugated_stems(self):
        for text in ("백업 안 해서 다 잃었습니다", "계약서 하나로 돈을 날렸어요", "그 습관이 제일 큰 실수였습니다"):
            self.assertGreaterEqual(score(text)[0]["STAKES"], 70, text)

    def test_frontload_ignores_verb_final_negation(self):
        early = score("세 가지 단축키만 외우지 마세요")[0]["FRONTLOAD"]
        late = score("정말 여러 가지 이유로 이런저런 고민 끝에 결국 세 가지만 남겼습니다")[0]["FRONTLOAD"]
        self.assertGreater(early, late)

    def test_address(self):
        self.assertEqual(score("아직도 회의록 손으로 쓰세요?")[0]["ADDRESS"], 100.0)
        self.assertEqual(score("이 설정부터 바꾸세요.")[0]["ADDRESS"], 90.0)
        self.assertEqual(score("제가 매일 쓰는 단축키입니다")[0]["ADDRESS"], 70.0)
        self.assertEqual(score("단축키는 생산성을 높입니다")[0]["ADDRESS"], 35.0)

    def test_length_in_syllables(self):
        short = score("5분")[0]["LENGTH"]
        ok = score("회의록 정리, 이제 5분이면 끝납니다")[0]["LENGTH"]
        long = score("회의가 끝나고 나서 녹음 파일을 올리고 결정 사항과 담당자와 마감일을 정리해서 공유하는 데까지 걸리는 시간")[0]["LENGTH"]
        self.assertEqual(ok, 100.0)
        self.assertLess(short, ok)
        self.assertLess(long, ok)

    def test_cli_ranking_is_korean_and_honest(self):
        code, out, _ = run("ig-reel/hookscore.py", [fx("hooks_ko.txt"), "--locale", "ko-KR"])
        self.assertIn("훅 순위", out)
        self.assertIn("바이럴 확률이 아님", out)
        self.assertNotIn("dealbreaker", out)
        self.assertNotIn("weakest", out)

    def test_json_keys_match_english(self):
        _, en, _ = run_json("ig-reel/hookscore.py", ["--hook", "Stop posting daily."])
        _, ko, _ = run_json("ig-reel/hookscore.py", ["--hook", "매일 올리지 마세요.", "--locale", "ko"])
        self.assertEqual(set(en), set(ko))
        self.assertEqual(set(en["checks"]), set(ko["checks"]))


class Beats(unittest.TestCase):
    def test_native_counter_digits_keep_the_spoken_hook_warning(self):
        for script in ("5개 6개 7개 8개 9개", "다섯 개 여섯 개 일곱 개 여덟 개 아홉 개"):
            with self.subTest(script=script):
                _, a, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR"], stdin=script)
                self.assertEqual(a["total_syllables"], 15)
                self.assertEqual(a["total_seconds"], 3.03)
                self.assertTrue(any("3초" in f for f in a["beats"][0]["flags"]))

    def test_native_count_with_particle_keeps_the_spoken_hook_warning(self):
        for script in ("5명으로 시작해도 정말 충분해요", "다섯 명으로 시작해도 정말 충분해요"):
            with self.subTest(script=script):
                _, a, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR"], stdin=script)
                self.assertEqual(a["total_syllables"], 15)
                self.assertEqual(a["total_seconds"], 3.03)
                self.assertTrue(any("3초" in f for f in a["beats"][0]["flags"]))

    def test_expression_tildes_do_not_create_a_hook_warning(self):
        _, a, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR"],
                           stdin="안녕하세요~ 만나서 정말 반가워요~")
        self.assertEqual(a["total_syllables"], 14)
        self.assertEqual(a["total_seconds"], 2.85)
        self.assertFalse(any("3초" in f for f in a["beats"][0]["flags"]))

    def test_range_symbol_contributes_to_spoken_duration(self):
        _, a, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR"], stdin="3~5분")
        self.assertEqual(a["total_syllables"], 5)  # 삼에서 오분
        self.assertEqual(a["total_seconds"], 1.21)

    def test_timing_uses_syllables_and_pauses(self):
        _, a, _ = run_json("ig-reel/beats.py", [fx("script_ko.txt"), "--locale", "ko-KR"])
        self.assertEqual(a["locale"], "ko-KR")
        self.assertTrue(a["estimate"])
        self.assertEqual(a["spm"], 330)
        first = a["beats"][0]
        self.assertEqual(first["label"], "HOOK")
        expected = first["syllables"] / 5.5 + first["pause"]
        self.assertAlmostEqual(first["dur"], round(expected, 2), places=2)

    def test_numbers_take_longer_than_their_digits(self):
        _, a, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR"], stdin="2026년 3,500,000원\n")
        self.assertEqual(a["total_syllables"], 1 + 5 + 5 + 1)   # 이천이십육 년, 삼백오십만 원

    def test_pause_scale_zero(self):
        _, a, _ = run_json("ig-reel/beats.py", [fx("script_ko.txt"), "--locale", "ko-KR",
                                                "--pause-scale", "0"])
        _, b, _ = run_json("ig-reel/beats.py", [fx("script_ko.txt"), "--locale", "ko-KR"])
        self.assertEqual(a["total_pause_seconds"], 0)
        self.assertLess(a["total_seconds"], b["total_seconds"])

    def test_long_hook_and_long_beat_flagged(self):
        _, a, _ = run_json("ig-reel/beats.py", [fx("script_ko.txt"), "--locale", "ko-KR"])
        self.assertTrue(any("3초" in f for f in a["beats"][0]["flags"]))
        self.assertTrue(any("4초를 넘습니다" in n for n in a["notes"]))

    def test_loop_found_through_particles(self):
        _, a, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR"],
                           stdin="회의록 정리에 걸리던 1시간.\n중간 설명입니다.\n이제 회의록은 5분이면 됩니다.\n")
        self.assertTrue(any(n.startswith("루프:") and "회의록" in n for n in a["notes"]))

    def test_subtitle_reading_speed(self):
        script = "녹음 파일을 올리고 결정된 것과 담당자와 마감일만 표로 뽑아 달라고 하면 됩니다\n"
        _, slow, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR", "--cps", "4"], stdin=script)
        _, normal, _ = run_json("ig-reel/beats.py", ["-", "--locale", "ko-KR"], stdin=script)
        self.assertTrue(slow["beats"][0]["subtitle"]["too_fast"])
        self.assertFalse(normal["beats"][0]["subtitle"]["too_fast"])

    def test_target_note_in_syllables(self):
        _, a, _ = run_json("ig-reel/beats.py", [fx("script_ko.txt"), "--locale", "ko-KR",
                                                "--target", "60"])
        self.assertTrue(any("음절을 더하거나" in n for n in a["notes"]))

    def test_calibration_round_trip(self):
        with IsolatedConfig() as cfg:
            code, out, _ = run("ig-reel/beats.py", [fx("script_ko.txt"), "--locale", "ko-KR",
                                                    "--calibrate", "30", "--save"],
                               config_dir=cfg.path)
            self.assertEqual(code, 0)
            saved = json.load(open(os.path.join(cfg.path, "config.json"), encoding="utf-8"))
            self.assertIn("ko-KR", saved["speech"])
            _, a, _ = run_json("ig-reel/beats.py", [fx("script_ko.txt"), "--locale", "ko-KR"],
                               config_dir=cfg.path)
        self.assertEqual(a["rate_source"], "config.json")
        self.assertAlmostEqual(a["total_seconds"], 30, delta=0.3)
        self.assertFalse(any("기본값이지 실측이 아닙니다" in n for n in a["notes"]))

    def test_spm_flag_beats_config(self):
        with IsolatedConfig(config={"speech": {"ko-KR": {"spm": 200}}}) as cfg:
            _, a, _ = run_json("ig-reel/beats.py", [fx("script_ko.txt"), "--locale", "ko-KR",
                                                    "--spm", "400"], config_dir=cfg.path)
        self.assertEqual(a["spm"], 400)

    def test_english_default_rate_unchanged(self):
        _, a, _ = run_json("ig-reel/beats.py", [fx("script.txt", "en")])
        self.assertEqual(a["wpm"], 165)


if __name__ == "__main__":
    unittest.main()
