import os
import sys
import asyncio
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ai_news_fetcher import AINewsFetcher
from main_news_bot import NewsBot

async def run_manual():
    # 强制清理去重记录以便能拉取今天的重复数据
    fetcher = AINewsFetcher()
    
    # 也可以直接改名历史记录文件以免干预明天跑的正常流程
    history_file = fetcher.history_file
    bak_file = history_file + ".bak"
    if os.path.exists(history_file):
        os.rename(history_file, bak_file)
        
    try:
        # 直接使用 NewsBot 正常运行流程
        bot = NewsBot()
        await bot.run(date_label="2026-03-05-手动补发版")
        print("====== 真实数据手动推送执行完毕 ======")
    finally:
        # 恢复去重记录，防止把今天已经看过的旧闻当成新新闻明天又推
        if os.path.exists(bak_file):
            if os.path.exists(history_file):
                os.remove(history_file)  # 删除刚才新生成的、包含今天全部内容的记录
            os.rename(bak_file, history_file)
            print("====== 已恢复历史查重记录以保证明天运行正常 ======")

if __name__ == "__main__":
    asyncio.run(run_manual())
