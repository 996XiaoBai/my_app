from typing import Any, Dict, List
from xml.etree import ElementTree as ET


class ApiReportService:
    """负责将接口执行结果整理为稳定的结构化报告。"""

    ARTIFACT_LABELS = {
        "compiled_script": "执行脚本",
        "generated_script": "生成脚本",
        "junit_xml": "JUnit 报告",
        "execution_summary": "执行摘要",
        "runtime_config": "运行配置",
        "asset_snapshot": "资产快照",
        "case_snapshot": "用例快照",
        "scene_snapshot": "场景快照",
        "allure_results": "Allure 原始结果",
        "allure_archive": "Allure 压缩包",
        "run_dir": "运行目录",
    }
    ARTIFACT_ORDER = (
        "compiled_script",
        "generated_script",
        "junit_xml",
        "execution_summary",
        "runtime_config",
        "asset_snapshot",
        "case_snapshot",
        "scene_snapshot",
        "allure_results",
        "allure_archive",
        "run_dir",
    )
    STATUS_LABELS = {
        "passed": "执行通过",
        "failed": "执行失败",
        "error": "执行异常",
        "not_executed": "未执行",
    }

    def build_report(
        self,
        spec: Dict[str, Any],
        cases: List[Dict[str, Any]],
        scenes: List[Dict[str, Any]],
        execution: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_execution = execution if isinstance(execution, dict) else {}
        stats = normalized_execution.get("stats") if isinstance(normalized_execution.get("stats"), dict) else {}
        artifacts = normalized_execution.get("artifacts") if isinstance(normalized_execution.get("artifacts"), dict) else {}
        status = str(normalized_execution.get("status") or "").strip().lower() or "not_executed"
        title = str((spec or {}).get("title") or "未命名接口套件").strip() or "未命名接口套件"

        summary_lines = [
            f"总 {int(stats.get('total') or 0)} / 通过 {int(stats.get('passed') or 0)} / 失败 {int(stats.get('failed') or 0)} / 异常 {int(stats.get('errors') or 0)} / 跳过 {int(stats.get('skipped') or 0)}",
            f"结构化用例 {len(cases or [])} 条 / 关联场景 {len(scenes or [])} 个",
        ]
        execution_summary = str(normalized_execution.get("summary") or "").strip()
        if execution_summary:
            summary_lines.append(execution_summary)

        return {
            "status": status,
            "headline": f"{title}：{self.STATUS_LABELS.get(status, '未执行')}",
            "summary_lines": summary_lines,
            "failure_cases": self._extract_failure_cases(str(normalized_execution.get("junit_xml_content") or "")),
            "artifact_labels": self._build_artifact_labels(artifacts),
        }

    def _build_artifact_labels(self, artifacts: Dict[str, Any]) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        for key in self.ARTIFACT_ORDER:
            value = str(artifacts.get(key) or "").strip()
            if not value:
                continue
            items.append(
                {
                    "key": key,
                    "label": self.ARTIFACT_LABELS.get(key, key),
                    "value": value,
                }
            )
        return items

    def _extract_failure_cases(self, junit_xml_content: str) -> List[Dict[str, str]]:
        text = str(junit_xml_content or "").strip()
        if not text:
            return []

        try:
            root = ET.fromstring(text)
        except Exception:
            return []

        suite_nodes: List[ET.Element] = []
        if root.tag == "testsuite":
            suite_nodes = [root]
        elif root.tag == "testsuites":
            suite_nodes = [node for node in root if node.tag == "testsuite"]

        failure_cases: List[Dict[str, str]] = []
        failure_index = 0
        for suite in suite_nodes:
            for testcase in suite.findall("testcase"):
                case_name = str(testcase.attrib.get("name") or "").strip()
                class_name = str(testcase.attrib.get("classname") or "").strip()
                title = f"{class_name}::{case_name}".strip(":")
                for child_name, kind in (("failure", "failure"), ("error", "error")):
                    child_node = testcase.find(child_name)
                    if child_node is None:
                        continue
                    failure_cases.append(
                        {
                            "key": f"{kind}-{failure_index}",
                            "title": title,
                            "detail": str(child_node.attrib.get("message") or child_node.text or "").strip() or child_name,
                            "kind": kind,
                        }
                    )
                    failure_index += 1
        return failure_cases
