#!/bin/bash

# 获取项目根目录
PROJECT_ROOT=$(cd "$(dirname "$0")" && pwd)
PYTHON_BIN="$(bash "$PROJECT_ROOT/test_platform/scripts/resolve_python.sh" "$PROJECT_ROOT")"

echo "------------------------------------------------"
echo "🚀 正在一键启动测试平台 (专家版)..."
echo "------------------------------------------------"
echo "🐍 使用解释器: $PYTHON_BIN"

# 0. 自动清理冲突端口 (防止 Address already in use)
echo "🧹 正在检查并清理残留进程..."
lsof -t -i:8000 | xargs kill -9 2>/dev/null
lsof -t -i:3000 | xargs kill -9 2>/dev/null

# 1. 启动后端 API
echo "🔌 [1/2] 正在启动后端服务 (Port 8000)..."
export PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON_BIN" -m test_platform.api_server > api_server.log 2>&1 &
BACKEND_PID=$!

cleanup() {
   if [ -n "${BACKEND_PID:-}" ] && ps -p "$BACKEND_PID" > /dev/null 2>&1
   then
      echo "🛑 正在关闭后端服务 (PID: $BACKEND_PID)..."
      kill "$BACKEND_PID" 2>/dev/null
   fi
}

# 提前注册退出清理，确保前端开发服务中断时后端也能回收
trap cleanup EXIT INT TERM

# 等待后端启动并确认健康检查通过
BACKEND_READY=0
for _ in $(seq 1 10)
do
   if curl -fsS http://localhost:8000/health > /dev/null 2>&1
   then
      BACKEND_READY=1
      break
   fi
   sleep 1
done

if [ "$BACKEND_READY" -eq 1 ]
then
   echo "✅ 后端启动成功 (PID: $BACKEND_PID)"
   echo "📝 后端日志存储在: $PROJECT_ROOT/api_server.log"
else
   echo "❌ 后端启动失败，请检查 api_server.log"
   tail -n 40 api_server.log 2>/dev/null
   exit 1
fi

# 2. 启动前端 Web
echo "🌐 [2/2] 正在启动前端服务 (Port 3000)..."
cd "$PROJECT_ROOT/test_platform/web"

# 自动在默认浏览器中打开页面
sleep 1
open http://localhost:3000

# 启动开发服务器
npm run dev
