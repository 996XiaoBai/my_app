import json
import re
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple


FINDINGS_JSON_PATTERN = re.compile(r"\s*<findings_json>[\s\S]*?</findings_json>\s*", re.IGNORECASE)
MERMAID_BLOCK_PATTERN = re.compile(r"```(?:mermaid)?\s*([\s\S]*?)```", re.IGNORECASE)
MERMAID_JSON_FIELD_PATTERN = re.compile(r'"mermaid"\s*:\s*"((?:\\.|[^"\\])*)"', re.IGNORECASE)
FLOWCHART_CODE_PATTERN = re.compile(r"^\s*(?:flowchart|graph)\s+(?:TD|TB|BT|RL|LR)\b", re.IGNORECASE)
CASE_PRIORITY_LEVELS = ("P0", "P1", "P2", "P3")
CASE_PRIORITY_RANK = {level: index for index, level in enumerate(CASE_PRIORITY_LEVELS)}
CASE_PRIORITY_ALIASES = {
    "P0": "P0",
    "CRITICAL": "P0",
    "URGENT": "P0",
    "HIGH": "P0",
    "H": "P0",
    "紧急": "P0",
    "致命": "P0",
    "高危": "P0",
    "P1": "P1",
    "MAJOR": "P1",
    "MEDIUM": "P1",
    "M": "P1",
    "高": "P1",
    "重要": "P1",
    "P2": "P2",
    "NORMAL": "P2",
    "LOW": "P2",
    "L": "P2",
    "中": "P2",
    "一般": "P2",
    "P3": "P3",
    "MINOR": "P3",
    "INFO": "P3",
    "LOWEST": "P3",
    "低": "P3",
}
DEFAULT_STEP_EXPECTED = "待补充预期结果"


def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def strip_findings_json_block(value: Any) -> str:
    text = _as_text(value)
    if not text:
        return ""
    return FINDINGS_JSON_PATTERN.sub("\n", text).strip()


def split_legacy_steps(raw_steps: Any) -> List[str]:
    text = _as_text(raw_steps)
    if not text:
        return []

    parts = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\d+\s*[.、]\s*", "", line)
        line = re.sub(r"^[\-*•]\s*", "", line)
        line = line.strip()
        if line:
            parts.append(line)

    if parts:
        return parts
    return [text]


def split_legacy_expectations(raw_expected: Any) -> List[str]:
    return split_legacy_steps(raw_expected)


def normalize_case_priority(raw_priority: Any) -> str:
    text = _as_text(raw_priority, "P3").upper()
    if not text:
        return "P3"

    match = re.search(r"P[0-3]", text)
    if match:
        return match.group(0)

    normalized = CASE_PRIORITY_ALIASES.get(text)
    if normalized:
        return normalized

    text = text.replace("（", "(").replace("）", ")")
    for alias, priority in CASE_PRIORITY_ALIASES.items():
        if alias and alias in text:
            return priority
    return "P3"


def _normalize_text_list(value: Any) -> List[str]:
    if isinstance(value, list):
        parts = [_as_text(item) for item in value]
        return [part for part in parts if part]

    text = _as_text(value)
    if not text:
        return []

    parts = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^\d+\s*[.、]\s*", "", line)
        line = re.sub(r"^[\-*•]\s*", "", line)
        line = line.strip()
        if line:
            parts.append(line)
    return parts or [text]


def _expand_expected_values(fallback_expected: str, count: int) -> List[str]:
    if count <= 0:
        return []

    expected_lines = split_legacy_expectations(fallback_expected)
    if not expected_lines:
        return [DEFAULT_STEP_EXPECTED] * count
    if len(expected_lines) >= count:
        return expected_lines[:count]
    if len(expected_lines) == 1:
        return expected_lines * count
    return expected_lines + [expected_lines[-1]] * (count - len(expected_lines))


def normalize_case_steps(raw_steps: Any, fallback_expected: str = "") -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    fallback_values: List[str] = []

    if isinstance(raw_steps, list):
        fallback_values = _expand_expected_values(fallback_expected, len(raw_steps))
        for item in raw_steps:
            index = len(normalized)
            if isinstance(item, dict):
                action = _as_text(item.get("action") or item.get("step") or item.get("title"))
                expected = _as_text(item.get("expected") or item.get("result")) or (
                    fallback_values[index] if index < len(fallback_values) else DEFAULT_STEP_EXPECTED
                )
            else:
                action = _as_text(item)
                expected = fallback_values[index] if index < len(fallback_values) else DEFAULT_STEP_EXPECTED

            if action or expected:
                normalized.append({
                    "action": action,
                    "expected": expected or DEFAULT_STEP_EXPECTED
                })
    elif isinstance(raw_steps, dict):
        action = _as_text(raw_steps.get("action") or raw_steps.get("step") or raw_steps.get("title"))
        expected = _as_text(raw_steps.get("expected") or raw_steps.get("result")) or (
            _expand_expected_values(fallback_expected, 1)[0] if fallback_expected else DEFAULT_STEP_EXPECTED
        )
        if action or expected:
            normalized.append({
                "action": action,
                "expected": expected or DEFAULT_STEP_EXPECTED
            })
    else:
        step_lines = split_legacy_steps(raw_steps)
        fallback_values = _expand_expected_values(fallback_expected, len(step_lines))
        for idx, action in enumerate(step_lines):
            normalized.append({
                "action": action,
                "expected": fallback_values[idx] if idx < len(fallback_values) else DEFAULT_STEP_EXPECTED
            })

    if not normalized and fallback_expected:
        normalized.append({
            "action": "",
            "expected": _as_text(fallback_expected) or DEFAULT_STEP_EXPECTED
        })

    return normalized


def normalize_case_item(raw_item: Dict[str, Any], default_module: str = "") -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    return {
        "id": _as_text(raw_item.get("id")) or str(uuid.uuid4()),
        "priority": normalize_case_priority(raw_item.get("priority")),
        "module": _as_text(raw_item.get("module"), default_module) or default_module or "未分类",
        "title": _as_text(raw_item.get("title") or raw_item.get("name"), "未命名用例") or "未命名用例",
        "precondition": _as_text(raw_item.get("precondition")),
        "steps": normalize_case_steps(raw_item.get("steps"), fallback_expected=_as_text(raw_item.get("expected")))
    }


def normalize_case_items(raw_items: Any, default_module: str = "") -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [normalize_case_item(item, default_module=default_module) for item in raw_items if isinstance(item, dict)]


