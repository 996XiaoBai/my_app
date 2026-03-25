import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_FEISHU_RESEARCH_TESTS") != "1",
    reason="研究类飞书集成测试默认跳过；如需真实验证请显式设置 RUN_LIVE_FEISHU_RESEARCH_TESTS=1",
)


def test_fetch_blocks_live():
    """保留为显式开启的真实飞书研究验证脚本。"""
    import requests
    from dotenv import load_dotenv

    load_dotenv()
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")

    auth_res = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )

    assert auth_res.status_code == 200
    assert auth_res.json().get("tenant_access_token")
