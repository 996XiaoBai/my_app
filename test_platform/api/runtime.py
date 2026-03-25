import datetime
import json
import logging
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import UploadFile

from test_platform.config import AgentConfig
from test_platform.core.services.progress_event_service import normalize_mode
from test_platform.core.services.weekly_report_service import WeeklyReportService
from test_platform.core.skill_modes import SkillMode
from test_platform.infrastructure.feishu_client import FeishuClient


logger = logging.getLogger(__name__)

TEMP_DIR_PREFIXES = ("qa_wb_", "qa_rec_")


class InvalidJsonPayloadError(ValueError):
    def __init__(self, field_name: str, message: Optional[str] = None):
        self.field_name = field_name
        super().__init__(message or f"{field_name} must be valid JSON")


@dataclass
class ApiServices:
    review_service: Any
    history_report_service: Any
    weekly_report_service: Optional[WeeklyReportService]
    db_manager: Any


@dataclass
class SkillExecutionResult:
    normalized_mode: str
    result: str
    context_id: Optional[str]
    cache_hit: bool
    meta: Dict[str, Any]


def create_weekly_report_service(review_service: Any) -> Optional[WeeklyReportService]:
    try:
        feishu_client = FeishuClient(
            app_id=AgentConfig.FEISHU_APP_ID,
            app_secret=AgentConfig.FEISHU_APP_SECRET,
            folder_token=AgentConfig.FEISHU_WEEKLY_REPORT_FOLDER_TOKEN or AgentConfig.FEISHU_FOLDER_TOKEN,
        )
        return WeeklyReportService(
            dify_client=review_service.client,
            feishu_client=feishu_client,
            config=AgentConfig,
        )
    except Exception:
        logger.exception("Failed to initialize weekly report service")
        return None


def parse_json_mapping(raw_value: Optional[str], field_name: str = "params") -> Dict[str, Any]:
    if not raw_value:
        return {}

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise InvalidJsonPayloadError(field_name, f"{field_name} 必须是合法的 JSON 对象") from error
    if isinstance(parsed, dict):
        return parsed

    raise InvalidJsonPayloadError(field_name, f"{field_name} 必须是 JSON 对象")


def parse_json_string_list(raw_value: Optional[str], field_name: str = "roles") -> Optional[List[str]]:
    if not raw_value:
        return None

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise InvalidJsonPayloadError(field_name, f"{field_name} 必须是合法的 JSON 数组") from error
    if not isinstance(parsed, list):
        raise InvalidJsonPayloadError(field_name, f"{field_name} 必须是 JSON 数组")

    return [str(item) for item in parsed]


def truncate_text(value: Any, limit: int) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return "".join(character for index, character in enumerate(text) if index < limit)


def resolve_source_name(file_path: Optional[str], requirement: str) -> str:
    if file_path:
        return os.path.basename(file_path)
    lines = [line.strip() for line in str(requirement or "").splitlines() if line.strip()]
    if lines:
        return truncate_text(lines[0], 40)
    return ""


def create_temp_dir(prefix: str) -> str:
    temp_dir = os.path.join(tempfile.gettempdir(), f"{prefix}{uuid.uuid4()}")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def cleanup_temp_dir(temp_dir: Optional[str]) -> None:
    if not temp_dir:
        return

    base_name = os.path.basename(temp_dir.rstrip(os.sep))
    if not any(base_name.startswith(prefix) for prefix in TEMP_DIR_PREFIXES):
        logger.warning("Skip cleanup for unexpected temp dir: %s", temp_dir)
        return

    shutil.rmtree(temp_dir, ignore_errors=True)


def store_uploads(files: Optional[List[UploadFile]], temp_dir: str) -> Tuple[Optional[str], List[str]]:
    main_file_path = None
    uploaded_paths: List[str] = []

    if files:
        for idx, file in enumerate(files):
            safe_name = os.path.basename(file.filename or f"upload_{idx}")
            file_path = os.path.join(temp_dir, safe_name)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_paths.append(file_path)
            if idx == 0:
                main_file_path = file_path

    return main_file_path, uploaded_paths


def build_recommendation_content(requirement: str, files: Optional[List[UploadFile]], temp_dir: str) -> str:
    content = requirement
    if not files or content:
        return content

    main_file_path, _ = store_uploads(files[:1], temp_dir)
    if not main_file_path:
        return content

    if not main_file_path.lower().endswith(".pdf"):
        return content

    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(main_file_path) as pdf:
            texts = [page.extract_text() or "" for page in pdf.pages[:3]]
            return "\n".join(texts)[:2000]
    except Exception as error:
        logger.error("PDF extraction for recommendation failed: %s", error)
        return content


def build_weekly_report_title() -> str:
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())
    week_end = week_start + datetime.timedelta(days=4)
    return f"软件测试周报 {week_start.strftime('%Y-%m-%d')} — {week_end.strftime('%Y-%m-%d')}"