def build_case_module_tree(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    root: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    ordered_items = sorted(
        items,
        key=lambda item: (
            _as_text(item.get("module"), "未分类"),
            CASE_PRIORITY_RANK.get(_as_text(item.get("priority"), "P3"), len(CASE_PRIORITY_LEVELS)),
            _as_text(item.get("title"), "未命名用例"),
        ),
    )

    for item in ordered_items:
        module_path = _as_text(item.get("module"), "未分类") or "未分类"
        parts = [part.strip() for part in module_path.split("/") if part.strip()] or ["未分类"]
        current_children = root
        current_path_parts: List[str] = []
        current_node: Optional[Dict[str, Any]] = None

        for part in parts:
            current_path_parts.append(part)
            if part not in current_children:
                current_children[part] = {
                    "name": part,
                    "path": "/".join(current_path_parts),
                    "cases": [],
                    "children": OrderedDict(),
                }
            current_node = current_children[part]
            current_children = current_node["children"]

        if current_node is not None:
            current_node["cases"].append(item)

    def serialize(node: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "name": node["name"],
            "path": node["path"],
            "cases": node["cases"],
            "children": [serialize(child) for child in node["children"].values()],
        }

    return [serialize(node) for node in root.values()]


def build_case_suite(raw_items: Any, summary: Optional[str] = None, default_module: str = "") -> Dict[str, Any]:
    items = sorted(
        normalize_case_items(raw_items, default_module=default_module),
        key=lambda item: (
            CASE_PRIORITY_RANK.get(_as_text(item.get("priority"), "P3"), len(CASE_PRIORITY_LEVELS)),
            _as_text(item.get("module"), "未分类"),
            _as_text(item.get("title"), "未命名用例"),
        ),
    )
    normalized_summary = _as_text(summary) or "已完成结构化测试用例生成。"
    return {
        "items": items,
        "modules": build_case_module_tree(items),
        "summary": normalized_summary,
        "markdown": build_case_suite_markdown({
            "items": items,
            "summary": normalized_summary,
        }),
    }


def build_case_suite_markdown(payload: Any, default_module: str = "") -> str:
    if isinstance(payload, dict):
        suite = {
            "items": normalize_case_items(payload.get("items"), default_module=default_module),
            "summary": _as_text(payload.get("summary")) or "已完成结构化测试用例生成。"
        }
    else:
        suite = build_case_suite(payload, default_module=default_module)

    sections: List[str] = ["# 智能测试用例", ""]
    summary = _as_text(suite.get("summary"))
    if summary:
        sections.extend([f"> {summary}", ""])

    modules: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for item in suite.get("items", []):
        if not isinstance(item, dict):
            continue
        module_name = _as_text(item.get("module"), "未分类") or "未分类"
        modules.setdefault(module_name, []).append(item)

    for module_name, module_items in modules.items():
        sections.extend([f"## 模块：{module_name}", ""])
        for item in module_items:
            title = _as_text(item.get("title"), "未命名用例") or "未命名用例"
            sections.append(f"### case：{title}")

            precondition = _as_text(item.get("precondition"))
            if precondition:
                sections.append(f"- 前置条件：{precondition}")

            sections.append("- 步骤描述：")

            steps = item.get("steps") or []
            if isinstance(steps, list) and steps:
                for index, step in enumerate(steps, start=1):
                    if isinstance(step, dict):
                        action = _as_text(step.get("action"), "待补充步骤") or "待补充步骤"
                        expected = _as_text(step.get("expected"), DEFAULT_STEP_EXPECTED) or DEFAULT_STEP_EXPECTED
                    else:
                        action = _as_text(step, "待补充步骤") or "待补充步骤"
                        expected = DEFAULT_STEP_EXPECTED
                    sections.append(f"  {index}. 步骤：{action}")
                    sections.append(f"     - 预期结果：{expected}")
            else:
                sections.append("  1. 步骤：待补充步骤")
                sections.append(f"     - 预期结果：{DEFAULT_STEP_EXPECTED}")

            sections.append(f"- 用例等级：{_as_text(item.get('priority'), 'P3') or 'P3'}")

            sections.extend(["", "---", ""])

    return "\n".join(sections).strip() + "\n"


def normalize_requirement_analysis_item(raw_item: Dict[str, Any], default_module: str = "") -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    return {
        "module": _as_text(raw_item.get("module"), default_module) or default_module or "未分类模块",
        "summary": _as_text(raw_item.get("summary")),
        "actors": _normalize_text_list(raw_item.get("actors")),
        "business_rules": _normalize_text_list(raw_item.get("business_rules")),
        "data_entities": _normalize_text_list(raw_item.get("data_entities")),
        "preconditions": _normalize_text_list(raw_item.get("preconditions")),
        "postconditions": _normalize_text_list(raw_item.get("postconditions")),
        "exceptions": _normalize_text_list(raw_item.get("exceptions")),
        "risks": _normalize_text_list(raw_item.get("risks")),
        "open_questions": _normalize_text_list(raw_item.get("open_questions")),
    }


def build_requirement_analysis_markdown(payload: Any, default_module: str = "") -> str:
    items = payload.get("items") if isinstance(payload, dict) else payload
    summary = _as_text(payload.get("summary")) if isinstance(payload, dict) else ""
    normalized_items = []
    if isinstance(items, list):
        normalized_items = [
            normalize_requirement_analysis_item(item, default_module=default_module)
            for item in items
            if isinstance(item, dict)
        ]

    sections = ["# 智能需求分析", ""]
    if summary:
        sections.extend([f"> {summary}", ""])

    field_sections = [
        ("actors", "参与角色"),
        ("business_rules", "业务规则"),
        ("data_entities", "数据实体"),
        ("preconditions", "前置条件"),
        ("postconditions", "后置条件"),
        ("exceptions", "异常处理"),
        ("risks", "显性风险"),
        ("open_questions", "待确认问题"),
    ]

    for item in normalized_items:
        sections.append(f"## {item['module']}")
        sections.append("")
        if item["summary"]:
            sections.extend([item["summary"], ""])
        for key, label in field_sections:
            values = item.get(key) or []
            if values:
                sections.append(f"### {label}")
                sections.extend([f"- {value}" for value in values])
                sections.append("")

    return "\n".join(sections).strip() + "\n"


def build_requirement_analysis_pack(raw_items: Any, summary: Optional[str] = None, default_module: str = "") -> Dict[str, Any]:
    items = []
    if isinstance(raw_items, list):
        items = [
            normalize_requirement_analysis_item(item, default_module=default_module)
            for item in raw_items
            if isinstance(item, dict)
        ]
    normalized_summary = _as_text(summary) or "已完成结构化需求分析。"
    return {
        "items": items,
        "summary": normalized_summary,
        "markdown": build_requirement_analysis_markdown({
            "items": items,
            "summary": normalized_summary,
        }),
    }


def sanitize_mermaid_code(value: Any) -> str:
    normalized, _, _ = _sanitize_mermaid_code_with_meta(value)
    return normalized


def _sanitize_mermaid_code_with_meta(value: Any) -> Tuple[str, bool, List[str]]:
    text = _extract_mermaid_text(value)
    if not text:
        return "", False, []

    block_match = MERMAID_BLOCK_PATTERN.search(text)
    if block_match:
        text = block_match.group(1).strip()

    lines = text.splitlines()
    cleaned: List[str] = []
    for line in lines:
        candidate = line.rstrip()
        if candidate.strip().startswith("classDef"):
            candidate = re.sub(r"\s+%%.*$", "", candidate)
        elif candidate.strip().startswith("%%"):
            continue
        candidate = re.sub(r'\[/"([^"]*?)"/\]', r'["\1"]', candidate)
        candidate = re.sub(r'\{/"([^"]*?)"/\}', r'["\1"]', candidate)
        cleaned.append(candidate)
    normalized, repaired = _repair_mermaid_structure("\n".join(cleaned).strip())
    issues = _detect_mermaid_structure_issues(normalized)
    if not FLOWCHART_CODE_PATTERN.match(normalized):
        return "", repaired, issues
    return normalized, repaired, issues


def _repair_mermaid_structure(text: str) -> Tuple[str, bool]:
    if not text:
        return "", False

    repaired_lines: List[str] = []
    changed = False
    for line in text.splitlines():
        repaired_line = _repair_mermaid_line(line)
        if repaired_line != line:
            changed = True
        repaired_lines.append(repaired_line)

    subgraph_count = sum(1 for line in repaired_lines if line.strip().startswith("subgraph "))
    end_count = sum(1 for line in repaired_lines if line.strip() == "end")
    if end_count < subgraph_count:
        repaired_lines.extend(["end"] * (subgraph_count - end_count))
        changed = True

    return "\n".join(repaired_lines).strip(), changed


def _repair_mermaid_line(line: str) -> str:
    repaired = line
    replacements = (
        (r'\["([^"\n]*)"\)', r'["\1"]'),
        (r'\["([^"\n]*)"\}', r'["\1"]'),
        (r'\("([^"\n]*)"\]', r'("\1")'),
        (r'\("([^"\n]*)"\}', r'("\1")'),
        (r'\{"([^"\n]*)"\]', r'{"\1"}'),
        (r'\{"([^"\n]*)"\)', r'{"\1"}'),
    )
    for pattern, replacement in replacements:
        repaired = re.sub(pattern, replacement, repaired)
    return repaired


def _detect_mermaid_structure_issues(text: str) -> List[str]:
    if not text:
        return []

    issues: List[str] = []
    broken_patterns = (
        r'\["[^"\n]*"\)',
        r'\["[^"\n]*"\}',
        r'\("[^"\n]*"\]',
        r'\("[^"\n]*"\}',
        r'\{"[^"\n]*"\]',
        r'\{"[^"\n]*"\)',
    )
    if any(re.search(pattern, text) for pattern in broken_patterns):
        issues.append("节点标签闭合符号仍不匹配")

    subgraph_count = sum(1 for line in text.splitlines() if line.strip().startswith("subgraph "))
    end_count = sum(1 for line in text.splitlines() if line.strip() == "end")
    if end_count != subgraph_count:
        issues.append("subgraph 与 end 数量不匹配")

    return issues


def _extract_json_like_string_field(text: str, field_names: List[str]) -> str:
    for field_name in field_names:
        key_match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"', text, re.IGNORECASE)
        if not key_match:
            continue

        start = key_match.end()
        next_field_match = re.search(r'",\s*(?:\r?\n\s*)?"[^"\n]+"\s*:', text[start:])
        if next_field_match:
            return _decode_json_like_string(text[start:start + next_field_match.start()])

        closing_match = re.search(r'"\s*[\]}]', text[start:])
        if closing_match:
            return _decode_json_like_string(text[start:start + closing_match.start()])

        return _decode_json_like_string(text[start:])

    return ""


def _decode_json_like_string(value: str) -> str:
    return (
        value
        .replace("\\r", "\r")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def _extract_mermaid_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("mermaid", "code", "diagram"):
            nested = _extract_mermaid_text(value.get(key))
            if nested:
                return nested
        return ""

    if isinstance(value, list):
        for item in value:
            nested = _extract_mermaid_text(item)
            if nested:
                return nested
        return ""

    text = _as_text(value)
    if not text:
        return ""

    block_match = MERMAID_BLOCK_PATTERN.search(text)
    if block_match:
        return _extract_mermaid_text(block_match.group(1).strip())

    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return _extract_mermaid_text(json.loads(stripped))
        except (json.JSONDecodeError, TypeError, ValueError):
            extracted_field = _extract_json_like_string_field(stripped, ["mermaid", "code", "diagram"])
            if extracted_field:
                return extracted_field

    return stripped


def normalize_flowchart_item(raw_item: Dict[str, Any], default_module: str = "") -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    module_name = _as_text(raw_item.get("module"), default_module) or default_module or "未分类模块"
    title = _as_text(raw_item.get("title"), module_name) or module_name
    original_mermaid = raw_item.get("mermaid")
    normalized_mermaid, repaired, issues = _sanitize_mermaid_code_with_meta(original_mermaid)
    warnings = _normalize_text_list(raw_item.get("warnings"))
    if repaired:
        warnings.append("Mermaid 语法已自动修复，建议复核关键节点命名与分支关系。")
    if issues:
        warnings.append(f"Mermaid 语法校验仍存在风险：{'；'.join(issues)}。")
    if not normalized_mermaid and _as_text(original_mermaid):
        warnings.append("Mermaid 语法校验未通过，当前模块无法生成稳定流程图，请重新生成或人工修正。")
    deduped_warnings = list(dict.fromkeys([warning for warning in warnings if warning]))
    return {
        "module": module_name,
        "title": title,
        "summary": _as_text(raw_item.get("summary")),
        "mermaid": normalized_mermaid,
        "warnings": deduped_warnings,
    }


def build_flowchart_markdown(payload: Any, default_module: str = "") -> str:
    items = payload.get("items") if isinstance(payload, dict) else payload
    summary = _as_text(payload.get("summary")) if isinstance(payload, dict) else ""
    normalized_items = []
    if isinstance(items, list):
        normalized_items = [
            normalize_flowchart_item(item, default_module=default_module)
            for item in items
            if isinstance(item, dict)
        ]

    sections = ["# 业务流程图", ""]
    if summary:
        sections.extend([f"> {summary}", ""])

    for item in normalized_items:
        sections.append(f"## {item['title']}")
        sections.append("")
        if item["summary"]:
            sections.extend([item["summary"], ""])
        if item["mermaid"]:
            sections.extend(["```mermaid", item["mermaid"], "```", ""])
        if item["warnings"]:
            sections.append("### 风险提示")
            sections.extend([f"- {warning}" for warning in item["warnings"]])
            sections.append("")

    return "\n".join(sections).strip() + "\n"


def build_flowchart_pack(raw_items: Any, summary: Optional[str] = None, default_module: str = "") -> Dict[str, Any]:
    items = []
    if isinstance(raw_items, list):
        items = [
            normalize_flowchart_item(item, default_module=default_module)
            for item in raw_items
            if isinstance(item, dict)
        ]
    normalized_summary = _as_text(summary) or "已完成业务流程图生成。"
    return {
        "items": items,
        "summary": normalized_summary,
        "markdown": build_flowchart_markdown({
            "items": items,
            "summary": normalized_summary,
        }),
    }


def normalize_test_data_column(raw_item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    return {
        "name": _as_text(raw_item.get("name"), "unknown_column") or "unknown_column",
        "sql_type": _as_text(raw_item.get("sql_type") or raw_item.get("type"), "UNKNOWN") or "UNKNOWN",
        "description": _as_text(raw_item.get("description")),
        "primary_key": bool(raw_item.get("primary_key") or raw_item.get("is_primary_key")),
        "required": bool(raw_item.get("required")),
        "default": _as_text(raw_item.get("default")),
    }


def normalize_test_data_table(raw_item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    columns = raw_item.get("columns")
    normalized_columns = [
        normalize_test_data_column(column)
        for column in columns
        if isinstance(column, dict)
    ] if isinstance(columns, list) else []

    return {
        "name": _as_text(raw_item.get("name"), "unknown_table") or "unknown_table",
        "display_name": _as_text(raw_item.get("display_name") or raw_item.get("description") or raw_item.get("name"), "unknown_table") or "unknown_table",
        "description": _as_text(raw_item.get("description")),
        "columns": normalized_columns,
        "select_sql": _as_text(raw_item.get("select_sql")),
        "insert_sql": _as_text(raw_item.get("insert_sql")),
        "update_sql": _as_text(raw_item.get("update_sql")),
        "delete_sql": _as_text(raw_item.get("delete_sql")),
    }


def normalize_test_data_scenario(raw_item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    tables = raw_item.get("tables")
    normalized_tables = [
        _as_text(table_name)
        for table_name in tables
        if _as_text(table_name)
    ] if isinstance(tables, list) else []

    return {
        "name": _as_text(raw_item.get("name"), "未命名场景") or "未命名场景",
        "tables": normalized_tables,
        "select_sql": _as_text(raw_item.get("select_sql")),
        "insert_sql": _as_text(raw_item.get("insert_sql")),
        "update_sql": _as_text(raw_item.get("update_sql")),
        "delete_sql": _as_text(raw_item.get("delete_sql")),
    }


def _build_sql_comment_lines(value: Any) -> List[str]:
    return [f"-- {line}" for line in _normalize_text_list(value)]


def build_test_data_sql_file(payload: Any) -> str:
    tables = payload.get("tables") if isinstance(payload, dict) else []
    scenarios = payload.get("scenarios") if isinstance(payload, dict) else []
    warnings = payload.get("warnings") if isinstance(payload, dict) else []
    summary = _as_text(payload.get("summary")) if isinstance(payload, dict) else ""
    document_name = _as_text(payload.get("document_name")) if isinstance(payload, dict) else ""

    normalized_tables = [
        normalize_test_data_table(item)
        for item in tables
        if isinstance(item, dict)
    ] if isinstance(tables, list) else []

    normalized_scenarios = [
        normalize_test_data_scenario(item)
        for item in scenarios
        if isinstance(item, dict)
    ] if isinstance(scenarios, list) else []

    normalized_warnings = _normalize_text_list(warnings)

    sections: List[str] = ["-- 识别摘要"]
    if document_name:
        sections.append(f"-- 文档名称：{document_name}")
    if summary:
        sections.append(f"-- 处理摘要：{summary}")
    sections.append(f"-- 识别表数量：{len(normalized_tables)}")
    sections.append(f"-- 生成场景数量：{len(normalized_scenarios)}")
    sections.append("")

    sections.extend(["-- 按表 SQL", ""])
    if normalized_tables:
        for table in normalized_tables:
            sections.append(f"-- 表：{table['display_name']} ({table['name']})")
            if table["description"]:
                sections.append(f"-- 说明：{table['description']}")
            sections.extend([
                table["select_sql"] or f"-- 未生成 {table['name']} 的 SELECT SQL",
                "",
                table["insert_sql"] or f"-- 未生成 {table['name']} 的 INSERT SQL",
                "",
                table["update_sql"] or f"-- 未生成 {table['name']} 的 UPDATE SQL",
                "",
                table["delete_sql"] or f"-- 未生成 {table['name']} 的 DELETE SQL",
                "",
            ])
    else:
        sections.extend(["-- 未识别到可导出的按表 SQL。", ""])

    sections.extend(["-- 按场景 SQL", ""])
    if normalized_scenarios:
        for scenario in normalized_scenarios:
            sections.extend([
                f"-- 场景：{scenario['name']}",
                f"-- 依赖表：{', '.join(scenario['tables']) or '未识别'}",
                scenario["select_sql"] or f"-- 未生成场景 {scenario['name']} 的 SELECT SQL",
                "",
                scenario["insert_sql"] or f"-- 未生成场景 {scenario['name']} 的 INSERT SQL",
                "",
                scenario["update_sql"] or f"-- 未生成场景 {scenario['name']} 的 UPDATE SQL",
                "",
                scenario["delete_sql"] or f"-- 未生成场景 {scenario['name']} 的 DELETE SQL",
                "",
            ])
    else:
        sections.extend(["-- 未识别到可导出的按场景 SQL。", ""])

    sections.append("-- 识别告警")
    if normalized_warnings:
        sections.extend(_build_sql_comment_lines(normalized_warnings))
    else:
        sections.append("-- 未发现明显告警。")

    return "\n".join(sections).strip() + "\n"


def build_test_data_markdown(payload: Any) -> str:
    tables = payload.get("tables") if isinstance(payload, dict) else []
    scenarios = payload.get("scenarios") if isinstance(payload, dict) else []
    warnings = payload.get("warnings") if isinstance(payload, dict) else []
    summary = _as_text(payload.get("summary")) if isinstance(payload, dict) else ""
    document_name = _as_text(payload.get("document_name")) if isinstance(payload, dict) else ""

    normalized_tables = [
        normalize_test_data_table(item)
        for item in tables
        if isinstance(item, dict)
    ] if isinstance(tables, list) else []

    normalized_scenarios = [
        normalize_test_data_scenario(item)
        for item in scenarios
        if isinstance(item, dict)
    ] if isinstance(scenarios, list) else []

    normalized_warnings = _normalize_text_list(warnings)

    sections = ["# 识别摘要", ""]
    if document_name:
        sections.append(f"- 文档名称：{document_name}")
    if summary:
        sections.append(f"- 处理摘要：{summary}")
    sections.append(f"- 识别表数量：{len(normalized_tables)}")
    sections.append(f"- 生成场景数量：{len(normalized_scenarios)}")
    sections.append("")

    sections.append("## 表清单")
    if normalized_tables:
        sections.extend(
            [f"- `{table['name']}`：{len(table['columns'])} 个字段" for table in normalized_tables]
        )
    else:
        sections.append("- 未识别到可生成 SQL 的表结构。")
    sections.append("")

    sections.append("## 场景清单")
    if normalized_scenarios:
        sections.extend(
            [f"- {scenario['name']}：{', '.join(scenario['tables']) or '未关联表'}" for scenario in normalized_scenarios]
        )
    else:
        sections.append("- 未生成可用的场景 SQL。")
    sections.append("")

    sections.extend(["# 按表 SQL", ""])
    if normalized_tables:
        for table in normalized_tables:
            table_heading = f"{table['display_name']} (`{table['name']}`)"
            sections.extend([f"## {table_heading}", "", "### 字段摘要", ""])
            sections.extend([
                "| 字段 | 类型 | 主键 | 必填 | 说明 |",
                "| --- | --- | --- | --- | --- |",
            ])
            if table["columns"]:
                for column in table["columns"]:
                    description = column["description"] or "-"
                    sections.append(
                        "| {name} | {sql_type} | {primary_key} | {required} | {description} |".format(
                            name=column["name"],
                            sql_type=column["sql_type"],
                            primary_key="是" if column["primary_key"] else "否",
                            required="是" if column["required"] else "否",
                            description=description.replace("|", "\\|"),
                        )
                    )
            else:
                sections.append("| - | - | - | - | 未识别到字段 |")
            sections.extend([
                "",
                "### SELECT",
                "",
                "```sql",
                table["select_sql"] or "-- 未生成 SELECT SQL",
                "```",
                "",
                "### INSERT",
                "",
                "```sql",
                table["insert_sql"] or "-- 未生成 INSERT SQL",
                "```",
                "",
                "### UPDATE",
                "",
                "```sql",
                table["update_sql"] or "-- 未生成 UPDATE SQL",
                "```",
                "",
                "### DELETE",
                "",
                "```sql",
                table["delete_sql"] or "-- 未生成 DELETE SQL",
                "```",
                "",
            ])
    else:
        sections.extend(["- 未识别到可输出的按表 SQL。", ""])

    sections.extend(["# 按场景 SQL", ""])
    if normalized_scenarios:
        for scenario in normalized_scenarios:
            sections.extend([
                f"## {scenario['name']}",
                "",
                "### 依赖表",
                "",
            ])
            if scenario["tables"]:
                sections.extend([f"- `{table_name}`" for table_name in scenario["tables"]])
            else:
                sections.append("- 未识别到依赖表")
            sections.extend([
                "",
                "### SELECT",
                "",
                "```sql",
                scenario["select_sql"] or "-- 未生成 SELECT SQL",
                "```",
                "",
                "### INSERT",
                "",
                "```sql",
                scenario["insert_sql"] or "-- 未生成 INSERT SQL",
                "```",
                "",
                "### UPDATE",
                "",
                "```sql",
                scenario["update_sql"] or "-- 未生成 UPDATE SQL",
                "```",
                "",
                "### DELETE",
                "",
                "```sql",
                scenario["delete_sql"] or "-- 未生成 DELETE SQL",
                "```",
                "",
            ])
    else:
        sections.extend(["- 未生成可用的按场景 SQL。", ""])

    sections.extend(["# 识别告警", ""])
    if normalized_warnings:
        sections.extend([f"- {warning}" for warning in normalized_warnings])
    else:
        sections.append("- 未发现明显告警。")

    return "\n".join(sections).strip() + "\n"


def build_test_data_pack(
    raw_tables: Any,
    raw_scenarios: Any,
    summary: Optional[str] = None,
    warnings: Optional[Any] = None,
    document_name: str = "",
) -> Dict[str, Any]:
    tables = [
        normalize_test_data_table(item)
        for item in raw_tables
        if isinstance(item, dict)
    ] if isinstance(raw_tables, list) else []

    scenarios = [
        normalize_test_data_scenario(item)
        for item in raw_scenarios
        if isinstance(item, dict)
    ] if isinstance(raw_scenarios, list) else []

    normalized_warnings = _normalize_text_list(warnings)
    normalized_summary = _as_text(summary) or "已根据技术文档完成测试数据 SQL 准备。"

    return {
        "document_name": document_name,
        "tables": tables,
        "scenarios": scenarios,
        "warnings": normalized_warnings,
        "summary": normalized_summary,
        "markdown": build_test_data_markdown({
            "document_name": document_name,
            "tables": tables,
            "scenarios": scenarios,
            "warnings": normalized_warnings,
            "summary": normalized_summary,
        }),
        "sql_file_content": build_test_data_sql_file({
            "document_name": document_name,
            "tables": tables,
            "scenarios": scenarios,
            "warnings": normalized_warnings,
            "summary": normalized_summary,
        }),
    }


def normalize_api_test_case(raw_item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    depends_on = raw_item.get("depends_on")
    raw_extract = raw_item.get("extract")
    raw_assertions = raw_item.get("assertions")

    return {
        "case_id": _as_text(raw_item.get("case_id"), str(uuid.uuid4())) or str(uuid.uuid4()),
        "title": _as_text(raw_item.get("title"), "未命名接口用例") or "未命名接口用例",
        "operation_id": _as_text(raw_item.get("operation_id")),
        "resource_key": _as_text(raw_item.get("resource_key")),
        "category": _as_text(raw_item.get("category"), "unknown") or "unknown",
        "priority": normalize_case_priority(raw_item.get("priority")),
        "depends_on": [
            _as_text(item)
            for item in depends_on
            if _as_text(item)
        ] if isinstance(depends_on, list) else [],
        "extract": [
            {
                "name": _as_text(item.get("name")),
                "from": _as_text(item.get("from")),
                "pick": _as_text(item.get("pick")),
            }
            for item in raw_extract
            if isinstance(item, dict) and (_as_text(item.get("name")) or _as_text(item.get("pick")))
        ] if isinstance(raw_extract, list) else [],
        "assertions": _normalize_text_list(raw_assertions),
    }


def normalize_api_test_scene(raw_item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    steps = raw_item.get("steps")
    return {
        "scene_id": _as_text(raw_item.get("scene_id"), str(uuid.uuid4())) or str(uuid.uuid4()),
        "title": _as_text(raw_item.get("title"), "未命名关联场景") or "未命名关联场景",
        "description": _as_text(raw_item.get("description")),
        "steps": [
            _as_text(step)
            for step in steps
            if _as_text(step)
        ] if isinstance(steps, list) else [],
    }


def normalize_api_test_execution(raw_execution: Any) -> Dict[str, Any]:
    if not isinstance(raw_execution, dict):
        return {}

    stats = raw_execution.get("stats") if isinstance(raw_execution.get("stats"), dict) else {}
    artifacts = raw_execution.get("artifacts") if isinstance(raw_execution.get("artifacts"), dict) else {}

    return {
        "run_id": _as_text(raw_execution.get("run_id")),
        "status": _as_text(raw_execution.get("status")),
        "summary": _as_text(raw_execution.get("summary")),
        "stats": {
            "total": int(stats.get("total") or 0),
            "passed": int(stats.get("passed") or 0),
            "failed": int(stats.get("failed") or 0),
            "errors": int(stats.get("errors") or 0),
            "skipped": int(stats.get("skipped") or 0),
        },
        "command": _as_text(raw_execution.get("command")),
        "stdout": _as_text(raw_execution.get("stdout")),
        "stderr": _as_text(raw_execution.get("stderr")),
        "junit_xml_content": _as_text(raw_execution.get("junit_xml_content")),
        "execution_summary_content": _as_text(raw_execution.get("execution_summary_content")),
        "runtime_config_content": _as_text(raw_execution.get("runtime_config_content")),
        "asset_snapshot_content": _as_text(raw_execution.get("asset_snapshot_content")),
        "case_snapshot_content": _as_text(raw_execution.get("case_snapshot_content")),
        "scene_snapshot_content": _as_text(raw_execution.get("scene_snapshot_content")),
        "artifacts": {
            "run_dir": _as_text(artifacts.get("run_dir")),
            "generated_script": _as_text(artifacts.get("generated_script")),
            "compiled_script": _as_text(artifacts.get("compiled_script")),
            "junit_xml": _as_text(artifacts.get("junit_xml")),
            "runtime_config": _as_text(artifacts.get("runtime_config")),
            "asset_snapshot": _as_text(artifacts.get("asset_snapshot")),
            "case_snapshot": _as_text(artifacts.get("case_snapshot")),
            "scene_snapshot": _as_text(artifacts.get("scene_snapshot")),
            "execution_summary": _as_text(artifacts.get("execution_summary")),
            "allure_results": _as_text(artifacts.get("allure_results")),
            "allure_archive": _as_text(artifacts.get("allure_archive")),
        },
    }


def normalize_api_test_link_plan(raw_link_plan: Any) -> Dict[str, Any]:
    if not isinstance(raw_link_plan, dict):
        return {}

    scene_orders = raw_link_plan.get("scene_orders") if isinstance(raw_link_plan.get("scene_orders"), list) else []
    case_dependencies = raw_link_plan.get("case_dependencies") if isinstance(raw_link_plan.get("case_dependencies"), dict) else {}
    extract_variables = raw_link_plan.get("extract_variables") if isinstance(raw_link_plan.get("extract_variables"), dict) else {}

    return {
        "ordered_case_ids": _normalize_text_list(raw_link_plan.get("ordered_case_ids")),
        "standalone_case_ids": _normalize_text_list(raw_link_plan.get("standalone_case_ids")),
        "scene_orders": [
            {
                "scene_id": _as_text(item.get("scene_id")),
                "ordered_steps": _normalize_text_list(item.get("ordered_steps")),
            }
            for item in scene_orders
            if isinstance(item, dict) and _as_text(item.get("scene_id"))
        ],
        "case_dependencies": {
            _as_text(case_id): _normalize_text_list(dependencies)
            for case_id, dependencies in case_dependencies.items()
            if _as_text(case_id)
        },
        "extract_variables": {
            _as_text(variable_name): _normalize_text_list(provider_cases)
            for variable_name, provider_cases in extract_variables.items()
            if _as_text(variable_name)
        },
        "warnings": _normalize_text_list(raw_link_plan.get("warnings")),
    }


def normalize_api_test_suite(raw_suite: Any) -> Dict[str, Any]:
    if not isinstance(raw_suite, dict):
        return {}

    return {
        "suite_id": _as_text(raw_suite.get("suite_id")),
        "suite_version": int(raw_suite.get("suite_version") or 0),
        "title": _as_text(raw_suite.get("title")),
        "case_count": int(raw_suite.get("case_count") or 0),
        "scene_count": int(raw_suite.get("scene_count") or 0),
        "storage_path": _as_text(raw_suite.get("storage_path")),
    }


def normalize_api_test_report(raw_report: Any) -> Dict[str, Any]:
    if not isinstance(raw_report, dict):
        return {}

    failure_cases = raw_report.get("failure_cases") if isinstance(raw_report.get("failure_cases"), list) else []
    artifact_labels = raw_report.get("artifact_labels") if isinstance(raw_report.get("artifact_labels"), list) else []
    return {
        "status": _as_text(raw_report.get("status")),
        "headline": _as_text(raw_report.get("headline")),
        "summary_lines": _normalize_text_list(raw_report.get("summary_lines")),
        "failure_cases": [
            {
                "key": _as_text(item.get("key")),
                "title": _as_text(item.get("title")),
                "detail": _as_text(item.get("detail")),
                "kind": _as_text(item.get("kind")),
            }
            for item in failure_cases
            if isinstance(item, dict) and _as_text(item.get("key"))
        ],
        "artifact_labels": [
            {
                "key": _as_text(item.get("key")),
                "label": _as_text(item.get("label")),
                "value": _as_text(item.get("value")),
            }
            for item in artifact_labels
            if isinstance(item, dict) and _as_text(item.get("key"))
        ],
    }


def _normalize_api_test_spec(raw_spec: Any) -> Dict[str, Any]:
    if not isinstance(raw_spec, dict):
        return {
            "title": "",
            "version": "",
            "openapi_version": "",
            "servers": [],
            "auth_profile": {
                "required_headers": [],
                "required_cookies": [],
            },
            "resources": [],
            "operations": [],
            "warnings": [],
        }

    auth_profile = raw_spec.get("auth_profile") if isinstance(raw_spec.get("auth_profile"), dict) else {}
    servers = raw_spec.get("servers") if isinstance(raw_spec.get("servers"), list) else []
    resources = raw_spec.get("resources") if isinstance(raw_spec.get("resources"), list) else []
    operations = raw_spec.get("operations") if isinstance(raw_spec.get("operations"), list) else []

    return {
        "title": _as_text(raw_spec.get("title")),
        "version": _as_text(raw_spec.get("version")),
        "openapi_version": _as_text(raw_spec.get("openapi_version")),
        "servers": [
            {
                "url": _as_text(item.get("url")),
                "description": _as_text(item.get("description")),
            }
            for item in servers
            if isinstance(item, dict) and _as_text(item.get("url"))
        ],
        "auth_profile": {
            "required_headers": _normalize_text_list(auth_profile.get("required_headers")),
            "required_cookies": _normalize_text_list(auth_profile.get("required_cookies")),
        },
        "resources": [
            {
                "resource_key": _as_text(item.get("resource_key")),
                "tag": _as_text(item.get("tag")),
                "lookup_fields": _normalize_text_list(item.get("lookup_fields")),
                "operation_ids": _normalize_text_list(item.get("operation_ids")),
                "operation_categories": _normalize_text_list(item.get("operation_categories")),
            }
            for item in resources
            if isinstance(item, dict) and _as_text(item.get("resource_key"))
        ],
        "operations": [
            {
                "operation_id": _as_text(item.get("operation_id")),
                "summary": _as_text(item.get("summary")),
                "category": _as_text(item.get("category"), "unknown") or "unknown",
                "resource_key": _as_text(item.get("resource_key")),
            }
            for item in operations
            if isinstance(item, dict) and _as_text(item.get("operation_id"))
        ],
        "warnings": _normalize_text_list(raw_spec.get("warnings")),
    }


def _normalize_script_content(script: Any) -> str:
    text = _as_text(script)
    if not text:
        return ""

    block_match = re.search(r"```(?:python)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if block_match:
        return block_match.group(1).strip()
    return text


def build_api_test_markdown(
    spec: Any,
    raw_cases: Any,
    raw_scenes: Any,
    script: Any = "",
    summary: Optional[str] = None,
    execution: Any = None,
    link_plan: Any = None,
    suite: Any = None,
    report: Any = None,
) -> str:
    normalized_spec = _normalize_api_test_spec(spec)
    cases = [
        normalize_api_test_case(item)
        for item in raw_cases
        if isinstance(item, dict)
    ] if isinstance(raw_cases, list) else []
    scenes = [
        normalize_api_test_scene(item)
        for item in raw_scenes
        if isinstance(item, dict)
    ] if isinstance(raw_scenes, list) else []
    normalized_execution = normalize_api_test_execution(execution)
    normalized_script = _normalize_script_content(script)
    normalized_link_plan = normalize_api_test_link_plan(link_plan)
    normalized_suite = normalize_api_test_suite(suite)
    normalized_report = normalize_api_test_report(report)
    normalized_summary = _as_text(summary) or (
        f"已识别 {len(normalized_spec['operations'])} 个接口，生成 {len(cases)} 条结构化用例和 {len(scenes)} 个关联场景。"
    )

    auth_profile = normalized_spec.get("auth_profile") or {}
    required_headers = auth_profile.get("required_headers") or []
    required_cookies = auth_profile.get("required_cookies") or []

    sections: List[str] = ["# 接口测试资产", ""]
    if normalized_summary:
        sections.extend([f"> {normalized_summary}", ""])

    sections.extend(["## 规范概览", ""])
    sections.append(f"- 标题：{_as_text(normalized_spec.get('title'), '未命名接口文档') or '未命名接口文档'}")
    if _as_text(normalized_spec.get("version")):
        sections.append(f"- 文档版本：{_as_text(normalized_spec.get('version'))}")
    if _as_text(normalized_spec.get("openapi_version")):
        sections.append(f"- OpenAPI 版本：{_as_text(normalized_spec.get('openapi_version'))}")
    sections.append(f"- 接口数量：{len(normalized_spec.get('operations') or [])}")

    servers = normalized_spec.get("servers") or []
    if servers:
        sections.append("- 服务地址：")
        for server in servers:
            if not isinstance(server, dict):
                continue
            server_url = _as_text(server.get("url"))
            if not server_url:
                continue
            description = _as_text(server.get("description"))
            if description:
                sections.append(f"  - {server_url}（{description}）")
            else:
                sections.append(f"  - {server_url}")
    sections.append("")

    sections.extend(["## 鉴权信息", ""])
    if required_headers:
        sections.append(f"- 必填请求头：{', '.join(required_headers)}")
    else:
        sections.append("- 必填请求头：无")
    if required_cookies:
        sections.append(f"- 必填 Cookie：{', '.join(required_cookies)}")
    else:
        sections.append("- 必填 Cookie：无")
    sections.append("")

    sections.extend(["## 资源分组", ""])
    resources = normalized_spec.get("resources") or []
    if resources:
        for resource in resources:
            if not isinstance(resource, dict):
                continue
            resource_key = _as_text(resource.get("resource_key"), "未命名资源") or "未命名资源"
            resource_tag = _as_text(resource.get("tag"))
            sections.append(f"### {resource_key}")
            if resource_tag:
                sections.append(f"- 资源名称：{resource_tag}")
            lookup_fields = resource.get("lookup_fields") or []
            sections.append(f"- 回查字段：{', '.join(lookup_fields) if lookup_fields else '无'}")
            operation_ids = resource.get("operation_ids") or []
            if operation_ids:
                sections.append("- 关联接口：")
                for operation_id in operation_ids:
                    sections.append(f"  - {operation_id}")
            sections.append("")
    else:
        sections.extend(["- 未识别到资源分组。", ""])

    sections.extend(["## 用例清单", ""])
    if cases:
        for case in cases:
            sections.append(f"### {case['case_id']}")
            sections.append(f"- 标题：{case['title']}")
            sections.append(f"- 接口：{case['operation_id'] or '未绑定'}")
            sections.append(f"- 分类：{case['category']}")
            sections.append(f"- 优先级：{case['priority']}")
            sections.append(f"- 前置依赖：{', '.join(case['depends_on']) if case['depends_on'] else '无'}")
            if case["extract"]:
                sections.append("- 提取规则：")
                for item in case["extract"]:
                    sections.append(
                        f"  - {item['name'] or '未命名变量'} <- {item['from'] or 'response'} / {item['pick'] or '未指定路径'}"
                    )
            if case["assertions"]:
                sections.append("- 断言：")
                for assertion in case["assertions"]:
                    sections.append(f"  - {assertion}")
            sections.append("")
    else:
        sections.extend(["- 未生成结构化用例。", ""])

    sections.extend(["## 关联场景", ""])
    if scenes:
        for scene in scenes:
            sections.append(f"### {scene['scene_id']}")
            sections.append(f"- 标题：{scene['title']}")
            if scene["description"]:
                sections.append(f"- 描述：{scene['description']}")
            sections.append("- 步骤：")
            for index, step in enumerate(scene["steps"], start=1):
                sections.append(f"  {index}. {step}")
            sections.append("")
    else:
        sections.extend(["- 未生成关联场景。", ""])

    if normalized_link_plan:
        sections.extend(["## 关联编排", ""])
        ordered_case_ids = normalized_link_plan.get("ordered_case_ids") or []
        sections.append(f"- 执行顺序：{', '.join(ordered_case_ids) if ordered_case_ids else '未生成'}")
        standalone_case_ids = normalized_link_plan.get("standalone_case_ids") or []
        sections.append(f"- 独立用例：{', '.join(standalone_case_ids) if standalone_case_ids else '无'}")
        extract_variables = normalized_link_plan.get("extract_variables") or {}
        if extract_variables:
            sections.append("- 提取变量：")
            for variable_name, provider_cases in extract_variables.items():
                sections.append(f"  - {variable_name} <- {', '.join(provider_cases)}")
        scene_orders = normalized_link_plan.get("scene_orders") or []
        if scene_orders:
            sections.append("- 场景顺序：")
            for item in scene_orders:
                sections.append(f"  - {item['scene_id']}：{', '.join(item.get('ordered_steps') or [])}")
        if normalized_link_plan.get("warnings"):
            sections.append("- 编排告警：")
            for warning in normalized_link_plan.get("warnings") or []:
                sections.append(f"  - {warning}")
        sections.append("")

    sections.extend(["## 生成脚本", ""])
    sections.append("```python")
    sections.append(normalized_script or "# 暂未生成脚本")
    sections.append("```")

    if normalized_suite:
        sections.extend(["", "## 套件沉淀", ""])
        if normalized_suite.get("suite_id"):
            sections.append(f"- 套件 ID：{normalized_suite['suite_id']}")
        if normalized_suite.get("suite_version"):
            sections.append(f"- 套件版本：v{int(normalized_suite['suite_version']):03d}")
        sections.append(f"- 用例数量：{int(normalized_suite.get('case_count') or 0)}")
        sections.append(f"- 场景数量：{int(normalized_suite.get('scene_count') or 0)}")
        if normalized_suite.get("storage_path"):
            sections.append(f"- 存储路径：{normalized_suite['storage_path']}")

    if normalized_execution:
        stats = normalized_execution.get("stats") or {}
        artifacts = normalized_execution.get("artifacts") or {}
        sections.extend(["", "## 执行结果", ""])
        if normalized_execution.get("status"):
            sections.append(f"- 执行状态：{normalized_execution['status']}")
        if normalized_execution.get("summary"):
            sections.append(f"- 执行摘要：{normalized_execution['summary']}")
        sections.append(
            f"- 统计结果：总数 {stats.get('total', 0)}，通过 {stats.get('passed', 0)}，失败 {stats.get('failed', 0)}，异常 {stats.get('errors', 0)}，跳过 {stats.get('skipped', 0)}"
        )
        if normalized_execution.get("command"):
            sections.append(f"- 执行命令：`{normalized_execution['command']}`")
        if artifacts.get("run_dir"):
            sections.append(f"- 运行目录：{artifacts['run_dir']}")
        if artifacts.get("junit_xml"):
            sections.append(f"- JUnit 报告：{artifacts['junit_xml']}")

    if normalized_report:
        sections.extend(["", "## 执行报告", ""])
        if normalized_report.get("headline"):
            sections.append(f"- 标题：{normalized_report['headline']}")
        for summary_line in normalized_report.get("summary_lines") or []:
            sections.append(f"- {summary_line}")
        if normalized_report.get("failure_cases"):
            sections.append("- 失败明细：")
            for item in normalized_report.get("failure_cases") or []:
                sections.append(f"  - {item['title']} [{item['kind']}]：{item['detail']}")
        if normalized_report.get("artifact_labels"):
            sections.append("- 报告产物：")
            for item in normalized_report.get("artifact_labels") or []:
                sections.append(f"  - {item['label']}：{item['value']}")

    warnings = normalized_spec.get("warnings") or []
    if warnings:
        sections.extend(["", "## 识别告警", ""])
        sections.extend([f"- {warning}" for warning in warnings])

    return "\n".join(sections).strip() + "\n"


def build_api_test_pack(
    spec: Any,
    raw_cases: Any,
    raw_scenes: Any,
    script: Any = "",
    summary: Optional[str] = None,
    execution: Any = None,
    link_plan: Any = None,
    suite: Any = None,
    report: Any = None,
) -> Dict[str, Any]:
    normalized_spec = _normalize_api_test_spec(spec)
    cases = [
        normalize_api_test_case(item)
        for item in raw_cases
        if isinstance(item, dict)
    ] if isinstance(raw_cases, list) else []
    scenes = [
        normalize_api_test_scene(item)
        for item in raw_scenes
        if isinstance(item, dict)
    ] if isinstance(raw_scenes, list) else []
    normalized_summary = _as_text(summary) or (
        f"已识别 {len(normalized_spec['operations'])} 个接口，生成 {len(cases)} 条结构化用例和 {len(scenes)} 个关联场景。"
    )
    normalized_script = _normalize_script_content(script)
    normalized_execution = normalize_api_test_execution(execution)
    normalized_link_plan = normalize_api_test_link_plan(link_plan)
    normalized_suite = normalize_api_test_suite(suite)
    normalized_report = normalize_api_test_report(report)

    return {
        "summary": normalized_summary,
        "spec": normalized_spec,
        "cases": cases,
        "scenes": scenes,
        "script": normalized_script,
        "execution": normalized_execution,
        "link_plan": normalized_link_plan,
        "suite": normalized_suite,
        "report": normalized_report,
        "markdown": build_api_test_markdown(
            spec=normalized_spec,
            raw_cases=cases,
            raw_scenes=scenes,
            script=normalized_script,
            summary=normalized_summary,
            execution=normalized_execution,
            link_plan=normalized_link_plan,
            suite=normalized_suite,
            report=normalized_report,
        ),
    }


def to_export_case(raw_case: Dict[str, Any], default_module: str = "") -> Dict[str, Any]:
    normalized = normalize_case_item(raw_case, default_module=default_module)
    return {
        "module": normalized["module"],
        "name": normalized["title"],
        "precondition": normalized["precondition"],
        "priority": normalized["priority"],
        "tags": "",
        "remark": "",
        "steps": [
            {
                "step": _as_text(step.get("action")),
                "expected": _as_text(step.get("expected"))
            }
            for step in normalized["steps"]
        ]
    }


def to_export_cases(raw_items: Any, default_module: str = "") -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [to_export_case(item, default_module=default_module) for item in raw_items if isinstance(item, dict)]


def sanitize_review_reports(raw_reports: Any) -> Dict[str, Dict[str, str]]:
    if not isinstance(raw_reports, dict):
        return {}

    sanitized: Dict[str, Dict[str, str]] = {}
    for key, report in raw_reports.items():
        if isinstance(report, dict):
            label = _as_text(report.get("label"), _as_text(key, "评审报告")) or "评审报告"
            content = strip_findings_json_block(report.get("content"))
        else:
            label = _as_text(key, "评审报告") or "评审报告"
            content = strip_findings_json_block(report)

        sanitized[_as_text(key)] = {
            "label": label,
            "content": content
        }

    return sanitized


def normalize_review_risk_level(raw_value: Any, default: str = "M") -> str:
    text = _as_text(raw_value, default).upper()
    if text in {"H", "M", "L"}:
        return text
    if text in {"HIGH", "P0", "CRITICAL"}:
        return "H"
    if text in {"LOW", "P3", "INFO"}:
        return "L"
    return "M"


def normalize_review_finding(raw_finding: Any) -> Dict[str, Any]:
    if not isinstance(raw_finding, dict):
        raw_finding = {}

    return {
        "risk_level": normalize_review_risk_level(raw_finding.get("risk_level")),
        "category": _as_text(raw_finding.get("category"), "待分类") or "待分类",
        "description": _as_text(raw_finding.get("description"), "未提供风险描述") or "未提供风险描述",
        "source_quote": _as_text(raw_finding.get("source_quote") or raw_finding.get("quote") or raw_finding.get("source")),
        "suggestion": _as_text(raw_finding.get("suggestion")),
    }


def normalize_review_findings(raw_findings: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_findings, list):
        return []
    return [normalize_review_finding(item) for item in raw_findings if isinstance(item, dict)]


def build_review_markdown(reports: Any, findings: Any) -> str:
    normalized_reports = sanitize_review_reports(reports)
    sections: List[str] = ["# 智能需求评审报告", ""]

    for report in normalized_reports.values():
        label = _as_text(report.get("label"), "评审报告") or "评审报告"
        content = _as_text(report.get("content"))
        if not content:
            continue
        sections.extend([f"## {label}", "", content, ""])

    normalized_findings = normalize_review_findings(findings)
    if normalized_findings:
        sections.extend(["## 风险看板", ""])
        for index, finding in enumerate(normalized_findings, start=1):
            sections.append(f"{index}. [{finding['risk_level']}] {finding['category']}：{finding['description']}")
            if finding["source_quote"]:
                sections.append(f"   - 原文：{finding['source_quote']}")
            suggestion = finding["suggestion"]
            if suggestion:
                sections.append(f"   - 建议：{suggestion}")
            sections.append("")

    return "\n".join(sections).strip() + "\n"


def normalize_test_case_review_risk_level(raw_value: Any, default: str = "M") -> str:
    text = _as_text(raw_value, default).upper()
    if text in {"H", "M", "L"}:
        return text
    if text in {"HIGH", "P0", "CRITICAL"}:
        return "H"
    if text in {"LOW", "P3", "INFO"}:
        return "L"
    return "M"


def normalize_test_case_review_finding(raw_finding: Any) -> Dict[str, Any]:
    if not isinstance(raw_finding, dict):
        raw_finding = {}

    return {
        "risk_level": normalize_test_case_review_risk_level(raw_finding.get("risk_level")),
        "category": _as_text(raw_finding.get("category"), "待分类") or "待分类",
        "related_case_ids": _normalize_text_list(raw_finding.get("related_case_ids")),
        "related_requirement_points": _normalize_text_list(raw_finding.get("related_requirement_points")),
        "description": _as_text(raw_finding.get("description"), "未提供问题描述") or "未提供问题描述",
        "suggestion": _as_text(raw_finding.get("suggestion"), "待补充修订建议") or "待补充修订建议",
    }


def normalize_test_case_review_item(raw_item: Any) -> Dict[str, Any]:
    if not isinstance(raw_item, dict):
        raw_item = {}

    verdict = _as_text(raw_item.get("verdict"), "warning").lower()
    if verdict not in {"pass", "warning", "fail"}:
        verdict = "warning"

    consistency = _as_text(raw_item.get("consistency"), "partial").lower()
    if consistency not in {"aligned", "partial", "deviated"}:
        consistency = "partial"

    return {
        "case_id": _as_text(raw_item.get("case_id") or raw_item.get("id")) or str(uuid.uuid4()),
        "title": _as_text(raw_item.get("title") or raw_item.get("name"), "未命名用例") or "未命名用例",
        "module": _as_text(raw_item.get("module"), "未分类") or "未分类",
        "verdict": verdict,
        "consistency": consistency,
        "issues": _normalize_text_list(raw_item.get("issues")),
        "suggestions": _normalize_text_list(raw_item.get("suggestions")),
    }


def build_test_case_review_markdown(payload: Any) -> str:
    if not isinstance(payload, dict):
        payload = {}

    summary = _as_text(payload.get("summary")) or "已完成测试用例评审。"
    findings = [
        normalize_test_case_review_finding(item)
        for item in (payload.get("findings") or [])
        if isinstance(item, dict)
    ]
    reviewed_cases = [
        normalize_test_case_review_item(item)
        for item in (payload.get("reviewed_cases") or [])
        if isinstance(item, dict)
    ]
    revised_suite_raw = payload.get("revised_suite") or {}
    if isinstance(revised_suite_raw, dict):
        revised_suite = build_case_suite(
            revised_suite_raw.get("items") or [],
            summary=_as_text(revised_suite_raw.get("summary")) or "修订建议版测试用例。",
        )
    else:
        revised_suite = build_case_suite([], summary="修订建议版测试用例。")

    sections: List[str] = ["# 测试用例评审报告", "", f"> {summary}", ""]

    if findings:
        sections.extend(["## 问题清单", ""])
        for index, finding in enumerate(findings, start=1):
            sections.append(f"{index}. [{finding['risk_level']}][{finding['category']}] {finding['description']}")
            if finding["related_requirement_points"]:
                sections.append(f"   - 对应需求点：{'；'.join(finding['related_requirement_points'])}")
            if finding["related_case_ids"]:
                sections.append(f"   - 关联用例：{'；'.join(finding['related_case_ids'])}")
            if finding["suggestion"]:
                sections.append(f"   - 建议：{finding['suggestion']}")
            sections.append("")

    if reviewed_cases:
        sections.extend(["## 逐条评审结论", ""])
        for item in reviewed_cases:
            sections.append(
                f"- [{item['verdict']}][{item['consistency']}] {item['module']} / {item['title']}"
            )
            if item["issues"]:
                sections.append(f"  - 问题：{'；'.join(item['issues'])}")
            if item["suggestions"]:
                sections.append(f"  - 建议：{'；'.join(item['suggestions'])}")
        sections.append("")

    sections.extend([
        "## 修订建议版测试用例",
        "",
        build_case_suite_markdown(revised_suite).strip(),
        "",
    ])

    return "\n".join(sections).strip() + "\n"


def build_test_case_review_payload(
    summary: str,
    findings: Any,
    reviewed_cases: Any,
    revised_suite: Any,
    markdown: str = "",
) -> Dict[str, Any]:
    normalized_findings = [
        normalize_test_case_review_finding(item)
        for item in (findings or [])
        if isinstance(item, dict)
    ]
    normalized_reviewed_cases = [
        normalize_test_case_review_item(item)
        for item in (reviewed_cases or [])
        if isinstance(item, dict)
    ]

    default_suite_summary = _as_text(summary) or "修订建议版测试用例。"
    if isinstance(revised_suite, dict) and isinstance(revised_suite.get("items"), list):
        normalized_revised_suite = build_case_suite(
            revised_suite.get("items") or [],
            summary=_as_text(revised_suite.get("summary")) or default_suite_summary,
        )
    else:
        normalized_revised_suite = build_case_suite(
            revised_suite or [],
            summary=default_suite_summary,
        )

    payload = {
        "summary": _as_text(summary) or "已完成测试用例评审。",
        "findings": normalized_findings,
        "reviewed_cases": normalized_reviewed_cases,
        "revised_suite": normalized_revised_suite,
    }
    payload["markdown"] = _as_text(markdown) or build_test_case_review_markdown(payload)
    return payload
