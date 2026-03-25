#!/bin/bash

# 获取当前脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查 .env 是否存在
if [ ! -f .env ]; then
    echo "Warning: .env file not found in $SCRIPT_DIR"
fi

echo "🐞 Starting TV Bug Report Generator..."
echo "Press Ctrl+C to stop."

# 运行 Streamlit 应用
# 确保 test_platform 目录在 Python 路径中
export PYTHONPATH=$PYTHONPATH:$SCRIPT_DIR

if command -v streamlit >/dev/null 2>&1; then
    streamlit run test_platform/tools/bug_report_ui.py
else
    echo "Streamlit not found. Attempting to run via python module..."
    python3 -m streamlit run test_platform/tools/bug_report_ui.py
fi
