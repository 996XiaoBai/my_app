import json
from unittest.mock import patch

import pytest

from ai_news_bot.services.common.dify_client import DifyClient, DifyRateLimitError


class FakeStreamResponse:
    def __init__(self, status_code=200, events=None, text=""):
        self.status_code = status_code
        self._events = events or []
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"status={self.status_code}")

    def iter_lines(self):
        for payload in self._events:
            yield f"data: {json.dumps(payload, ensure_ascii=False)}".encode("utf-8")


@patch("ai_news_bot.services.common.dify_client.time.sleep", return_value=None)
@patch("ai_news_bot.services.common.dify_client.requests.post")
def test_ai_news_bot_dify_client_retries_when_stream_hits_throughput_limit(mock_post, mock_sleep):
    mock_post.side_effect = [
        FakeStreamResponse(
            events=[
                {
                    "event": "error",
                    "status": 400,
                    "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
                }
            ]
        ),
        FakeStreamResponse(
            events=[
                {
                    "event": "message",
                    "answer": "重试后摘要成功",
                }
            ]
        ),
    ]

    client = DifyClient("https://dify.cvte.com/v1", "test-key", "test-user")

    result = client.generate_completion("请生成测试摘要")

    assert result == "重试后摘要成功"
    assert mock_post.call_count == 2
    mock_sleep.assert_called()


@patch("ai_news_bot.services.common.dify_client.time.sleep", return_value=None)
@patch("ai_news_bot.services.common.dify_client.requests.post")
def test_ai_news_bot_dify_client_raises_rate_limit_error_after_retry_exhausted(mock_post, _mock_sleep):
    mock_post.side_effect = [
        FakeStreamResponse(
            events=[
                {
                    "event": "error",
                    "status": 400,
                    "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
                }
            ]
        ),
        FakeStreamResponse(
            events=[
                {
                    "event": "error",
                    "status": 400,
                    "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
                }
            ]
        ),
        FakeStreamResponse(
            events=[
                {
                    "event": "error",
                    "status": 400,
                    "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
                }
            ]
        ),
    ]

    client = DifyClient("https://dify.cvte.com/v1", "test-key", "test-user")

    with pytest.raises(DifyRateLimitError, match="throughput limit"):
        client.generate_completion("请生成测试摘要")
