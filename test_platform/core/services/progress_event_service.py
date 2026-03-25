import json
from typing import Any, Dict


MODE_ALIASES = {
    "req-analysis": "req_analysis",
    "test-point": "test_point",
    "impact": "impact_analysis",
    "test-plan": "test_plan",
    "test-data": "test_data",
    "log-diagnosis": "log_diagnosis",
    "api-test": "api_test_gen",
    "perf-test": "api_perf_test_gen",
    "ui-auto": "auto_script_gen",
    "weekly-report": "weekly_report",
}


def normalize_mode(mode: str) -> str:
    normalized = str(mode or "").replace("-", "_").lower()
    normalized = MODE_ALIASES.get(str(mode or "").lower(), normalized)
    if normalized == "test_cases":
        return "test_case"
    return normalized or "review"


def infer_progress_stage(mode: str, message: str) -> str:
    normalized_mode = normalize_mode(mode)
    text = str(message or "")

    if normalized_mode == "auto_script_gen":
        if "解析需求与上传内容" in text or "解析输入内容" in text:
            return "parsing"
        if "提取页面结构" in text or "交互元素" in text:
            return "extracting"
        if "自动化脚本" in text or "Playwright" in text or "脚本" in text:
            return "generating_script"
        if "整理输出结果" in text or "格式化输出结果" in text or "动态风险洞察" in text:
            return "organizing"
        return "parsing"

    if normalized_mode in {"api_test_gen", "api_perf_test_gen"}:
        if "执行生成的 Pytest 用例" in text or "执行接口测试" in text:
            return "executing"
        if "Pytest 脚本" in text or "Locust 压测脚本" in text or "生成" in text:
            return "generating"
        if "提取接口定义" in text or "参数结构" in text:
            return "extracting"
        if "解析接口描述" in text or "解析接口" in text:
            return "parsing"
        if "整理输出结果" in text or "动态风险洞察" in text:
            return "organizing"
        return "parsing"

    if normalized_mode == "weekly_report":
        if "企业微信讨论" in text or "处理已上传截图" in text or "整理本周输入内容" in text:
            return "collecting"
        if "清洗和总结周报内容" in text or "总结周报" in text:
            return "summarizing"
        if "写入飞书文档" in text:
            return "publishing"
        if "整理周报输出结果" in text:
            return "organizing"
        return "collecting"

    if normalized_mode == "test_case":
        if "解析需求上下文" in text:
            return "context"
        if "关联历史评审风险点" in text:
            return "associating"
        if "模块拆解" in text or "拆解业务功能点" in text:
            return "decomposing"
        if "匹配工程化测试策略" in text or "开始生成测试用例" in text:
            return "matching"
        if "结构化生成" in text or "开始处理" in text or "JSON 结构化" in text:
            return "generating"
        if "汇总测试用例结果" in text or "完成：" in text:
            return "evaluating"
        return "context"

    if normalized_mode == "test_case_review":
        if "解析需求上下文" in text:
            return "context"
        if "解析测试用例内容" in text or "解析测试用例文件" in text:
            return "parsing_cases"
        if "对齐需求与测试用例" in text or "建立需求映射" in text:
            return "aligning"
        if "评审测试用例质量" in text or "评审测试用例" in text:
            return "reviewing"
        if "生成修订建议版测试用例" in text or "修订建议版测试用例" in text:
            return "revising"
        return "context"

    if normalized_mode == "test_data":
        if "解析技术文档内容" in text:
            return "reading"
        if "清洗技术文档噪音" in text:
            return "cleaning"
        if "识别表结构" in text or "字段定义" in text:
            return "extracting"
        if "生成按表 SQL" in text or "场景 SQL" in text:
            return "generating"
        if "动态风险洞察" in text or "整理输出结果" in text:
            return "organizing"
        return "reading"

    if "解析文档并提取上下文" in text:
        return "reading"
    if "并行深度分析" in text:
        return "analyzing"
    if "逻辑冲突识别" in text:
        return "grouping"
    if "仲裁建议生成" in text or "架构仲裁" in text:
        return "conflicting"
    if "风险等级划分与汇总" in text or "动态风险洞察" in text:
        return "grading"
    return "reading"


def build_progress_event(mode: str, message: str, sequence: int) -> Dict[str, Any]:
    return {
        "type": "progress",
        "stage": infer_progress_stage(mode, message),
        "message": str(message or ""),
        "sequence": sequence,
    }


def build_result_event(
    result: str,
    insight: str = None,
    context_id: str = None,
    cache_hit: bool = False,
    meta: Dict[str, Any] = None
) -> Dict[str, Any]:
    return {
        "type": "result",
        "success": True,
        "result": result,
        "insight": insight,
        "context_id": context_id,
        "cache_hit": cache_hit,
        "meta": meta or {},
    }


def build_error_event(message: str) -> Dict[str, Any]:
    return {
        "type": "error",
        "message": str(message or "执行失败"),
    }


def encode_stream_event(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"
