import json

from test_platform.core.services.review_result_service import ReviewResultService


def test_review_result_service_strips_internal_findings_block():
    service = ReviewResultService()

    reports = {
        "test": {
            "label": "测试视角",
            "content": (
                "## 灵魂追问\n"
                "\n"
                "- 请确认话题数量口径。\n"
                "<findings_json>[{\"category\":\"逻辑缺陷\",\"risk_level\":\"H\","
                "\"description\":\"口径不一致\",\"suggestion\":\"统一定义\"}]</findings_json>\n"
            ),
        }
    }

    payload = json.loads(service.serialize(reports, []))

    assert "<findings_json>" not in payload["reports"]["test"]["content"]
    assert "口径不一致" not in payload["reports"]["test"]["content"]
    assert "请确认话题数量口径" in payload["reports"]["test"]["content"]


def test_review_result_service_generates_markdown_payload():
    service = ReviewResultService()

    reports = {
        "test": {
            "label": "测试视角",
            "content": "## 灵魂追问\n\n- 请确认话题数量口径。\n",
        },
        "architect": {
            "label": "资深架构师(仲裁)",
            "content": "## 仲裁结论\n\n统一按 200 个口径输出。\n",
        },
    }
    findings = [
        {
            "category": "逻辑缺陷",
            "risk_level": "H",
            "description": "话题数量定义冲突",
            "source_quote": "需求写明“每次最多选择 200 个话题”。",
            "suggestion": "统一产品口径并补充边界说明",
        }
    ]

    payload = json.loads(service.serialize(reports, findings))

    assert payload["markdown"].startswith("# 智能需求评审报告")
    assert "## 测试视角" in payload["markdown"]
    assert "## 资深架构师(仲裁)" in payload["markdown"]
    assert "## 风险看板" in payload["markdown"]
    assert payload["findings"][0]["source_quote"] == "需求写明“每次最多选择 200 个话题”。"
    assert "1. [H] 逻辑缺陷：话题数量定义冲突" in payload["markdown"]
    assert "原文：需求写明“每次最多选择 200 个话题”。" in payload["markdown"]
    assert "建议：统一产品口径并补充边界说明" in payload["markdown"]


def test_review_result_service_fills_missing_source_quote_with_empty_string():
    service = ReviewResultService()

    payload = json.loads(service.serialize(
        {
            "test": {
                "label": "测试视角",
                "content": "## 灵魂追问\n\n- 请确认登录失败文案。\n",
            }
        },
        [
            {
                "category": "逻辑缺陷",
                "risk_level": "H",
                "description": "登录失败提示文案不清晰",
                "suggestion": "补充失败原因与下一步引导",
            }
        ],
    ))

    assert payload["findings"][0]["source_quote"] == ""
