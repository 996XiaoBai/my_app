#!/bin/bash
# 解析测试平台可用的 Python 解释器，并确保版本不低于 3.11

set -euo pipefail

PROJECT_ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=11

is_supported_python() {
    local candidate="$1"
    "$candidate" - <<'PY'
import sys

sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
}

print_python_version() {
    local candidate="$1"
    "$candidate" - <<'PY'
import sys

print(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
PY
}

append_candidate() {
    local candidate="$1"
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
        CANDIDATES+=("$candidate")
    fi
}

declare -a CANDIDATES=()

append_candidate "${PYTHON_BIN:-}"
append_candidate "${VIRTUAL_ENV:-}/bin/python"
append_candidate "$PROJECT_ROOT/test_platform/.venv/bin/python"
append_candidate "$PROJECT_ROOT/.venv/bin/python"

if command -v python3 >/dev/null 2>&1; then
    append_candidate "$(command -v python3)"
fi

for candidate in "${CANDIDATES[@]}"; do
    if is_supported_python "$candidate"; then
        printf '%s\n' "$candidate"
        exit 0
    fi
done

echo "❌ 未找到满足 Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ 的解释器。" >&2
if [ "${#CANDIDATES[@]}" -gt 0 ]; then
    echo "已检查以下候选解释器：" >&2
    for candidate in "${CANDIDATES[@]}"; do
        version_text="未知"
        if [ -x "$candidate" ]; then
            version_text="$(print_python_version "$candidate" 2>/dev/null || echo 未知)"
        fi
        echo "  - $candidate ($version_text)" >&2
    done
fi
exit 1
