import requests
import json
from typing import List, Optional

class WeComNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_text(self, content: str, mentioned_mobile_list: List[str] = None) -> bool:
        """
        发送纯文本消息。
        """
        payload = {
            "msgtype": "text",
            "text": {
                "content": content,
                "mentioned_mobile_list": mentioned_mobile_list or []
            }
        }
        return self._send(payload)

    def send_markdown(self, content: str) -> bool:
        """
        发送 Markdown 消息。
        """
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content
            }
        }
        return self._send(payload)

    def send_news(self, title: str, description: str, url: str, picurl: str = "") -> bool:
        """
        发送图文（链接卡片）消息。
        """
        payload = {
            "msgtype": "news",
            "news": {
                "articles": [
                    {
                        "title": title,
                        "description": description,
                        "url": url,
                        "picurl": picurl
                    }
                ]
            }
        }
        return self._send(payload)

    def _send(self, payload: dict) -> bool:
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("errcode") == 0:
                    print("WeCom notification sent successfully.")
                    return True
                else:
                    print(f"WeCom error: {data}")
            else:
                print(f"WeCom HTTP error: {resp.status_code}")
            return False
        except Exception as e:
            print(f"Error sending WeCom notification: {e}")
            return False
