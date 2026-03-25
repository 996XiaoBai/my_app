#!/bin/bash
# 初始化 AI 资讯机器人的独立虚拟环境，并返回环境内 Python 路径

set -euo pipefail

PROJECT_ROOT="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
RESOLVER_SCRIPT="${2:-$PROJECT_ROOT/scripts/resolve_python.sh}"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
VENV_DIR="$(dirname "$(dirname "$VENV_PYTHON")")"

is_supported_python() {
    local candidate="$1"
    "$candidate" - <<'PY'
import sys

sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY
}

if [ -x "$VENV_PYTHON" ]; then
    if ! is_supported_python "$VENV_PYTHON"; then
        echo "❌ 已存在的 ai_news_bot/.venv Python 版本低于 3.10，请删除后重建。" >&2
        exit 1
    fi
else
    BASE_PYTHON="$(bash "$RESOLVER_SCRIPT" "$PROJECT_ROOT")"
    echo "正在使用 $BASE_PYTHON 创建 ai_news_bot/.venv ..." >&2
    "$BASE_PYTHON" -m venv "$VENV_DIR"
fi

echo "正在同步 ai_news_bot 依赖 ..." >&2
"$VENV_PYTHON" -m pip install --upgrade pip 1>&2
"$VENV_PYTHON" -m pip install -r "$PROJECT_ROOT/requirements.txt" 1>&2

printf '%s\n' "$VENV_PYTHON"
