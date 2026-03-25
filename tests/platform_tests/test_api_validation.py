from fastapi.testclient import TestClient

import test_platform.api_server as api_server
from test_platform.services.dify_client import DifyRateLimitError


def test_run_returns_400_for_invalid_params_json():
    client = TestClient(api_server.app)

    response = client.post(
        "/run",
        data={
            "mode": "review",
            "requirement": "登录需求",
            "params": "{bad json}",
        },
    )

    assert response.status_code == 400
    assert "params" in response.json()["detail"]


def test_run_stream_returns_400_for_invalid_roles_json():
    client = TestClient(api_server.app)

    response = client.post(
        "/run/stream",
        data={
            "mode": "review",
            "requirement": "登录需求",
            "roles": "{bad json}",
        },
    )

    assert response.status_code == 400
    assert "roles" in response.json()["detail"]


def test_run_returns_503_for_dify_rate_limit(monkeypatch):
    monkeypatch.setattr(
        api_server.review_service,
        "prepare_context",
        lambda **kwargs: {"context_id": "ctx-rate-limit", "cache_hit": False},
    )
    monkeypatch.setattr(
        api_server.review_service,
        "run_review",
        lambda **kwargs: (_ for _ in ()).throw(DifyRateLimitError("Dify/Azure OpenAI 吞吐受限")),
    )

    client = TestClient(api_server.app)

    response = client.post(
        "/run",
        data={
            "mode": "review",
            "requirement": "登录需求",
        },
    )

    assert response.status_code == 503
    assert "吞吐受限" in response.json()["detail"]
