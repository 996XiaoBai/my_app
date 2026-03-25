import json
from unittest.mock import call, patch

import pytest

from test_platform.services.dify_client import DifyClient, DifyRateLimitError, DifyRequestError


class FakeStreamResponse:
    def __init__(self, status_code=200, events=None, text=""):
        self.status_code = status_code
        self._events = events or []
        self.text = text

    def iter_lines(self):
        for payload in self._events:
            yield f"data: {json.dumps(payload, ensure_ascii=False)}".encode("utf-8")


@patch("test_platform.services.dify_client.time.sleep", return_value=None)
@patch("test_platform.services.dify_client.requests.post")
def test_generate_completion_uses_configured_cooldown_for_rate_limit_errors(mock_post, mock_sleep, monkeypatch):
    monkeypatch.setenv("DIFY_RATE_LIMIT_MAX_RETRIES", "5")
    monkeypatch.setenv("DIFY_RATE_LIMIT_BASE_DELAY_SECONDS", "2")
    monkeypatch.setenv("DIFY_RATE_LIMIT_MAX_DELAY_SECONDS", "30")
    monkeypatch.setenv("DIFY_RATE_LIMIT_COOLDOWN_SECONDS", "20")
    mock_post.side_effect = [
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "message",
                "answer": "冷却后成功",
            }
        ]),
    ]

    client = DifyClient("https://dify.cvte.com/v1", "test-key", "test-user")

    result = client.generate_completion("请生成测试用例")

    assert result == "冷却后成功"
    assert mock_post.call_count == 5
    assert mock_sleep.call_args_list == [call(20), call(20), call(20), call(20)]


@patch("test_platform.services.dify_client.time.sleep", return_value=None)
@patch("test_platform.services.dify_client.requests.post")
def test_generate_completion_uses_configured_exponential_backoff_for_gateway_errors(mock_post, mock_sleep, monkeypatch):
    monkeypatch.setenv("DIFY_RATE_LIMIT_MAX_RETRIES", "4")
    monkeypatch.setenv("DIFY_RATE_LIMIT_BASE_DELAY_SECONDS", "3")
    monkeypatch.setenv("DIFY_RATE_LIMIT_MAX_DELAY_SECONDS", "7")
    monkeypatch.setenv("DIFY_RATE_LIMIT_COOLDOWN_SECONDS", "20")
    mock_post.side_effect = [
        FakeStreamResponse(
            status_code=502,
            text="<html><head><title>502 Bad Gateway</title></head><body><center><h1>502 Bad Gateway</h1></center><hr><center>openresty</center></body></html>",
        ),
        FakeStreamResponse(
            status_code=502,
            text="<html><head><title>502 Bad Gateway</title></head><body><center><h1>502 Bad Gateway</h1></center><hr><center>openresty</center></body></html>",
        ),
        FakeStreamResponse(events=[
            {
                "event": "message",
                "answer": "重试后成功",
            }
        ]),
    ]

    client = DifyClient("https://dify.cvte.com/v1", "test-key", "test-user")

    result = client.generate_completion("请生成接口测试脚本")

    assert result == "重试后成功"
    assert mock_post.call_count == 3
    assert mock_sleep.call_args_list == [call(3), call(6)]


@patch("test_platform.services.dify_client.time.sleep", return_value=None)
@patch("test_platform.services.dify_client.requests.post")
def test_generate_completion_retries_when_stream_hits_throughput_limit(mock_post, _mock_sleep):
    mock_post.side_effect = [
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "message",
                "answer": "最终生成结果",
            }
        ]),
    ]

    client = DifyClient("https://dify.cvte.com/v1", "test-key", "test-user")

    result = client.generate_completion("请生成测试用例")

    assert result == "最终生成结果"
    assert mock_post.call_count == 2


@patch("test_platform.services.dify_client.requests.post")
def test_generate_completion_raises_when_upload_file_id_is_invalid(mock_post):
    mock_post.return_value = FakeStreamResponse(
        status_code=400,
        text='{"code":"invalid_param","message":"Invalid file at index 0: Invalid upload file id format","status":400}',
    )

    client = DifyClient("https://dify.cvte.com/v1", "test-key", "test-user")

    with pytest.raises(DifyRequestError, match="Invalid upload file id format"):
        client.generate_completion(
            "请生成测试用例",
            files=[{"type": "image", "transfer_method": "local_file", "upload_file_id": "mock_id_1"}],
        )


@patch("test_platform.services.dify_client.time.sleep", return_value=None)
@patch("test_platform.services.dify_client.requests.post")
def test_generate_completion_retries_when_gateway_returns_502(mock_post, _mock_sleep):
    mock_post.side_effect = [
        FakeStreamResponse(
            status_code=502,
            text="<html><head><title>502 Bad Gateway</title></head><body><center><h1>502 Bad Gateway</h1></center><hr><center>openresty</center></body></html>",
        ),
        FakeStreamResponse(events=[
            {
                "event": "message",
                "answer": "重试后成功",
            }
        ]),
    ]

    client = DifyClient("https://dify.cvte.com/v1", "test-key", "test-user")

    result = client.generate_completion("请生成接口测试脚本")

    assert result == "重试后成功"
    assert mock_post.call_count == 2


@patch("test_platform.services.dify_client.time.sleep", return_value=None)
@patch("test_platform.services.dify_client.requests.post")
def test_generate_completion_raises_rate_limit_error_after_retry_exhausted(mock_post, _mock_sleep):
    mock_post.side_effect = [
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
        FakeStreamResponse(events=[
            {
                "event": "error",
                "status": 400,
                "message": "Requests have exceeded the throughput limit on your Provisioned-Managed deployment.",
            }
        ]),
    ]

    client = DifyClient("https://dify.cvte.com/v1", "test-key", "test-user")

    with pytest.raises(DifyRateLimitError, match="throughput limit"):
        client.generate_completion("请生成测试用例")
