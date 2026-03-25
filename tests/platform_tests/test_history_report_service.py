import datetime
import json
from pathlib import Path

from test_platform.core.services.history_report_service import HistoryReportService, PERSISTED_HISTORY_MODES
import test_platform.utils.history_manager as history_manager_module


def test_history_report_service_builds_review_markdown(tmp_path):
    service = HistoryReportService(base_dir=str(tmp_path))

    payload = json.dumps(
        {
            "reports": {
                "test": {
                    "label": "测试视角",
                    "content": (
                        "## 灵魂追问\n\n"
                        "- 请确认登录失败文案。\n"
                        "<findings_json>[{\"category\":\"逻辑缺陷\",\"risk_level\":\"H\","
                        "\"description\":\"失败口径缺失\",\"suggestion\":\"统一定义\"}]</findings_json>\n"
                    ),
                }
            },
            "findings": [
                {
                    "category": "逻辑缺陷",
                    "risk_level": "H",
                    "description": "失败重试口径缺失",
                    "source_quote": "需求中仅描述“失败后可重试”，未说明次数和提示。",
                    "suggestion": "补充失败重试与提示规则",
                }
            ],
        },
        ensure_ascii=False,
    )

    content = service.build_history_content("review", payload)

    assert content.startswith("# 智能需求评审报告")
    assert "## 测试视角" in content
    assert "失败重试口径缺失" in content
    assert "1. [H] 逻辑缺陷：失败重试口径缺失" in content
    assert "原文：需求中仅描述“失败后可重试”，未说明次数和提示。" in content
    assert "<findings_json>" not in content


def test_history_report_service_builds_test_case_markdown(tmp_path):
    service = HistoryReportService(base_dir=str(tmp_path))

    payload = json.dumps(
        {
            "items": [
                {
                    "id": "case-1",
                    "priority": "P1",
                    "module": "登录",
                    "title": "登录成功",
                    "precondition": "账号可用",
                    "steps": [
                        {"action": "输入账号", "expected": ""},
                        {"action": "点击登录", "expected": "进入首页"},
                    ],
                }
            ],
            "summary": "覆盖登录主流程",
        },
        ensure_ascii=False,
    )

    content = service.build_history_content("test_case", payload)

    assert content.startswith("# 智能测试用例")
    assert "> 覆盖登录主流程" in content
    assert "### case：登录成功" in content
    assert "- 前置条件：账号可用" in content
    assert "  1. 步骤：输入账号" in content
    assert "     - 预期结果：进入首页" in content


def test_history_report_service_builds_test_case_review_markdown(tmp_path):
    service = HistoryReportService(base_dir=str(tmp_path))

    payload = json.dumps(
        {
            "summary": "已评审 2 条测试用例，识别 1 项问题。",
            "findings": [
                {
                    "risk_level": "H",
                    "category": "需求偏离",
                    "related_case_ids": ["case-login-2"],
                    "related_requirement_points": ["连续失败 5 次锁定 30 分钟"],
                    "description": "未覆盖锁定恢复规则。",
                    "suggestion": "补充锁定中登录与锁定恢复场景。",
                }
            ],
            "reviewed_cases": [
                {
                    "case_id": "case-login-1",
                    "title": "账号密码登录成功",
                    "module": "登录",
                    "verdict": "pass",
                    "consistency": "aligned",
                    "issues": [],
                    "suggestions": [],
                }
            ],
            "revised_suite": {
                "items": [
                    {
                        "id": "case-login-2",
                        "priority": "P0",
                        "module": "登录",
                        "title": "连续失败 5 次后锁定账号",
                        "steps": [
                            {"action": "连续 5 次输入错误密码", "expected": "第 5 次失败后账号进入锁定状态"}
                        ],
                    }
                ],
                "summary": "修订建议版测试用例，共 1 条。",
            },
        },
        ensure_ascii=False,
    )

    content = service.build_history_content("test_case_review", payload)

    assert content.startswith("# 测试用例评审报告")
    assert "连续失败 5 次锁定 30 分钟" in content
    assert "修订建议版测试用例" in content


def test_history_report_service_persists_generic_modes_and_uses_fallback_names(tmp_path):
    service = HistoryReportService(base_dir=str(tmp_path))

    expected_modes = {
        "test_point",
        "impact_analysis",
        "test_plan",
        "test_data",
        "log_diagnosis",
        "api_test_gen",
        "api_perf_test_gen",
        "test_case_review",
    }

    assert expected_modes.issubset(PERSISTED_HISTORY_MODES)

    report_id = service.save_execution_result(
        mode="api_test_gen",
        result="# 接口测试结果\n\n- 已生成接口覆盖清单\n",
        requirement="接口测试需求",
    )

    assert report_id

    report = service.get_report(report_id)

    assert report is not None
    assert report["type"] == "api_test_gen"
    assert report["filename"] == "接口测试需求"
    assert "已生成接口覆盖清单" in report["content"]


