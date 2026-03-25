"""
功能模式枚举与元数据集中管理模块。

将整个项目中散落的魔法字符串（模式名称、按钮文本、标题等）统一集中到此文件，
任何新增或修改只需改这里一处，前后端自动同步。
"""
from enum import Enum
from typing import Dict, Any


class SkillMode(str, Enum):
    """功能模式枚举，值即为传递给后端的 mode key。"""
    REVIEW          = "review"
    TEST_CASE       = "test_case"
    TEST_CASE_REVIEW = "test_case_review"
    REQ_ANALYSIS    = "req_analysis"
    TEST_POINT      = "test_point"
    LOG_DIAGNOSIS   = "log_diagnosis"
    TEST_DATA       = "test_data"
    IMPACT_ANALYSIS = "impact_analysis"
    TEST_PLAN       = "test_plan"
    FLOWCHART       = "flowchart"
    API_TEST_GEN    = "api_test_gen"
    API_PERF_TEST   = "api_perf_test_gen"
    AUTO_SCRIPT_GEN = "auto_script_gen"
    WEEKLY_REPORT   = "weekly_report"


# 技能名称映射（供 Agent 加载 SKILL.md 时使用）
SKILL_NAME_MAP: Dict[SkillMode, str] = {
    SkillMode.REVIEW:          "requirement_expert_reviewer",
    SkillMode.TEST_CASE:       "test_case_master",
    SkillMode.TEST_CASE_REVIEW:"requirement_expert_reviewer",
    SkillMode.REQ_ANALYSIS:    "requirement_analysis_master",
    SkillMode.TEST_POINT:      "test_point_analysis_master",
    SkillMode.LOG_DIAGNOSIS:   "log_diagnosis_expert",
    SkillMode.TEST_DATA:       "test_data_expert",
    SkillMode.IMPACT_ANALYSIS: "requirement_diff_analyzer",
    SkillMode.TEST_PLAN:       "test_plan_master",
    SkillMode.FLOWCHART:       "flowchart_master",
    SkillMode.API_TEST_GEN:    "api_test_generator",
    SkillMode.API_PERF_TEST:   "api_performance_test_generator",
    SkillMode.AUTO_SCRIPT_GEN: "auto_script_generator",
}

