import asyncio
import sys
import time
from email.utils import formatdate
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_news_bot.ai_news_fetcher import AINewsFetcher
from ai_news_bot.wechat_oa_publisher import WeChatOAPublisher
from ai_news_bot.wecom_notifier import WeComNotifier


class _MockResponse:
    def __init__(self, text: str, status: int):
        self._text = text
        self.status = status

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def test_fetcher_async():
    """验证历史单测在包导入模式下仍能跑通异步抓取。"""

    async def run_test():
        with patch("ai_news_bot.ai_news_fetcher.feedparser.parse") as mock_parse, patch(
            "ai_news_bot.ai_news_fetcher.aiohttp.ClientSession.get"
        ) as mock_get:
            mock_entry = MagicMock()
            payload = {
                "title": "AI Test News",
                "link": "http://example.com/ai-test",
                "published": formatdate(time.time(), localtime=False, usegmt=True),
                "summary": "This is a summary about Artificial Intelligence",
                "media_content": [],
                "content": [],
            }
            mock_entry.get.side_effect = lambda key, default=None: payload.get(key, default)
            mock_entry.title = payload["title"]
            mock_entry.link = payload["link"]
            mock_entry.published = payload["published"]
            mock_entry.summary = payload["summary"]
            mock_entry.media_content = payload["media_content"]
            mock_entry.content = payload["content"]

            mock_feed = MagicMock()
            mock_feed.entries = [mock_entry]
            mock_parse.return_value = mock_feed
            mock_get.return_value = _MockResponse("xml content", 200)

            fetcher = AINewsFetcher()
            fetcher.sources = [{"name": "Test", "url": "http://test", "type": "rss"}]

            items = await fetcher.fetch_all_async()

            assert len(items) == 1
            assert items[0].title == "AI Test News"

    asyncio.run(run_test())


@patch("ai_news_bot.wechat_oa_publisher.requests.get")
def test_wechat_token(mock_get):
    """验证微信公众号 token 拉取逻辑。"""
    publisher = WeChatOAPublisher("appid", "secret")

    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "token123", "expires_in": 7200}
    mock_get.return_value = mock_response

    token = publisher._get_access_token()

    assert token == "token123"


@patch("ai_news_bot.wecom_notifier.requests.post")
def test_wecom_send(mock_post):
    """验证企业微信通知发送逻辑。"""
    notifier = WeComNotifier("http://webhook")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errcode": 0}
    mock_post.return_value = mock_response

    success = notifier.send_text("Hello")

    assert success is True
