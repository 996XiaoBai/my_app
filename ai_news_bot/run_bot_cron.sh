#!/bin/bash

# Cron 环境通常很精简，所以我们需要显式设置。

set -e

MONOREPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AI_NEWS_BOT_DIR="$MONOREPO_ROOT/ai_news_bot"
RESOLVER_SCRIPT="$MONOREPO_ROOT/ai_news_bot/scripts/resolve_python.sh"
PYTHON_BIN="$(bash "$RESOLVER_SCRIPT" "$AI_NEWS_BOT_DIR")"

# 1. 切换到项目目录
cd "$AI_NEWS_BOT_DIR" || exit 1

# 2. 输出当前解释器，便于排查 cron 环境问题
echo "Using Python: $PYTHON_BIN" >> bot_cron.log

# 3. 运行机器人
# 将标准输出和错误重定向到日志文件以进行调试
"$PYTHON_BIN" main_news_bot.py >> bot_cron.log 2>&1

echo "Job finished at $(date)" >> bot_cron.log
