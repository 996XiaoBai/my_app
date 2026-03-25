import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_news_bot.feishu_publisher import FeishuPublisher


@patch("ai_news_bot.feishu_publisher.requests.patch")
def test_set_public_sharing_uses_public_permission_api(mock_patch):
    """验证公开权限修复逻辑构造了正确的飞书请求。"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"code": 0}
    mock_patch.return_value = mock_response

    publisher = FeishuPublisher("app_id", "app_secret")
    publisher._get_tenant_access_token = MagicMock(return_value="tenant-token")

    success = publisher.set_public_sharing("doc_token", is_wiki=False)

    assert success is True
    args, kwargs = mock_patch.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer tenant-token"
    assert kwargs["json"]["external_access"] is True
    assert kwargs["json"]["link_share_entity"] == "anyone_readable"
    assert kwargs["timeout"] == 10
    assert args[0].endswith("/doc_token/public?type=docx")


@patch("ai_news_bot.feishu_publisher.requests.patch")
def test_set_public_sharing_uses_wiki_permission_api(mock_patch):
    """验证知识库场景会切换到 wiki 权限接口。"""
    mock_response = MagicMock()
    mock_response.json.return_value = {"code": 0}
    mock_patch.return_value = mock_response

    publisher = FeishuPublisher("app_id", "app_secret")
    publisher._get_tenant_access_token = MagicMock(return_value="tenant-token")

    success = publisher.set_public_sharing("wiki_token", is_wiki=True)

    assert success is True
    args, _ = mock_patch.call_args
    assert args[0].endswith("/wiki_token/public?type=wiki")
