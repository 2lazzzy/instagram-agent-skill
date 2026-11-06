#!/usr/bin/env bash
# Real skill invocation through Claude Code, headless. Not part of the unit
# suite: it calls the model (network, usage). It verifies successful Bash
# scoring events and their JSON results, not keywords in the model's prose.
# Run it by hand after changing a SKILL.md.
#
#   bash tests/integration/claude_cli.sh            # writes to a temp dir
#
# It loads the repo as a session-only plugin (--plugin-dir), points the
# profile at an empty temp folder, and lets the model run only python3.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'echo "outputs in $WORK"' EXIT
export IG_CONFIG_DIR="$WORK/cfg"; mkdir -p "$IG_CONFIG_DIR"
unset IG_LOCALE
cd "$WORK"
run() {  # name, locale, prompt
  if ! nice -n 10 claude -p --plugin-dir "$REPO" --model sonnet --no-session-persistence \
    --output-format stream-json --verbose \
    --permission-mode acceptEdits --allowedTools "Bash(python3:*)" "Read" "Write" "Glob" \
    -- "$3" > "$1.out" 2> "$1.err"; then
    echo "FAIL $1: Claude execution failed (see $WORK/$1.err)" >&2
    return 1
  fi
  python3 - "$1.out" "$2" <<'PY'
import json
import math
import re
import sys

path, locale = sys.argv[1:]

def fail(message):
    raise SystemExit(f"FAIL {path}: {message}")

try:
    with open(path, encoding="utf-8") as fh:
        events = [json.loads(line) for line in fh if line.strip()]
except (OSError, ValueError) as exc:
    fail(f"invalid event output: {exc}")
if not events or any(not isinstance(e, dict) for e in events):
    fail("missing structured events")
result = events[-1]
if (result.get("type") != "result" or result.get("subtype") != "success"
        or result.get("is_error") is not False):
    fail("Claude did not finish successfully")

checks = {"LENGTH", "SPECIFICITY", "STAKES", "FRONTLOAD", "ADDRESS"}
calls, scored = set(), set()

def number(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100

for event in events:
    content = event.get("message", {}).get("content", [])
    if not isinstance(content, list):
        continue
    for block in content:
        if not isinstance(block, dict):
            continue
        if event.get("type") == "assistant" and block.get("type") == "tool_use":
            command = block.get("input", {}).get("command", "")
            if (block.get("name") == "Bash" and "hookscore.py" in command
                    and "--json" in command):
                calls.add(block.get("id"))
        if (event.get("type") != "user" or block.get("type") != "tool_result"
                or block.get("tool_use_id") not in calls or block.get("is_error")):
            continue
        output = block.get("content", "")
        if isinstance(output, list):
            output = "\n".join(b.get("text", "") for b in output if b.get("type") == "text")
        structured = event.get("tool_use_result")
        if isinstance(structured, dict) and isinstance(structured.get("stdout"), str):
            output = structured["stdout"]
        if not isinstance(output, str):
            continue
        try:
            # One Bash call may run three --hook invocations, each printing its
            # own JSON object, or one invocation printing an array of hooks.
            rows = []
            decoder = json.JSONDecoder()
            rest = output.strip()
            while rest:
                value, end = decoder.raw_decode(rest)
                rows.extend(value if isinstance(value, list) else [value])
                rest = rest[end:].lstrip()
        except (TypeError, ValueError):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            panel = row.get("checks", {})
            if (row.get("locale") == locale and isinstance(row.get("hook"), str)
                    and row["hook"].strip() and number(row.get("score"))
                    and row.get("verdict") in ("STRONG", "OK", "WEAK")
                    and isinstance(panel, dict) and checks <= panel.keys()
                    and all(isinstance(panel[k], dict) and number(panel[k].get("score"))
                            for k in checks)):
                scored.add(row["hook"])
if len(scored) < 3:
    fail("need three distinct hooks scored by hookscore.py --json in the requested locale")
text = result.get("result", "")
if not isinstance(text, str) or not text.strip():
    fail("missing final response")
if locale == "ko-KR":
    if not re.search("[가-힣]", text) or not re.search("휴리스틱|조회수", text):
        fail("not Korean or missing the heuristic note")
elif re.search("[가-힣]", text):
    fail("Korean leaked into English response")
print(f"PASS {path}: {len(scored)} hooks scored ({locale})")
PY
}
fail=0
run reel_ko ko-KR "/instagram-agent:ig-reel --locale ko-KR 회의록 정리를 Claude로 자동화하는 방법. 훅 후보 3개만 만들어서 hookscore.py --json --locale ko-KR로 실제 점수를 매기고 보여 줘. 대본과 비트 시트는 쓰지 마." || fail=1
run reel_en en-US "/instagram-agent:ig-reel --locale en-US Three hook options for a reel about automating meeting notes with Claude. Run hookscore.py --json --locale en-US on all three hooks and show the ranking. Do not write the script." || fail=1
exit $fail
