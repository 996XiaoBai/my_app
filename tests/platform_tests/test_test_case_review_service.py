import json
from pathlib import Path

from test_platform.core.data_generators.test_case_exporter import export_to_excel, export_to_xmind
from test_platform.core.services.test_case_review_service import TestCaseReviewService


def _build_export_cases():
    return [
        {
            "name": "账号密码登录成功",
            "module": "登录",
            "precondition": "账号已注册",
            "priority": "P1",
            "steps": [
                {"step": "输入正确账号密码", "expected": "账号密码输入成功"},
                {"step": "点击登录", "expected": "进入首页"},
            ],
        },
        {
            "name": "连续失败 5 次后锁定账号",
            "module": "登录",
            "precondition": "账号已注册",
            "priority": "P0",
            "steps": [
                {"step": "连续 5 次输入错误密码", "expected": "第 5 次失败后账号进入锁定状态"},
            ],
        },
    ]


def test_resolve_case_suite_from_case_result_json():
    service = TestCaseReviewService()

    suite = service.resolve_case_suite(
        params={
            "case_result": json.dumps(
                {
                    "items": [
                        {
                            "id": "case-login-1",
                            "priority": "P1",
                            "module": "登录",
                            "title": "账号密码登录成功",
                            "steps": [
                                {"action": "输入正确账号密码", "expected": "账号密码输入成功"},
                                {"action": "点击登录", "expected": "进入首页"},
                            ],
                        }
                    ],
                    "summary": "覆盖登录主流程",
                },
                ensure_ascii=False,
            )
        },
        uploaded_paths=[],
    )

    assert suite["summary"] == "覆盖登录主流程"
    assert suite["items"][0]["title"] == "账号密码登录成功"


def test_resolve_case_suite_from_excel_file_roundtrip(tmp_path):
    service = TestCaseReviewService()
    excel_path = Path(tmp_path) / "review-cases.xlsx"
    export_to_excel(_build_export_cases(), str(excel_path))

    suite = service.resolve_case_suite(
        params={"case_file_indexes": [0]},
        uploaded_paths=[str(excel_path)],
    )

    assert len(suite["items"]) == 2
    assert suite["items"][0]["module"] == "登录"
    assert any(item["title"] == "连续失败 5 次后锁定账号" for item in suite["items"])


def test_resolve_case_suite_from_xmind_file_roundtrip(tmp_path):
    service = TestCaseReviewService()
    xmind_path = Path(tmp_path) / "review-cases.xmind"
    export_to_xmind(_build_export_cases(), str(xmind_path))

    suite = service.resolve_case_suite(
        params={"case_file_indexes": [0]},
        uploaded_paths=[str(xmind_path)],
    )

    assert len(suite["items"]) == 2
    assert suite["modules"][0]["name"] == "登录"
    assert any(item["priority"] == "P0" for item in suite["items"])


def test_review_cases_falls_back_to_deterministic_payload_when_llm_output_invalid():
    service = TestCaseReviewService()
    suite = service.resolve_case_suite(
        params={
            "case_content": """
# 智能测试用例

## 模块：登录

### case：账号密码登录成功
- 前置条件：账号已注册
- 步骤描述：
  1. 步骤：输入正确账号密码
     - 预期结果：账号密码输入成功
  2. 步骤：点击登录
     - 预期结果：进入首页
"""
        },
        uploaded_paths=[],
    )

    payload = service.review_cases(
        requirement_text="需求：支持账号密码登录。",
        suite=suite,
        reviewer=lambda _prompt: "not-json",
    )

    assert payload["summary"].startswith("已评审 1 条测试用例")
    assert payload["revised_suite"]["items"][0]["title"] == "账号密码登录成功"
    assert payload["markdown"].startswith("# 测试用例评审报告")
