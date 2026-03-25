"""
指定日期时间窗口的日报推送脚本。
用法: python run_dated.py [time_window_hours] [date_label]
示例:
  python run_dated.py 48 "2026-02-22"   # 推送过去 48h 内容，标记为 2/22 日报
  python run_dated.py 26 "2026-02-23"   # 推送最近 26h 内容，标记为 2/23 日报
"""
import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from ai_news_bot.main_news_bot import NewsBot

if __name__ == "__main__":
    time_window = int(sys.argv[1]) if len(sys.argv) > 1 else 26
    date_label = sys.argv[2] if len(sys.argv) > 2 else None

    bot = NewsBot()
    # 覆盖时间窗口
    bot.fetcher.filter_config["time_window_hours"] = time_window

    asyncio.run(bot.run(date_label=date_label))
