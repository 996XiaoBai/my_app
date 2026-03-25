import logging
import requests
import os
from typing import Dict, Any

from publishers.base import PublisherBase
from dotenv import load_dotenv

load_dotenv()

WECOM_WEBHOOK_URL = os.getenv("WECOM_BOT_WEBHOOK_URL", "")

logger = logging.getLogger(__name__)

class WeComPublisher(PublisherBase):
    """
    企业微信机器人发布渠道。
    向指定的 Webhook 发送 Markdown 消息。
    """
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or WECOM_WEBHOOK_URL

    def publish(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        向企微群发送 Markdown 消息。可以通过 kwargs 传入 doc_id 和 doc_url。
        """
        doc_id = kwargs.get('doc_id')
        doc_url = kwargs.get('doc_url')
        
        # 构建消息卡片内容
        message_lines = [f"📢 **{title}**\n"]
        if doc_url:
            message_lines.append(f"> [点击阅读完整图文日报]({doc_url})\n")
        
        # 简单截断主体内容作为概览
        lines = content.split('\n')
        # 取前 15 行或更少作为企微群预览
        preview_lines = []
        for line in lines:
            if '# ' in line:  # 跳过大标题
                continue
            preview_lines.append(line.strip())
            if len(preview_lines) > 20:
                break
                
        message_lines.append('\n'.join(preview_lines))
        if len(lines) > 20:
             message_lines.append("...\n*(内容过多已截断，请点击链接查看全文)*")
        
        final_content = "\n".join(message_lines)
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": final_content
            }
        }
        
        if not self.webhook_url:
            logger.warning("WeCom Webhook URL is not configured. Skipping notification.")
            return {"success": False, "error": "Webhook not configured"}
            
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("✅ WeCom notification sent successfully.")
            return {"success": True, "ext_data": response.json()}
        except Exception as e:
            logger.error(f"Failed to send WeCom notification: {e}")
            return {"success": False, "error": str(e)}
