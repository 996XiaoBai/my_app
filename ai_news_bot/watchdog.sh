#!/bin/bash

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查进程是否存在
if ! pgrep -f "run_scheduler.py" > /dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [Watchdog] 发现 Scheduler 未运行，正在启动..." >> watchdog.log
    # 调用现有的启动脚本
    ./run_local.sh
fi
