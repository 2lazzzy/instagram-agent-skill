"""English output must match reviewed baselines (see golden_cases.py)."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from golden_cases import CASES, GOLDEN, run_case, strip_locale  # noqa: E402


class EnglishGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._cfg = tempfile.TemporaryDirectory()

    @classmethod
    def tearDownClass(cls):
        cls._cfg.cleanup()

    def _check(self, name, script, argv, is_json):
        with open(os.path.join(GOLDEN, name + ".json"), encoding="utf-8") as fh:
            gold = json.load(fh)
        code, out, err = run_case(script, argv, self._cfg.name)
        self.assertEqual(code, gold["code"], f"{name}: exit code changed")
        if is_json:
            self.assertEqual(strip_locale(json.loads(out)), json.loads(gold["stdout"]),
                             f"{name}: JSON changed")
        else:
            self.assertEqual(out, gold["stdout"], f"{name}: stdout changed")
        self.assertEqual(err, gold["stderr"], f"{name}: stderr changed")


def _make(case):
    def test(self):
        self._check(*case)
    return test


for _case in CASES:
    setattr(EnglishGolden, "test_" + _case[0], _make(_case))


if __name__ == "__main__":
    unittest.main()