# 前端 UI 显示元数据（供 streamlit_app.py 使用）
MODE_META: Dict[str, Dict[str, Any]] = {
    SkillMode.REVIEW: {
        "label":         "📝 需求评审",
        "caption":       "资深专家独立视角评审，支持多角色并行",
        "button":        "🚀 开始评审",
        "spinner":       "🤖 AI 专家团正在评审……",
        "result_title":  "📝 评审报告",
        "download_name": "需求评审报告.md",
    },
    SkillMode.TEST_CASE: {
        "label":         "🧪 生成测试用例",
        "caption":       "根据需求文档逐模块生成详细测试用例，覆盖正向/逆向/边界/异常",
        "button":        "🧪 生成测试用例",
        "spinner":       "🤖 正在根据需求文档生成测试用例……",
        "result_title":  "🧪 测试用例",
        "download_name": "测试用例.md",
    },
    SkillMode.TEST_CASE_REVIEW: {
        "label":         "🧾 测试用例评审",
        "caption":       "基于原始需求评审已有测试用例的覆盖性、一致性、可执行性，并输出修订建议版用例",
        "button":        "🧾 开始评审",
        "spinner":       "🤖 正在结合需求上下文评审测试用例……",
        "result_title":  "🧾 测试用例评审报告",
        "download_name": "测试用例评审报告.md",
    },
    SkillMode.REQ_ANALYSIS: {
        "label":         "🔬 需求结构化分析",
        "caption":       "五步法深度拆解需求：业务流程、数据逻辑、交互规则、隐性需求一网打尽",
        "button":        "🔬 开始分析",
        "spinner":       "🤖 正在深度拆解需求结构，识别业务流与数据逻辑……",
        "result_title":  "🔬 需求结构化分析",
        "download_name": "需求结构化分析.md",
    },
    SkillMode.TEST_POINT: {
        "label":         "🎯 测试点提取",
        "caption":       "九维全景分析：功能/边界/异常/性能/安全/兼容性等维度提取测试点",
        "button":        "🎯 提取测试点",
        "spinner":       "🤖 正在进行九维全景测试点分析……",
        "result_title":  "🎯 测试点分析报告",
        "download_name": "测试点分析.md",
    },
    SkillMode.LOG_DIAGNOSIS: {
        "label":         "🔍 缺陷日志诊断",
        "caption":       "粘贴崩溃日志或业务日志，AI 将自动分析报错位置、原因并提供修复建议",
        "uploader_label":"上传日志文件（可选）",
        "button":        "🔍 诊断日志",
        "spinner":       "🤖 正在深入分析日志细节并定位风险……",
        "result_title":  "🔍 日志诊断报告",
        "download_name": "日志诊断报告.md",
    },
    SkillMode.TEST_DATA: {
        "label":         "🏗️ 测试数据准备",
        "caption":       "根据研发技术文档提取表结构，并生成可直接使用的 MySQL 查询与插入 SQL",
        "button":        "🏗️ 生成测试数据 SQL",
        "spinner":       "🤖 正在根据技术文档准备测试数据 SQL……",
        "result_title":  "🏗️ 测试数据准备结果",
        "download_name": "测试数据准备.md",
    },
    SkillMode.IMPACT_ANALYSIS: {
        "label":         "⚡ 需求影响面分析",
        "caption":       "对比两个版本的需求文档，提取变更点并评估对现有功能的影响面",
        "uploader_label":"上传旧版本 (V1.0) 文档",
        "button":        "⚡ 分析影响面",
        "spinner":       "🤖 正在对比双版本需求并评估波及范围……",
        "result_title":  "⚡ 影响面评估报告",
        "download_name": "影响面分析报告.md",
    },
    SkillMode.TEST_PLAN: {
        "label":         "📅 制定测试方案",
        "caption":       "从项目目标、资源、策略、风险等多维度自动生成标准测试方案",
        "button":        "📅 生成方案",
        "spinner":       "🤖 正在全力为您拆解需求并制定测试方案……",
        "result_title":  "📅 标准测试方案",
        "download_name": "测试方案.md",
    },
    SkillMode.FLOWCHART: {
        "label":         "📊 业务流程导图",
        "caption":       "自动提取需求中的业务逻辑节点，生成高颜值的 Mermaid 业务流程图",
        "button":        "📊 生成流程图",
        "spinner":       "🤖 正在梳理业务逻辑并绘制高颜值流程图……",
        "result_title":  "📊 业务流程图",
        "download_name": "业务流程图.md",
    },
    SkillMode.API_TEST_GEN: {
        "label":         "🔌 接口测试生成",
        "caption":       "上传 Swagger/Text 接口文档，自动生成覆盖正向/异常/边界场景的 Pytest 脚本",
        "uploader_label":"上传接口文档 (Swagger/JSON/YAML/Txt)",
        "button":        "🔌 生成测试脚本",
        "spinner":       "🤖 正在分析接口数据并生成 Pytest 脚本……",
        "result_title":  "🔌 接口测试脚本",
        "download_name": "接口自动化脚本.py",
    },
    SkillMode.API_PERF_TEST: {
        "label":         "🚀 接口性能压测",
        "caption":       "上传接口文档，自动转换并生成可高并发执行的 Locust 压测脚本，含断言与请求参数",
        "uploader_label":"上传接口文档 (Swagger/JSON/YAML/Txt)",
        "button":        "🚀 生成压测脚本",
        "spinner":       "🤖 正在转换为 Locust 框架格式压测脚本……",
        "result_title":  "🚀 性能压测脚本",
        "download_name": "Locust性能压测脚本.py",
    },
    SkillMode.AUTO_SCRIPT_GEN: {
        "label":         "🤖 UI 自动化脚本",
        "caption":       "上传测试用例描述或页面 HTML 代码，自动生成 Python + Playwright 自动化脚本",
        "uploader_label":"上传测试用例/页面代码 (Txt/HTML)",
        "button":        "🤖 生成自动脚本",
        "spinner":       "🤖 正在生成 Playwright 自动化测试脚本……",
        "result_title":  "🤖 UI 测试脚本",
        "download_name": "UI自动化脚本.py",
    },
    SkillMode.WEEKLY_REPORT: {
        "label":         "📰 周报生成",
        "caption":       "整理企业微信讨论与 TAPD 截图，生成 Markdown 周报并可选写入飞书",
        "uploader_label":"上传 TAPD 截图 (PNG/JPG/WebP)",
        "button":        "📰 生成测试周报",
        "spinner":       "🤖 正在整理本周讨论与任务信息……",
        "result_title":  "📰 测试周报",
        "download_name": "测试周报.md",
    },
}


# 以"一键执行"模式运行的模式集合（无需文档结构解析，直接调用 AI）
ONEKEY_MODES = {
    SkillMode.LOG_DIAGNOSIS,
    SkillMode.TEST_DATA,
    SkillMode.IMPACT_ANALYSIS,
    SkillMode.API_TEST_GEN,
    SkillMode.API_PERF_TEST,
    SkillMode.AUTO_SCRIPT_GEN,
    SkillMode.WEEKLY_REPORT,
}

# 仅在纯文本模式下走一键路径，有文件时走两步解析的模式集合
TEXT_ONEKEY_MODES = {
    SkillMode.TEST_PLAN,
    SkillMode.FLOWCHART,
    SkillMode.REQ_ANALYSIS,
    SkillMode.TEST_POINT,
}


def get_meta(mode: str, key: str, default: str = "") -> str:
    """便捷获取指定模式的某项元数据。"""
    return MODE_META.get(mode, {}).get(key, default)
