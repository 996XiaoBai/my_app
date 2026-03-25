#!/bin/bash
# 测试平台 Streamlit 启动脚本
# 优先使用当前虚拟环境或项目 `.venv`，避免硬编码解释器路径

set -e

PROJECT_ROOT=$(cd "$(dirname "$0")" && pwd)
STREAMLIT_PORT="${TEST_PLATFORM_STREAMLIT_PORT:-8501}"
RESOLVED_PYTHON_BIN="$(bash "$PROJECT_ROOT/test_platform/scripts/resolve_python.sh" "$PROJECT_ROOT")"

export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "🚀 Starting Interest Island Review Agent..."
echo "🐍 使用解释器: $RESOLVED_PYTHON_BIN"
echo "🌐 Streamlit 端口: $STREAMLIT_PORT"

exec "$RESOLVED_PYTHON_BIN" -m streamlit run "$PROJECT_ROOT/test_platform/app.py" --server.port "$STREAMLIT_PORT"
