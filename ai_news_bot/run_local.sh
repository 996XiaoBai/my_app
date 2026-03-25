#!/bin/bash

set -e

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MONOREPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_ROOT="$MONOREPO_ROOT/ai_news_bot"
RESOLVER_SCRIPT="$MONOREPO_ROOT/ai_news_bot/scripts/resolve_python.sh"
SETUP_VENV_SCRIPT="$MONOREPO_ROOT/ai_news_bot/scripts/setup_venv.sh"

cd "$PROJECT_ROOT"

echo "Checking local virtual environment..."
PY_CMD="$(bash "$SETUP_VENV_SCRIPT" "$PROJECT_ROOT" "$RESOLVER_SCRIPT")"

echo "Using Python: $PY_CMD"

echo "Starting Scheduler..."
echo "Logs will be appended to bot_scheduler.log"
nohup "$PY_CMD" run_scheduler.py >> bot_scheduler.log 2>&1 &

echo "Scheduler is running in background. PID: $!"
echo "Use 'tail -f bot_scheduler.log' to view logs."
