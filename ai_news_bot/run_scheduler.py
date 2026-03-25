import os
import sys
import yaml
import logging
import asyncio
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

try:
    from main_news_bot import NewsBot
    from run_qa_bot import QABot
except ImportError:
    from .main_news_bot import NewsBot
    from .run_qa_bot import QABot

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Scheduler")

def load_config(path="config/news_config.yaml"):
    if not os.path.exists(path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(current_dir, "config", "news_config.yaml")
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

async def run_qa_job():
    logger.info("--- 启动 QA/研效 专项机器人任务 ---")
    try:
        bot = QABot()
        await bot.run()
    except Exception as e:
        logger.error(f"执行 QABot 失败: {e}")

async def run_news_job():
    logger.info("--- 启动 AI 资讯机器人任务 ---")
    try:
        bot = NewsBot()
        await bot.run()
    except Exception as e:
        logger.error(f"执行 NewsBot 失败: {e}")

def qa_job():
    logger.info("====================================")
    logger.info(f"[APScheduler] Starting QA job at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    asyncio.run(run_qa_job())
    logger.info("====================================")

def news_job():
    logger.info("====================================")
    logger.info(f"[APScheduler] Starting AI News job at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    asyncio.run(run_news_job())
    logger.info("====================================")

def main():
    config = load_config()
    scheduler_config = config.get("scheduler", {})
    
    if not scheduler_config.get("enabled", False):
        logger.warning("Scheduler is disabled in config.yaml. Exiting.")
        return

    # 建立持久化的阻塞调度器，明确指定亚洲/上海时区
    tz = pytz.timezone('Asia/Shanghai')
    scheduler = BlockingScheduler(timezone=tz)
    
    # 按照用户明确要求设定：09:00 测试日报，09:10 AI 日报
    scheduler.add_job(qa_job, CronTrigger(hour=9, minute=0, timezone=tz), id='qa_daily_0900')
    scheduler.add_job(news_job, CronTrigger(hour=9, minute=10, timezone=tz), id='news_daily_0910')
    
    logger.info(f"成功注册系统定时任务:")
    logger.info(f"  - 09:00: 测试日报 (QABot)")
    logger.info(f"  - 09:10: AI 日报 (NewsBot)")

    # 手动触发支持
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        logger.info("Flag --now detected, trigger immediate execution for both...")
        qa_job()
        news_job()
        logger.info("Flag --now 执行完毕，本次不进入常驻调度。")
        return
        
    logger.info("APScheduler 守护进程正在运行... 按 Ctrl+C 可以退出。")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("收到退出信号，APScheduler 防护进程准备停止。")

if __name__ == "__main__":
    main()
