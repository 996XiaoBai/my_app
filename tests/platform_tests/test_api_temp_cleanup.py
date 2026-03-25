from io import BytesIO

from fastapi.testclient import TestClient

import test_platform.api_server as api_server


def test_run_stream_cleans_request_temp_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(api_server.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(api_server.uuid, "uuid4", lambda: "cleanup-stream")
    monkeypatch.setattr(
        api_server.review_service,
        "prepare_context",
        lambda **kwargs: {"context_id": "ctx-cleanup", "cache_hit": False},
    )
    monkeypatch.setattr(
        api_server.review_service,
        "run_review",
        lambda **kwargs: "# 清理测试\n\n- 已完成",
    )
    monkeypatch.setattr(
        api_server.review_service,
        "generate_dynamic_insight",
        lambda *_args, **_kwargs: None,
    )

    client = TestClient(api_server.app)
    temp_dir = tmp_path / "qa_wb_cleanup-stream"

    response = client.post(
        "/run/stream",
        data={"mode": "review", "requirement": "登录需求"},
        files={"files": ("req.md", BytesIO(b"# login"), "text/markdown")},
    )

    assert response.status_code == 200
    assert not temp_dir.exists()


def test_recommend_experts_cleans_request_temp_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(api_server.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(api_server.uuid, "uuid4", lambda: "cleanup-recommend")
    monkeypatch.setattr(
        api_server.review_service,
        "recommend_experts",
        lambda requirement_text: ["product", "test"],
    )

    client = TestClient(api_server.app)
    temp_dir = tmp_path / "qa_rec_cleanup-recommend"

    response = client.post(
        "/recommend-experts",
        files={"files": ("roles.txt", BytesIO(b"login"), "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["recommended"] == ["product", "test"]
    assert not temp_dir.exists()