def execute_weekly_report(
    weekly_report_service: Optional[WeeklyReportService],
    requirement: str,
    image_paths: List[str],
    extra_prompt: str,
    params: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    if not weekly_report_service:
        raise RuntimeError("周报服务未初始化")

    combined_requirement = requirement or ""
    if extra_prompt:
        combined_requirement = f"{combined_requirement}\n\n【附加要求】{extra_prompt}".strip()

    summary_md = weekly_report_service.summarize_report(combined_requirement, image_paths)
    if not summary_md:
        raise RuntimeError("周报总结失败")

    publish_to_feishu = bool(params.get("publish_to_feishu", True))
    report_title = str(params.get("report_title") or build_weekly_report_title())
    feishu_url = None

    if publish_to_feishu:
        try:
            feishu_url = weekly_report_service.export_to_feishu(report_title, summary_md)
        except Exception:
            logger.exception("Failed to export weekly report to Feishu")

    return summary_md, {
        "title": report_title,
        "feishu_url": feishu_url,
        "published_to_feishu": bool(feishu_url),
        "publish_requested": publish_to_feishu,
    }


def resolve_prepared_context(
    review_service: Any,
    mode: str,
    requirement: str,
    file_path: Optional[str],
    context_id: Optional[str],
    historical_findings: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
    prepared_context = None
    resolved_context_id = context_id
    cache_hit = False

    has_fresh_input = bool(str(requirement or "").strip()) or bool(file_path)
    skip_module_split = normalize_mode(mode) == SkillMode.TEST_DATA

    if has_fresh_input:
        prepared_context = review_service.prepare_context(
            requirement=requirement,
            file_path=file_path,
            skip_module_split=skip_module_split,
        )
        resolved_context_id = prepared_context.get("context_id")
    elif context_id:
        prepared_context = review_service.get_context(context_id)
        if not prepared_context and (requirement or file_path):
            prepared_context = review_service.prepare_context(
                requirement=requirement,
                file_path=file_path,
                skip_module_split=skip_module_split,
            )
            resolved_context_id = prepared_context.get("context_id")
    elif requirement or file_path:
        prepared_context = review_service.prepare_context(
            requirement=requirement,
            file_path=file_path,
            skip_module_split=skip_module_split,
        )
        resolved_context_id = prepared_context.get("context_id")

    if prepared_context:
        cache_hit = bool(prepared_context.get("cache_hit"))
        if historical_findings:
            prepared_context["historical_findings"] = historical_findings

    return prepared_context, resolved_context_id, cache_hit


def execute_skill_request(
    services: ApiServices,
    mode: str,
    requirement: str,
    params: Dict[str, Any],
    roles: Optional[List[str]],
    extra_prompt: str,
    historical_findings: Optional[str],
    context_id: Optional[str],
    main_file_path: Optional[str],
    uploaded_paths: List[str],
    status_callback: Optional[Callable[[str], None]] = None,
) -> SkillExecutionResult:
    normalized_mode = normalize_mode(mode)
    result_meta: Dict[str, Any] = {}

    if normalized_mode == SkillMode.WEEKLY_REPORT:
        result, result_meta = execute_weekly_report(
            weekly_report_service=services.weekly_report_service,
            requirement=requirement,
            image_paths=uploaded_paths,
            extra_prompt=extra_prompt or "",
            params=params,
        )
        return SkillExecutionResult(
            normalized_mode=normalized_mode,
            result=result,
            context_id=context_id,
            cache_hit=False,
            meta=result_meta,
        )

    prepared_context, resolved_context_id, cache_hit = resolve_prepared_context(
        review_service=services.review_service,
        mode=normalized_mode,
        requirement=requirement,
        file_path=main_file_path,
        context_id=context_id,
        historical_findings=historical_findings,
    )
    if prepared_context is not None:
        prepared_context["uploaded_paths"] = uploaded_paths
        prepared_context["main_file_path"] = main_file_path

    result = services.review_service.run_review(
        requirement=requirement,
        file_path=main_file_path,
        mode=normalized_mode,
        roles=roles,
        preparsed_data=prepared_context,
        context_id=resolved_context_id,
        status_callback=status_callback,
        params=params,
        extra_prompt=extra_prompt,
    )

    return SkillExecutionResult(
        normalized_mode=normalized_mode,
        result=result,
        context_id=resolved_context_id,
        cache_hit=cache_hit,
        meta=result_meta,
    )


def persist_execution_result(
    services: ApiServices,
    execution: SkillExecutionResult,
    requirement: str,
    main_file_path: Optional[str],
    roles: Optional[List[str]],
    params: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        saved_path = services.history_report_service.save_execution_result(
            mode=execution.normalized_mode,
            result=execution.result,
            requirement=requirement,
            source_name=resolve_source_name(main_file_path, requirement),
            meta={
                "mode": normalize_mode(execution.normalized_mode),
                "context_id": execution.context_id,
                "cache_hit": execution.cache_hit,
                "roles": roles or [],
                "has_file": bool(main_file_path),
                "params": params or {},
            },
        )
        if saved_path:
            execution.meta["history_report_id"] = os.path.splitext(os.path.basename(saved_path))[0]
    except Exception:
        logger.exception("Failed to persist history report")


def generate_dynamic_insight(services: ApiServices, mode: str, result: str) -> Optional[str]:
    if normalize_mode(mode) in {
        SkillMode.WEEKLY_REPORT,
        SkillMode.AUTO_SCRIPT_GEN,
        SkillMode.API_TEST_GEN,
        SkillMode.API_PERF_TEST,
    }:
        return None

    return services.review_service.generate_dynamic_insight(truncate_text(result, 5000))