def test_history_report_service_prefers_test_data_markdown_when_result_is_json_payload(tmp_path):
    service = HistoryReportService(base_dir=str(tmp_path))

    payload = json.dumps(
        {
            "summary": "已生成测试数据 SQL。",
            "markdown": "# 识别摘要\n\n- 处理摘要：已生成测试数据 SQL。\n",
            "sql_file_content": "-- 识别摘要\n-- 处理摘要：已生成测试数据 SQL。\n",
            "tables": [
                {
                    "name": "xqd_platform_goods",
                    "display_name": "直播商品表",
                    "select_sql": "SELECT 1;",
                    "insert_sql": "INSERT INTO `xqd_platform_goods` VALUES (1);",
                    "update_sql": "UPDATE `xqd_platform_goods` SET `status` = 1 WHERE `id` = 10001;",
                    "delete_sql": "DELETE FROM `xqd_platform_goods` WHERE `id` = 10001;",
                    "columns": [],
                }
            ],
            "scenarios": [],
            "warnings": [],
        },
        ensure_ascii=False,
    )

    content = service.build_history_content("test_data", payload)

    assert content.startswith("# 识别摘要")
    assert '"tables"' not in content
    assert "已生成测试数据 SQL。" in content


def test_history_report_service_prefers_api_test_markdown_when_result_is_json_payload(tmp_path):
    service = HistoryReportService(base_dir=str(tmp_path))

    payload = json.dumps(
        {
            "summary": "已生成接口测试资产。",
            "markdown": "# 接口测试资产\n\n## 用例清单\n- platformGoods_add_success\n",
            "spec": {"title": "默认模块"},
            "cases": [{"case_id": "platformGoods_add_success"}],
            "scenes": [{"scene_id": "platformGoods_crud_flow"}],
        },
        ensure_ascii=False,
    )

    content = service.build_history_content("api_test_gen", payload)

    assert content.startswith("# 接口测试资产")
    assert '"cases"' not in content
    assert "platformGoods_add_success" in content


def test_history_report_service_persists_api_test_replay_payload_in_meta(tmp_path):
    service = HistoryReportService(base_dir=str(tmp_path))

    report_id = service.save_execution_result(
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
        requirement="平台带货接口回归",
    )

    detail = service.get_report(report_id)

    assert detail is not None
    pack_payload = detail["meta"]["pack_payload"]
    assert pack_payload["spec"]["title"] == "默认模块"
    assert pack_payload["cases"][0]["case_id"] == "platformGoods_add_success"
    assert pack_payload["script"].startswith("import pytest")


def test_history_report_service_keeps_api_test_extended_payload_fields(tmp_path):
    service = HistoryReportService(base_dir=str(tmp_path))

    report_id = service.save_execution_result(
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
                "scenes": [],
                "script": "import pytest\n",
                "link_plan": {"ordered_case_ids": ["platformGoods_add_success"]},
                "suite": {"suite_id": "api_suite_default", "suite_version": 1},
                "report": {"status": "passed", "headline": "默认模块：执行通过"},
            },
            ensure_ascii=False,
        ),
        requirement="平台带货接口回归",
    )

    detail = service.get_report(report_id)

    assert detail is not None
    pack_payload = detail["meta"]["pack_payload"]
    assert pack_payload["link_plan"]["ordered_case_ids"] == ["platformGoods_add_success"]
    assert pack_payload["suite"]["suite_id"] == "api_suite_default"
    assert pack_payload["report"]["status"] == "passed"


def test_history_manager_uses_project_root_history_dir():
    expected_dir = Path(__file__).resolve().parents[2] / "history"

    assert Path(history_manager_module.HISTORY_DIR) == expected_dir


def test_history_manager_generates_unique_ids_even_when_timestamp_matches(tmp_path, monkeypatch):
    fixed_now = datetime.datetime(2026, 3, 19, 10, 30, 0, 123456)

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is None else tz.fromutc(fixed_now.replace(tzinfo=tz))

    monkeypatch.setattr(history_manager_module.datetime, "datetime", FixedDateTime)
    manager = history_manager_module.HistoryManager(base_dir=str(tmp_path))

    first_path = manager.save_report("内容 A", "same.md", "review")
    second_path = manager.save_report("内容 B", "same.md", "review")

    assert first_path
    assert second_path
    assert first_path != second_path
    assert len(list(Path(tmp_path).glob("*.json"))) == 2
