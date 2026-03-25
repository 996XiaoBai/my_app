import json

from fastapi.testclient import TestClient

import test_platform.api_server as api_server
from test_platform.core.services.history_report_service import HistoryReportService


class StubWeeklyReportService:
    def __init__(self):
        self.summary_calls = []
        self.export_calls = []

    def summarize_report(self, wecom_text, image_paths):
        self.summary_calls.append({
            "wecom_text": wecom_text,
            "image_paths": image_paths,
        })
        return "# 测试周报\n\n## 工作概览\n\n- 已完成需求评审与测试用例生成。\n"

    def export_to_feishu(self, title, summary_md):
        self.export_calls.append({
            "title": title,
            "summary_md": summary_md,
        })
        return "https://feishu.example.com/docx/weekly"


def test_run_stream_handles_weekly_report_mode_and_persists_history(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    stub_service = StubWeeklyReportService()

    monkeypatch.setattr(api_server, "history_report_service", history_service)
    monkeypatch.setattr(api_server, "weekly_report_service", stub_service)

    client = TestClient(api_server.app)

    response = client.post(
        "/run/stream",
        data={
            "mode": "weekly-report",
            "requirement": "本周完成登录链路优化",
            "extra_prompt": "突出稳定性专项",
            "params": json.dumps({"publish_to_feishu": True}),
        },
    )

    assert response.status_code == 200

    events = [json.loads(line) for line in response.text.strip().splitlines()]
    assert events[-1]["type"] == "result"
    assert events[-1]["result"].startswith("# 测试周报")
    assert events[-1]["meta"]["feishu_url"] == "https://feishu.example.com/docx/weekly"
    assert events[-1]["meta"]["published_to_feishu"] is True

    assert len(stub_service.summary_calls) == 1
    assert "突出稳定性专项" in stub_service.summary_calls[0]["wecom_text"]
    assert stub_service.summary_calls[0]["image_paths"] == []

    assert len(stub_service.export_calls) == 1
    assert "软件测试周报" in stub_service.export_calls[0]["title"]

    history_items = client.get("/api/history/reports", params={"types": "weekly-report"}).json()["items"]
    assert len(history_items) == 1
    assert history_items[0]["type"] == "weekly_report"


def test_run_stream_weekly_report_can_skip_feishu_publish(tmp_path, monkeypatch):
    history_service = HistoryReportService(base_dir=str(tmp_path))
    stub_service = StubWeeklyReportService()

    monkeypatch.setattr(api_server, "history_report_service", history_service)
    monkeypatch.setattr(api_server, "weekly_report_service", stub_service)

    client = TestClient(api_server.app)

    response = client.post(
        "/run/stream",
        data={
            "mode": "weekly-report",
            "requirement": "本周完成搜索优化",
            "params": json.dumps({"publish_to_feishu": False}),
        },
    )

    assert response.status_code == 200

    events = [json.loads(line) for line in response.text.strip().splitlines()]
    assert events[-1]["type"] == "result"
    assert events[-1]["meta"]["published_to_feishu"] is False
    assert events[-1]["meta"]["feishu_url"] is None
    assert stub_service.export_calls == []
