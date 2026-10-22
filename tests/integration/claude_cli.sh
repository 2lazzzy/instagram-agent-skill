#!/usr/bin/env bash
# Real skill invocation through Claude Code, headless. Not part of the unit
# suite: it calls the model (network, usage) and its output is free text, so
# the checks are loose. Run it by hand after changing a SKILL.md.
#
#   bash tests/integration/claude_cli.sh            # writes to a temp dir
#
# It loads the repo as a session-only plugin (--plugin-dir), points the
# profile at an empty temp folder, and lets the model run only python3.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
export IG_CONFIG_DIR="$WORK/cfg"; mkdir -p "$IG_CONFIG_DIR"
cd "$WORK"
run() {  # name, prompt
  nice -n 10 claude -p --plugin-dir "$REPO" --model sonnet --no-session-persistence \
    --permission-mode acceptEdits --allowedTools "Bash(python3:*)" "Read" "Write" "Glob" \
    -- "$2" > "$1.out" 2> "$1.err" || true
}
run reel_ko "/instagram-agent:ig-reel --locale ko-KR 회의록 정리를 Claude로 자동화하는 방법. 훅 후보 3개만 만들어서 hookscore.py로 점수를 매기고 보여 줘. 대본과 비트 시트는 쓰지 마."
run reel_en "/instagram-agent:ig-reel Three hook options for a reel about automating meeting notes with Claude. Score them with hookscore.py and show the ranking. Do not write the script."

fail=0
grep -q "[가-힣]" reel_ko.out && grep -Eq "휴리스틱|조회수" reel_ko.out || { echo "FAIL reel_ko: not Korean or no heuristic note"; fail=1; }
grep -q "[가-힣]" reel_en.out && { echo "FAIL reel_en: Korean leaked into English output"; fail=1; }
grep -Eqi "score|hook" reel_en.out || { echo "FAIL reel_en: no ranking"; fail=1; }
echo "outputs in $WORK"
exit $fail
