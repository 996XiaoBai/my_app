import os
import requests
import logging
from typing import List

try:
    from ai_news_fetcher import NewsItem
except ImportError:
    from .ai_news_fetcher import NewsItem

logger = logging.getLogger(__name__)

class WeComBotNotifier:
    """企业微信群机器人 Webhook 通知器"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def _truncate_text(self, text: str, max_length: int = 100) -> str:
        if not text:
            return ""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    def notify_feishu_doc(self, title: str, doc_url: str, news_items: List[NewsItem]):
        """发送包含飞书文档链接的图文导航 Markdown 到群里"""
        if not self.webhook_url:
            logger.info("WECOM_BOT_WEBHOOK_URL is not configured, skipping WeCom notification.")
            return False

        if not news_items:
            logger.warning("No news items provided to WeComBotNotifier, skipping notification.")
            return False

        # 构建 Markdown 内容
        md_lines = [
            f"📢 **{title} 已发布**\n",
            "> 本期精选内容:\n"
        ]

        # 选取所有新闻标题进行列举
        for i, item in enumerate(news_items):
            # 仅保留序号和标题，移除 [来源] 和 摘要，标题转为超链接跳转原文
            md_lines.append(f"> {i+1}. [{item.title}]({item.link})")

        md_lines.append(f"🔗 [点击这里阅读完整图文日报]({doc_url})")

        markdown_content = "\n".join(md_lines)

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": markdown_content
            }
        }

        try:
            logger.info("Sending notification to WeCom Bot...")
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            resp_data = resp.json()
            if resp_data.get("errcode") == 0:
                logger.info("✅ WeCom notification sent successfully.")
                return True
            else:
                logger.error(f"❌ Failed to send WeCom notification: {resp_data}")
                return False
        except Exception as e:
            logger.error(f"❌ Error sending WeCom notification: {e}")
            return False
