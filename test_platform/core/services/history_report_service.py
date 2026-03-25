import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from test_platform.core.services.progress_event_service import normalize_mode
from test_platform.core.services.result_contracts import (
    build_case_suite_markdown,
    build_flowchart_markdown,
    build_requirement_analysis_markdown,
    build_review_markdown,
    build_test_case_review_markdown,
)
from test_platform.utils.history_manager import HistoryManager


PERSISTED_HISTORY_MODES = {
    "review",
    "test_case",
    "test_case_review",
    "req_analysis",
    "test_point",
    "impact_analysis",
    "test_plan",
    "test_data",
    "log_diagnosis",
    "flowchart",
    "api_test_gen",
    "api_perf_test_gen",
    "auto_script_gen",
    "weekly_report",
}


class HistoryReportService:
    """负责执行结果的历史落盘与查询。"""

    def __init__(self, base_dir: Optional[str] = None, history_manager: Optional[HistoryManager] = None):
        if history_manager is not None:
            self.history_manager = history_manager
        elif base_dir:
            self.history_manager = HistoryManager(base_dir=base_dir)
        else:
            self.history_manager = HistoryManager()

    def build_history_content(self, mode: str, result: Any) -> str:
        normalized_mode = normalize_mode(mode)
        text_result = str(result or "")
        if not text_result:
            return ""

        payload = self._load_json_payload(text_result)

        if normalized_mode == "review" and isinstance(payload, dict):
            markdown = str(payload.get("markdown") or "").strip()
            if markdown:
                return markdown if markdown.endswith("\n") else markdown + "\n"
            return build_review_markdown(payload.get("reports"), payload.get("findings"))

        if normalized_mode == "test_case" and isinstance(payload, dict):
            return build_case_suite_markdown(payload)

        if normalized_mode == "test_case_review" and isinstance(payload, dict):
            markdown = str(payload.get("markdown") or "").strip()
            if markdown:
                return markdown if markdown.endswith("\n") else markdown + "\n"
            return build_test_case_review_markdown(payload)

        if normalized_mode == "req_analysis" and isinstance(payload, dict):
            markdown = str(payload.get("markdown") or "").strip()
            if markdown:
                return markdown if markdown.endswith("\n") else markdown + "\n"
            return build_requirement_analysis_markdown(payload)

        if normalized_mode == "flowchart" and isinstance(payload, dict):
            markdown = str(payload.get("markdown") or "").strip()
            if markdown:
                return markdown if markdown.endswith("\n") else markdown + "\n"
            return build_flowchart_markdown(payload)

        if normalized_mode == "test_data" and isinstance(payload, dict):
            markdown = str(payload.get("markdown") or "").strip()
            if markdown:
                return markdown if markdown.endswith("\n") else markdown + "\n"

        if normalized_mode == "api_test_gen" and isinstance(payload, dict):
            markdown = str(payload.get("markdown") or "").strip()
            if markdown:
                return markdown if markdown.endswith("\n") else markdown + "\n"

        return text_result.strip() + ("\n" if not text_result.endswith("\n") else "")

    def save_execution_result(
        self,
        mode: str,
        result: Any,
        requirement: str = "",
        source_name: str = "",
        meta: Optional[Dict[str, Any]] = None,
    ) -> str:
        normalized_mode = normalize_mode(mode)
        if normalized_mode not in PERSISTED_HISTORY_MODES:
            return ""

        content = self.build_history_content(normalized_mode, result)
        if not content.strip():
            return ""

        merged_meta = {
            "mode": normalized_mode,
            **(meta or {}),
        }
        if normalized_mode == "api_test_gen":
            merged_meta = {
                **merged_meta,
                **self._build_api_test_history_meta(result),
            }
        filename = source_name or self._build_source_name(requirement, normalized_mode)
        return self.history_manager.save_report(
            content=content,
            filename=filename,
            report_type=normalized_mode,
            meta=merged_meta,
        )

    def list_reports(self, report_types: Optional[List[str]] = None, limit: int = 20) -> List[Dict[str, Any]]:
        normalized_types = None
        if report_types:
            normalized_types = {normalize_mode(report_type) for report_type in report_types if report_type}

        raw_reports = self.history_manager.list_reports(limit=max(limit * 3, limit, 20))
        items: List[Dict[str, Any]] = []

        for report in raw_reports:
            report_type = str(report.get("type") or "")
            if normalized_types and report_type not in normalized_types:
                continue

            items.append({
                "id": report.get("id"),
                "timestamp": report.get("timestamp"),
                "filename": report.get("filename"),
                "type": report_type,
                "meta": self._build_list_meta(report_type, report.get("meta") or {}),
            })

            if len(items) >= limit:
                break

        return items

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        safe_report_id = os.path.basename(str(report_id or "")).replace(".json", "")
        if not safe_report_id:
            return None

        file_path = os.path.join(self.history_manager.base_dir, f"{safe_report_id}.json")
        data = self.history_manager.load_report(file_path)
        if not data:
            return None

        return {
            "id": data.get("id"),
            "timestamp": data.get("timestamp"),
            "filename": data.get("filename"),
            "type": data.get("type"),
            "content": data.get("content", ""),
            "meta": data.get("meta") or {},
        }

    def get_report_artifact_path(self, report_id: str, artifact_key: str) -> Optional[str]:
        report = self.get_report(report_id)
        if not report:
            return None

        meta = report.get("meta")
        if not isinstance(meta, dict):
            return None

        pack_payload = meta.get("pack_payload")
        if not isinstance(pack_payload, dict):
            return None

        execution = pack_payload.get("execution")
        if not isinstance(execution, dict):
            return None

        artifacts = execution.get("artifacts")
        if not isinstance(artifacts, dict):
            return None

        artifact_path = str(artifacts.get(artifact_key) or "").strip()
        if not artifact_path:
            return None

        resolved_path = Path(artifact_path).resolve()
        allowed_root = Path(self.history_manager.base_dir).resolve()
        if allowed_root not in resolved_path.parents and resolved_path != allowed_root:
            return None
        if not resolved_path.is_file():
            return None
        return str(resolved_path)

    @staticmethod
    def _load_json_payload(text_result: str) -> Optional[Dict[str, Any]]:
        try:
            payload = json.loads(text_result)
        except (TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    def _build_api_test_history_meta(self, result: Any) -> Dict[str, Any]:
        payload = self._load_json_payload(str(result or ""))
        if not isinstance(payload, dict):
            return {}

        spec = payload.get("spec")
        cases = payload.get("cases")
        scenes = payload.get("scenes")
        script = payload.get("script")
        execution = payload.get("execution")
        link_plan = payload.get("link_plan")
        suite = payload.get("suite")
        report = payload.get("report")
        if not isinstance(spec, dict) or not isinstance(cases, list) or not isinstance(scenes, list):
            return {}

        return {
            "pack_payload": {
                "summary": str(payload.get("summary") or "").strip(),
                "spec": spec,
                "cases": cases,
                "scenes": scenes,
                "script": str(script or ""),
                "execution": execution if isinstance(execution, dict) else {},
                "link_plan": link_plan if isinstance(link_plan, dict) else {},
                "suite": suite if isinstance(suite, dict) else {},
                "report": report if isinstance(report, dict) else {},
            },
            "api_test_summary": self._build_api_test_summary(payload),
        }

    @staticmethod
    def _build_api_test_summary(payload: Dict[str, Any]) -> Dict[str, Any]:
        execution = payload.get("execution") if isinstance(payload.get("execution"), dict) else {}
        stats = execution.get("stats") if isinstance(execution.get("stats"), dict) else {}
        suite = payload.get("suite") if isinstance(payload.get("suite"), dict) else {}
        report = payload.get("report") if isinstance(payload.get("report"), dict) else {}
        spec = payload.get("spec") if isinstance(payload.get("spec"), dict) else {}
        total = int(stats.get("total") or 0)
        passed = int(stats.get("passed") or 0)
        failed = int(stats.get("failed") or 0)
        errors = int(stats.get("errors") or 0)
        skipped = int(stats.get("skipped") or 0)

        return {
            "spec_title": str(spec.get("title") or "").strip(),
            "suite_id": str(suite.get("suite_id") or "").strip(),
            "suite_version": int(suite.get("suite_version") or 0) if suite.get("suite_version") else None,
            "status": str(execution.get("status") or "").strip(),
            "case_count": len(payload.get("cases") or []) if isinstance(payload.get("cases"), list) else 0,
            "scene_count": len(payload.get("scenes") or []) if isinstance(payload.get("scenes"), list) else 0,
            "report_headline": str(report.get("headline") or "").strip(),
            "stats": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
            },
            "pass_rate": round((passed / total) * 100, 1) if total > 0 else None,
        }

    @staticmethod
    def _build_list_meta(report_type: str, meta: Dict[str, Any]) -> Dict[str, Any]:
        if report_type != "api_test_gen" or not isinstance(meta, dict):
            return {}

        api_test_summary = meta.get("api_test_summary")
        if not isinstance(api_test_summary, dict):
            return {}

        return {
            "api_test_summary": api_test_summary,
        }

    @staticmethod
    def _build_source_name(requirement: str, normalized_mode: str) -> str:
        lines = [line.strip() for line in str(requirement or "").splitlines() if line.strip()]
        if lines:
            return lines[0][:40]

        fallback_names = {
            "review": "需求评审",
            "test_case": "测试用例",
            "test_case_review": "测试用例评审",
            "req_analysis": "需求分析",
            "test_point": "测试点提取",
            "impact_analysis": "影响面分析",
            "test_plan": "测试方案",
            "test_data": "测试数据准备",
            "log_diagnosis": "日志诊断",
            "flowchart": "业务流程图",
            "api_test_gen": "接口测试",
            "api_perf_test_gen": "性能压测",
            "auto_script_gen": "UI自动化",
            "weekly_report": "测试周报",
        }
        return fallback_names.get(normalized_mode, normalized_mode)
