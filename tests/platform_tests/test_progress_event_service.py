import json

from test_platform.core.services.progress_event_service import (
    build_progress_event,
    encode_stream_event,
    infer_progress_stage,
    normalize_mode,
)


def test_infer_progress_stage_for_review_flow():
    assert infer_progress_stage("review", "📄 正在解析文档并提取上下文...") == "reading"
    assert infer_progress_stage("review", "🧠 专家角色并行深度分析...") == "analyzing"
    assert infer_progress_stage("review", "⚖️ 视角对碰与逻辑冲突识别...") == "grouping"
    assert infer_progress_stage("review", "🏛️ 架构师最终仲裁建议生成...") == "conflicting"
    assert infer_progress_stage("review", "📌 风险等级划分与汇总...") == "grading"


def test_infer_progress_stage_for_test_case_flow():
    assert infer_progress_stage("test_case", "📄 正在解析需求上下文...") == "context"
    assert infer_progress_stage("test_case", "🔗 已关联历史评审风险点...") == "associating"
    assert infer_progress_stage("test_case", "🧩 已完成需求模块拆解...") == "decomposing"
    assert infer_progress_stage("test_case", "🧠 正在匹配工程化测试策略...") == "matching"
    assert infer_progress_stage("test_case", "  🔄 [登录] 正在执行确定性 JSON 结构化生成...") == "generating"
    assert infer_progress_stage("test_case", "🧪 正在汇总测试用例结果...") == "evaluating"


def test_infer_progress_stage_for_test_case_review_flow():
    assert infer_progress_stage("test_case_review", "📄 正在解析需求上下文...") == "context"
    assert infer_progress_stage("test_case_review", "🧾 正在解析测试用例内容...") == "parsing_cases"
    assert infer_progress_stage("test_case_review", "🔗 正在对齐需求与测试用例...") == "aligning"
    assert infer_progress_stage("test_case_review", "🧠 正在评审测试用例质量与覆盖情况...") == "reviewing"
    assert infer_progress_stage("test_case_review", "🛠️ 正在生成修订建议版测试用例...") == "revising"


def test_normalize_mode_aliases():
    assert normalize_mode("req-analysis") == "req_analysis"
    assert normalize_mode("test-point") == "test_point"
    assert normalize_mode("api-test") == "api_test_gen"
    assert normalize_mode("perf-test") == "api_perf_test_gen"
    assert normalize_mode("ui-auto") == "auto_script_gen"
    assert normalize_mode("weekly-report") == "weekly_report"


def test_infer_progress_stage_for_automation_flows():
    assert infer_progress_stage("ui-auto", "📄 正在解析需求与上传内容...") == "parsing"
    assert infer_progress_stage("ui-auto", "🧩 正在提取页面结构与交互元素...") == "extracting"
    assert infer_progress_stage("ui-auto", "🤖 正在生成 Playwright 脚本...") == "generating_script"
    assert infer_progress_stage("api-test", "📄 正在解析接口描述与上传内容...") == "parsing"
    assert infer_progress_stage("api-test", "🧩 正在提取接口定义与参数结构...") == "extracting"
    assert infer_progress_stage("api-test", "🔌 正在解析接口并生成 Pytest 脚本...") == "generating"
    assert infer_progress_stage("api-test", "🧪 正在执行生成的 Pytest 用例...") == "executing"
    assert infer_progress_stage("perf-test", "🚀 正在解析接口并生成 Locust 压测脚本...") == "generating"
    assert infer_progress_stage("perf-test", "🧾 正在整理输出结果...") == "organizing"
    assert infer_progress_stage("weekly-report", "💬 正在整理企业微信讨论内容...") == "collecting"
    assert infer_progress_stage("weekly-report", "🧠 AI 正在清洗和总结周报内容...") == "summarizing"
    assert infer_progress_stage("weekly-report", "📝 正在写入飞书文档...") == "publishing"


def test_infer_progress_stage_for_test_data_flow():
    assert infer_progress_stage("test-data", "📄 正在解析技术文档内容...") == "reading"
    assert infer_progress_stage("test-data", "🧹 正在清洗技术文档噪音...") == "cleaning"
    assert infer_progress_stage("test-data", "🧩 正在识别表结构与字段定义...") == "extracting"
    assert infer_progress_stage("test-data", "🧠 正在生成按表 SQL 和场景 SQL...") == "generating"


def test_build_and_encode_progress_event():
    payload = build_progress_event("review", "🧠 专家角色并行深度分析...", sequence=3)

    assert payload["type"] == "progress"
    assert payload["stage"] == "analyzing"
    assert payload["message"] == "🧠 专家角色并行深度分析..."
    assert payload["sequence"] == 3

    encoded = encode_stream_event(payload)
    decoded = json.loads(encoded)

    assert decoded["stage"] == "analyzing"
    assert encoded.endswith("\n")
