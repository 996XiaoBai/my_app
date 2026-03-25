#!/usr/bin/env python3
import asyncio
import os
import sys
import argparse
import subprocess
from pathlib import Path

# 将项目根目录添加到 PYTHONPATH
ROOT_DIR = Path(__file__).parent.absolute()
sys.path.append(str(ROOT_DIR))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  Warning: python-dotenv not found, environment variables might not be loaded.")

MIN_PYTHON_VERSION = (3, 11)


def is_supported_python_version(version_info=None):
    """判断当前解释器是否满足测试平台最低 Python 版本要求。"""
    current = version_info or sys.version_info
    return tuple(current[:2]) >= MIN_PYTHON_VERSION


def ensure_supported_python(component: str):
    """在启动测试平台相关入口前校验 Python 版本。"""
    if is_supported_python_version():
        return

    required = ".".join(str(part) for part in MIN_PYTHON_VERSION)
    current = ".".join(str(part) for part in sys.version_info[:3])
    raise RuntimeError(f"{component} 需要 Python {required}+，当前解释器版本为 {current}")

def run_news_bot():
    """启动 AI 资讯机器人全流程"""
    from ai_news_bot.main_news_bot import main
    print("🚀 Starting AI News Bot (Full Flow)...")
    asyncio.run(main())

def run_scheduler():
    """启动 AI 资讯机器人定时调度器"""
    from ai_news_bot.run_scheduler import main
    print("⏰ Starting AI News Bot Scheduler...")
    main()

def run_ui():
    """启动评审代理 Web UI (Streamlit)"""
    ensure_supported_python("测试平台 Streamlit UI")
    print("🌐 Launching Review Agent Web UI...")
    app_path = ROOT_DIR / "test_platform" / "app.py"
    if not app_path.exists():
        # 兼容历史路径
        app_path = ROOT_DIR / "tests" / "app.py"
    
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
    streamlit_port = os.getenv("TEST_PLATFORM_STREAMLIT_PORT", "8501")
    
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", streamlit_port]
    subprocess.run(cmd, env=env)

def main():
    parser = argparse.ArgumentParser(description="Antigravity Project CLI - 一键启动管理工具")
    subparsers = parser.add_subparsers(dest="command", help="Available business commands")

    # news 子命令
    subparsers.add_parser("news", help="Run AI News Bot immediately")
    
    # scheduler 子命令
    subparsers.add_parser("scheduler", help="Start AI News Bot Scheduler")
    
    # ui 子命令
    subparsers.add_parser("ui", help="Start Review Agent Streamlit UI")

    args = parser.parse_args()

    if args.command == "news":
        run_news_bot()
    elif args.command == "scheduler":
        run_scheduler()
    elif args.command == "ui":
        run_ui()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
