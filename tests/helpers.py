"""Shared helpers: run a skill script the way a user would, in isolation."""

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
FIX_EN = os.path.join(ROOT, "tests", "fixtures", "en")
FIX_KO = os.path.join(ROOT, "tests", "fixtures", "ko")

sys.path.insert(0, os.path.join(SKILLS, "ig-i18n"))
sys.path.insert(0, os.path.join(SKILLS, "ig-reel"))
sys.path.insert(0, os.path.join(SKILLS, "ig-human"))
sys.path.insert(0, os.path.join(SKILLS, "ig-caption"))
sys.path.insert(0, os.path.join(SKILLS, "ig-viral"))


class IsolatedConfig:
    """A throwaway ~/.claude/instagram, so no test ever reads the real one."""

    def __init__(self, config=None, voice=None):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name
        if config is not None:
            with open(os.path.join(self.path, "config.json"), "w", encoding="utf-8") as fh:
                json.dump(config, fh, ensure_ascii=False)
        if voice is not None:
            with open(os.path.join(self.path, "voice.md"), "w", encoding="utf-8") as fh:
                fh.write(voice)

    def __enter__(self):
        self._old = {k: os.environ.get(k) for k in ("IG_CONFIG_DIR", "IG_LOCALE")}
        os.environ["IG_CONFIG_DIR"] = self.path
        os.environ.pop("IG_LOCALE", None)
        return self

    def __exit__(self, *exc):
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()


def run(script, args=(), stdin=None, env_extra=None, config_dir=None, cwd=None):
    """Run skills/<script> with args. Returns (code, stdout, stderr)."""
    env = dict(os.environ)
    env.pop("IG_LOCALE", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    own_tmp = None
    if config_dir is None:
        own_tmp = tempfile.TemporaryDirectory()
        config_dir = own_tmp.name
    env["IG_CONFIG_DIR"] = config_dir
    env.update(env_extra or {})
    path = script if os.path.isabs(script) else os.path.join(SKILLS, script)
    try:
        proc = subprocess.run([sys.executable, path] + list(args), input=stdin,
                              capture_output=True, text=True, encoding="utf-8",
                              env=env, cwd=cwd or ROOT)
    finally:
        if own_tmp:
            own_tmp.cleanup()
    return proc.returncode, proc.stdout, proc.stderr


def run_json(script, args=(), **kw):
    code, out, err = run(script, list(args) + ["--json"], **kw)
    if not out.strip():
        raise AssertionError(f"no JSON from {script}: exit {code}\n{err}")
    return code, json.loads(out), err


def fx(name, lang="ko"):
    return os.path.join(FIX_KO if lang == "ko" else FIX_EN, name)
