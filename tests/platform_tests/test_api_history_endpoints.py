import json
from pathlib import Path

from fastapi.testclient import TestClient

import test_platform.api_server as api_server
from test_platform.core.services.history_report_service import HistoryReportService


def test_run_stream_persists_review_history_and_exposes_history_api(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    monkeypatch.setattr(api_server, "history_report_service", history_service)
    monkeypatch.setattr(
        api_server.review_service,
        "prepare_context",
        lambda **kwargs: {"context_id": "ctx-review", "cache_hit": False},
    )
    monkeypatch.setattr(
        api_server.review_service,
        "run_review",
        lambda **kwargs: json.dumps(
            {
                "reports": {
                    "test": {
                        "label": "测试视角",
                        "content": "## 灵魂追问\n\n- 请确认失败重试规则。\n",
                    }
                },
                "findings": [],
                "markdown": "# 智能需求评审报告\n\n## 测试视角\n\n- 请确认失败重试规则。\n",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setattr(
        api_server.review_service,
        "generate_dynamic_insight",
        lambda *_args, **_kwargs: "风险已汇总",
    )

    client = TestClient(api_server.app)

    response = client.post(
        "/run/stream",
        data={"mode": "review", "requirement": "登录失败后允许重试"},
    )

    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.strip().splitlines()]
    assert events[-1]["type"] == "result"

    list_response = client.get("/api/history/reports", params={"types": "review"})
    assert list_response.status_code == 200

    reports = list_response.json()["items"]
    assert len(reports) == 1
    assert reports[0]["type"] == "review"

    detail_response = client.get(f"/api/history/reports/{reports[0]['id']}")
    assert detail_response.status_code == 200

    detail = detail_response.json()
    assert detail["type"] == "review"
    assert detail["meta"]["mode"] == "review"
    assert detail["content"].startswith("# 智能需求评审报告")
    assert "请确认失败重试规则" in detail["content"]


def test_history_list_supports_mode_alias_filter(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    monkeypatch.setattr(api_server, "history_report_service", history_service)

    history_service.save_execution_result(
        mode="auto_script_gen",
        result="## UI 自动化结果\n\n- 已生成 Playwright 脚本",
        requirement="登录页自动化",
        source_name="login-prd.md",
        meta={"task_type": "auto-script"},
    )

    client = TestClient(api_server.app)

    response = client.get("/api/history/reports", params={"types": "ui-auto"})

    assert response.status_code == 200
    reports = response.json()["items"]
    assert len(reports) == 1
    assert reports[0]["type"] == "auto_script_gen"


def test_run_persists_review_history_and_returns_sync_payload(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    monkeypatch.setattr(api_server, "history_report_service", history_service)
    monkeypatch.setattr(
        api_server.review_service,
        "prepare_context",
        lambda **kwargs: {"context_id": "ctx-sync", "cache_hit": False},
    )
    monkeypatch.setattr(
        api_server.review_service,
        "run_review",
        lambda **kwargs: json.dumps(
            {
                "reports": {
                    "product": {
                        "label": "产品视角",
                        "content": "## 关注点\n\n- 请补充重试提示口径。\n",
                    }
                },
                "findings": [],
                "markdown": "# 智能需求评审报告\n\n## 产品视角\n\n- 请补充重试提示口径。\n",
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setattr(
        api_server.review_service,
        "generate_dynamic_insight",
        lambda *_args, **_kwargs: "同步洞察已生成",
    )

    client = TestClient(api_server.app)

    response = client.post(
        "/run",
        data={"mode": "review", "requirement": "登录失败后需要重试提示"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["context_id"] == "ctx-sync"
    assert payload["cache_hit"] is False
    assert payload["insight"] == "同步洞察已生成"

    reports = client.get("/api/history/reports", params={"types": "review"}).json()["items"]
    assert len(reports) == 1
    detail = client.get(f"/api/history/reports/{reports[0]['id']}").json()
    assert detail["content"].startswith("# 智能需求评审报告")


def test_history_detail_returns_api_test_replay_pack_payload(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    monkeypatch.setattr(api_server, "history_report_service", history_service)

    history_service.save_execution_result(
        mode="api_test_gen",
        result=json.dumps(
            {
                "summary": "已生成接口测试资产。",
                "markdown": "# 接口测试资产\n",
                "spec": {
                    "title": "默认模块",
                    "servers": [{"url": "https://example.com"}],
                    "auth_profile": {"required_headers": [], "required_cookies": []},
                    "resources": [],
                    "operations": [],
                },
                "cases": [{"case_id": "platformGoods_add_success"}],
                "scenes": [{"scene_id": "platformGoods_crud_flow"}],
                "script": "import pytest\n",
            },
            ensure_ascii=False,
        ),
        requirement="接口测试回归",
    )

    client = TestClient(api_server.app)
    reports = client.get("/api/history/reports", params={"types": "api-test"}).json()["items"]
    detail = client.get(f"/api/history/reports/{reports[0]['id']}").json()

    assert detail["type"] == "api_test_gen"
    assert detail["meta"]["pack_payload"]["spec"]["title"] == "默认模块"
    assert detail["meta"]["pack_payload"]["script"].startswith("import pytest")


def test_history_list_returns_api_test_summary_meta_and_supports_artifact_download(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    monkeypatch.setattr(api_server, "history_report_service", history_service)

    run_dir = Path(tmp_path) / "api_test_runs" / "run-001"
    run_dir.mkdir(parents=True, exist_ok=True)
    allure_archive = run_dir / "allure-results.zip"
    allure_archive.write_bytes(b"fake-zip")

    history_service.save_execution_result(
        mode="api_test_gen",
        result=json.dumps(
            {
                "summary": "已生成接口测试资产。",
                "markdown": "# 接口测试资产\n",
                "spec": {
                    "title": "默认模块",
                    "servers": [{"url": "https://example.com"}],
                    "auth_profile": {"required_headers": [], "required_cookies": []},
                    "resources": [],
                    "operations": [],
                },
                "cases": [{"case_id": "platformGoods_add_success"}],
                "scenes": [{"scene_id": "platformGoods_crud_flow"}],
                "script": "import pytest\n",
                "execution": {
                    "status": "failed",
                    "stats": {"total": 4, "passed": 3, "failed": 1, "errors": 0, "skipped": 0},
                    "artifacts": {
                        "run_dir": str(run_dir),
                        "allure_archive": str(allure_archive),
                    },
                },
                "suite": {
                    "suite_id": "api_suite_default",
                    "suite_version": 2,
                },
                "report": {
                    "headline": "默认模块：执行失败",
                },
            },
            ensure_ascii=False,
        ),
        requirement="接口测试回归",
    )

    client = TestClient(api_server.app)
    reports = client.get("/api/history/reports", params={"types": "api-test"}).json()["items"]

    assert len(reports) == 1
    assert reports[0]["meta"]["api_test_summary"] == {
        "spec_title": "默认模块",
        "suite_id": "api_suite_default",
        "suite_version": 2,
        "status": "failed",
        "case_count": 1,
        "scene_count": 1,
        "report_headline": "默认模块：执行失败",
        "stats": {"total": 4, "passed": 3, "failed": 1, "errors": 0, "skipped": 0},
        "pass_rate": 75.0,
    }

    download_response = client.get(
        f"/api/history/reports/{reports[0]['id']}/artifacts/allure_archive"
    )

    assert download_response.status_code == 200
    assert download_response.content == b"fake-zip"


def test_run_uses_fresh_requirement_when_context_id_and_new_input_are_both_present(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    monkeypatch.setattr(api_server, "history_report_service", history_service)
    monkeypatch.setattr(
        api_server.review_service,
        "get_context",
        lambda context_id: {
            "context_id": context_id,
            "cache_hit": True,
            "context": {
                "combined_text": "旧需求",
                "vision_files_map": {},
                "pages": [],
                "page_texts": {1: "旧需求"},
                "file_basename": "old.md",
                "requirement": "旧需求",
            },
            "modules": [{"name": "旧模块", "pages": [1], "description": "旧模块"}],
        },
    )

    captured = {}

    def fake_prepare_context(**kwargs):
        captured["prepare_requirement"] = kwargs.get("requirement")
        return {
            "context_id": "ctx-new",
            "cache_hit": False,
            "context": {
                "combined_text": "新需求",
                "vision_files_map": {},
                "pages": [],
                "page_texts": {1: "新需求"},
                "file_basename": "new.md",
                "requirement": "新需求",
            },
            "modules": [{"name": "新模块", "pages": [1], "description": "新模块"}],
        }

    monkeypatch.setattr(api_server.review_service, "prepare_context", fake_prepare_context)

    def fake_run_review(**kwargs):
        captured["context_id"] = kwargs.get("context_id")
        captured["prepared_context"] = kwargs.get("preparsed_data")
        return json.dumps(
            {
                "reports": {
                    "test": {
                        "label": "测试视角",
                        "content": "## 关注点\n\n- 新需求生效。\n",
                    }
                },
                "findings": [],
                "markdown": "# 智能需求评审报告\n\n- 新需求生效。\n",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(api_server.review_service, "run_review", fake_run_review)
    monkeypatch.setattr(api_server.review_service, "generate_dynamic_insight", lambda *_args, **_kwargs: None)

    client = TestClient(api_server.app)
    response = client.post(
        "/run",
        data={
            "mode": "review",
            "requirement": "这是新需求",
            "context_id": "ctx-old",
        },
    )

    assert response.status_code == 200
    assert response.json()["context_id"] == "ctx-new"
    assert captured["prepare_requirement"] == "这是新需求"
    assert captured["context_id"] == "ctx-new"
    assert captured["prepared_context"]["context"]["combined_text"] == "新需求"


def test_run_returns_success_false_when_service_reports_error(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    monkeypatch.setattr(api_server, "history_report_service", history_service)
    monkeypatch.setattr(
        api_server.review_service,
        "prepare_context",
        lambda **kwargs: {"context_id": "ctx-error", "cache_hit": False},
    )
    monkeypatch.setattr(
        api_server.review_service,
        "run_review",
        lambda **kwargs: "Error: 测试用例生成失败：未获得有效结果",
    )

    client = TestClient(api_server.app)

    response = client.post(
        "/run",
        data={"mode": "test_case", "requirement": "登录需求"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"] == "测试用例生成失败：未获得有效结果"

    reports = client.get("/api/history/reports", params={"types": "test_case"}).json()["items"]
    assert reports == []
