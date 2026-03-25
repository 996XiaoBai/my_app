import os
import sys
import shutil
import uuid
import json
import logging
import mimetypes
import tempfile
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from queue import Queue
from threading import Thread
from urllib.parse import quote

from fastapi import APIRouter, FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse

runtime_package_name = globals().get("__package__")
if not isinstance(runtime_package_name, str) or not runtime_package_name:
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from test_platform.api.runtime import (
    ApiServices,
    InvalidJsonPayloadError,
    SkillExecutionResult,
    create_weekly_report_service as create_runtime_weekly_report_service,
    execute_skill_request as execute_runtime_skill_request,
    generate_dynamic_insight as generate_runtime_dynamic_insight,
    parse_json_mapping as parse_runtime_json_mapping,
    parse_json_string_list as parse_runtime_json_string_list,
    persist_execution_result as persist_runtime_execution_result,
)
from test_platform.core.services.history_report_service import HistoryReportService
from test_platform.core.skill_modes import SkillMode
from test_platform.core.services.review_service import ReviewService
from test_platform.core.services.weekly_report_service import WeeklyReportService
from test_platform.core.services.progress_event_service import (
    build_error_event,
    build_progress_event,
    build_result_event,
    encode_stream_event,
    normalize_mode,
)
from test_platform.core.db.db_manager import db_manager
from test_platform.core.data_generators.test_case_exporter import (
    export_to_excel,
    export_to_xmind,
    parse_test_cases_from_text,
)
from test_platform.infrastructure.tapd_client import TAPDClient
from test_platform.services.dify_client import DifyRateLimitError

# 日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# 初始化服务
review_service = ReviewService()
history_report_service = HistoryReportService()
TEMP_DIR_PREFIXES = ("qa_wb_", "qa_rec_", "qa_exp_")


@dataclass
class RequestExecutionBundle:
    normalized_mode: str
    parsed_params: Dict[str, Any]
    parsed_roles: Optional[List[str]]
    main_file_path: Optional[str]
    execution: SkillExecutionResult


def _create_weekly_report_service() -> Optional[WeeklyReportService]:
    return create_runtime_weekly_report_service(review_service)


weekly_report_service = _create_weekly_report_service()


def _parse_json_mapping(raw_value: Optional[str]) -> Dict[str, Any]:
    return parse_runtime_json_mapping(raw_value, field_name="params")


def _parse_json_string_list(raw_value: Optional[str]) -> Optional[List[str]]:
    return parse_runtime_json_string_list(raw_value, field_name="roles")


def _create_temp_dir(prefix: str) -> str:
    temp_dir = os.path.join(tempfile.gettempdir(), f"{prefix}{uuid.uuid4()}")
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir


def _cleanup_temp_dir(temp_dir: Optional[str]) -> None:
    if not temp_dir:
        return

    base_name = os.path.basename(temp_dir.rstrip(os.sep))
    if not any(base_name.startswith(prefix) for prefix in TEMP_DIR_PREFIXES):
        logger.warning(f"Skip cleanup for unexpected temp dir: {temp_dir}")
        return

    shutil.rmtree(temp_dir, ignore_errors=True)


def _store_uploads(files: Optional[List[UploadFile]], temp_dir: str) -> Tuple[Optional[str], List[str]]:
    main_file_path = None
    uploaded_paths: List[str] = []

    if files:
        for idx, file in enumerate(files):
            safe_name = os.path.basename(file.filename or f"upload_{idx}")
            f_path = os.path.join(temp_dir, safe_name)
            with open(f_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded_paths.append(f_path)
            if idx == 0:
                main_file_path = f_path

    return main_file_path, uploaded_paths


def _build_export_basename(raw_name: str) -> str:
    text = os.path.basename(str(raw_name or "").strip())
    if not text:
        return "测试用例"

    invalid_chars = '<>:"/\\|?*'
    sanitized = ''.join('_' if character in invalid_chars else character for character in text).strip()
    if not sanitized:
        return "测试用例"

    stem, _ = os.path.splitext(sanitized)
    return (stem or sanitized).strip() or "测试用例"


def _build_download_headers(filename: str) -> Dict[str, str]:
    encoded = quote(filename)
    extension = os.path.splitext(filename)[1] or ".bin"
    ascii_fallback = f"test-cases{extension}"
    return {
        "Content-Disposition": f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'
    }


def _normalize_error_message(result: Any) -> str:
    message = str(result or "执行失败").strip()
    if message.startswith("Error:"):
        return message.split("Error:", 1)[1].strip() or "执行失败"
    return message or "执行失败"


def _get_services() -> ApiServices:
    return ApiServices(
        review_service=review_service,
        history_report_service=history_report_service,
        weekly_report_service=weekly_report_service,
        db_manager=db_manager,
    )


def _emit_initial_progress(
    normalized_mode: str,
    uploaded_paths: List[str],
    emit_progress: Any,
) -> None:
    if normalized_mode == SkillMode.TEST_CASE:
        emit_progress("📄 正在解析需求上下文...")
        return

    if normalized_mode == SkillMode.TEST_CASE_REVIEW:
        emit_progress("📄 正在解析需求上下文...")
        emit_progress("🧾 正在解析测试用例内容...")
        return

    if normalized_mode == SkillMode.WEEKLY_REPORT:
        emit_progress("💬 正在整理企业微信讨论内容...")
        if uploaded_paths:
            emit_progress("🖼️ 正在处理已上传截图...")
        return

    if normalized_mode == SkillMode.AUTO_SCRIPT_GEN:
        emit_progress("📄 正在解析需求与上传内容...")
        emit_progress("🧩 正在提取页面结构与交互元素...")
        return

    if normalized_mode == SkillMode.API_TEST_GEN:
        emit_progress("📄 正在解析接口描述与上传内容...")
        emit_progress("🧩 正在提取接口定义与参数结构...")
        return

    if normalized_mode == SkillMode.API_PERF_TEST:
        emit_progress("📄 正在解析接口描述与上传内容...")
        emit_progress("🧩 正在提取压测目标与参数结构...")
        return

    emit_progress("📄 正在解析文档并提取上下文...")


def _execute_request(
    mode: str,
    requirement: str,
    params_raw: Optional[str],
    roles_raw: Optional[str],
    extra_prompt: Optional[str],
    historical_findings: Optional[str],
    context_id: Optional[str],
    files: Optional[List[UploadFile]],
    status_callback: Optional[Any] = None,
) -> RequestExecutionBundle:
    normalized_mode = normalize_mode(mode)
    parsed_params = _parse_json_mapping(params_raw)
    parsed_roles = _parse_json_string_list(roles_raw)
    temp_dir = None
    bundle: Optional[RequestExecutionBundle] = None

    try:
        temp_dir = _create_temp_dir("qa_wb_")
        main_file_path, uploaded_paths = _store_uploads(files, temp_dir)

        logger.info(f"Running mode: {normalized_mode} for requirement length: {len(requirement)}")

        if status_callback:
            _emit_initial_progress(normalized_mode, uploaded_paths, status_callback)
            if normalized_mode == SkillMode.TEST_CASE:
                if historical_findings:
                    status_callback("🔗 已关联历史评审风险点...")
                else:
                    status_callback("🔗 已跳过关联历史评审风险点，本次无需关联...")
                status_callback("🧩 已完成需求模块拆解...")
                status_callback("🧠 正在匹配工程化测试策略...")
            elif normalized_mode == SkillMode.TEST_CASE_REVIEW:
                status_callback("🔗 正在对齐需求与测试用例...")
            elif normalized_mode == SkillMode.WEEKLY_REPORT:
                status_callback("🧠 AI 正在清洗和总结周报内容...")

        execution = execute_runtime_skill_request(
            services=_get_services(),
            mode=normalized_mode,
            requirement=requirement,
            params=parsed_params,
            roles=parsed_roles,
            extra_prompt=extra_prompt or "",
            historical_findings=historical_findings,
            context_id=context_id,
            main_file_path=main_file_path,
            uploaded_paths=uploaded_paths,
            status_callback=status_callback,
        )
        bundle = RequestExecutionBundle(
            normalized_mode=normalized_mode,
            parsed_params=parsed_params,
            parsed_roles=parsed_roles,
            main_file_path=main_file_path,
            execution=execution,
        )
    finally:
        _cleanup_temp_dir(temp_dir)

    if bundle is None:
        raise RuntimeError("请求执行失败，未生成执行结果")
    return bundle


def _build_execution_insight(
    bundle: RequestExecutionBundle,
    emit_progress: Optional[Any] = None,
) -> Optional[str]:
    normalized_mode = bundle.execution.normalized_mode
    result = bundle.execution.result

    if normalized_mode in {SkillMode.AUTO_SCRIPT_GEN, SkillMode.API_TEST_GEN, SkillMode.API_PERF_TEST}:
        if emit_progress:
            emit_progress("🧾 正在整理输出结果...")
        return None

    if normalized_mode == SkillMode.WEEKLY_REPORT:
        if emit_progress and bundle.execution.meta.get("publish_requested"):
            emit_progress("📝 正在写入飞书文档...")
        if emit_progress:
            emit_progress("🧾 正在整理周报输出结果...")
        return None

    if normalized_mode != SkillMode.TEST_CASE and emit_progress:
        emit_progress("💡 正在提炼动态风险洞察...")

    return generate_runtime_dynamic_insight(_get_services(), normalized_mode, result)


def _persist_execution(bundle: RequestExecutionBundle, requirement: str) -> None:
    persist_runtime_execution_result(
        services=_get_services(),
        execution=bundle.execution,
        requirement=requirement,
        main_file_path=bundle.main_file_path,
        roles=bundle.parsed_roles,
        params=bundle.parsed_params,
    )

@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.2.0-hardened"}

@router.post("/recommend-experts")
async def recommend_experts(
    requirement: str = Form(""),
    files: List[UploadFile] = File(None)
):
    """根据需求内容推荐角色。"""
    temp_dir = None
    try:
        content = requirement
        # 修复：当有文件上传但无手输文本时，提取 PDF 内容用于角色推荐
        if files and not content:
            first_file = files[0]
            temp_dir = _create_temp_dir("qa_rec_")
            f_path = os.path.join(temp_dir, os.path.basename(first_file.filename or "upload.pdf"))
            with open(f_path, "wb") as buffer:
                shutil.copyfileobj(first_file.file, buffer)
            # 提取前 2000 字供角色推荐
            if f_path.lower().endswith('.pdf'):
                try:
                    import pdfplumber  # type: ignore
                    with pdfplumber.open(f_path) as pdf:
                        texts = [p.extract_text() or "" for p in pdf.pages[:3]]
                        content = "\n".join(texts)[:2000]  # type: ignore
                except Exception as e:
                    logger.error(f"PDF extraction for recommendation failed: {e}")
            
        recommended = review_service.recommend_experts(content)
        return {"success": True, "recommended": recommended}
    except Exception as e:
        logger.error(f"Error in recommend_experts: {e}")
        return {"success": False, "recommended": ["product", "test"]}
    finally:
        _cleanup_temp_dir(temp_dir)

@router.post("/run")
async def run_skill(
    mode: str = Form(...),
    requirement: str = Form(""),
    params: Optional[str] = Form(None),
    roles: Optional[str] = Form(None), # JSON string
    extra_prompt: Optional[str] = Form(""),
    historical_findings: Optional[str] = Form(None), # 可选的历史评审发现
    context_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    """
    通用执行入口，模拟 Streamlit 的交互逻辑。
    """
    try:
        bundle = _execute_request(
            mode=mode,
            requirement=requirement,
            params_raw=params,
            roles_raw=roles,
            extra_prompt=extra_prompt,
            historical_findings=historical_findings,
            context_id=context_id,
            files=files,
        )

        # 追加动态风险洞察
        insight = None
        result = bundle.execution.result
        if result and not str(result).startswith("Error:"):
            _persist_execution(bundle, requirement)
            insight = _build_execution_insight(bundle)
            return {
                "success": True,
                "result": result,
                "insight": insight,
                "context_id": bundle.execution.context_id,
                "cache_hit": bundle.execution.cache_hit,
                "meta": bundle.execution.meta,
            }

        return {
            "success": False,
            "result": "",
            "error": _normalize_error_message(result),
            "context_id": bundle.execution.context_id,
            "cache_hit": bundle.execution.cache_hit,
            "meta": bundle.execution.meta,
        }

    except InvalidJsonPayloadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DifyRateLimitError as e:
        logger.warning(f"Dify 吞吐受限: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Error during skill execution")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run/stream")
async def run_skill_stream(
    mode: str = Form(...),
    requirement: str = Form(""),
    params: Optional[str] = Form(None),
    roles: Optional[str] = Form(None),
    extra_prompt: Optional[str] = Form(""),
    historical_findings: Optional[str] = Form(None),
    context_id: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    try:
        _parse_json_mapping(params)
        _parse_json_string_list(roles)
    except InvalidJsonPayloadError as e:
        raise HTTPException(status_code=400, detail=str(e))

    event_queue: Queue[Any] = Queue()
    sentinel = object()

    def emit(payload: Dict[str, Any]) -> None:
        event_queue.put(payload)

    def worker() -> None:
        progress_state: Dict[str, int] = {"sequence": 0}
        temp_dir = None

        def emit_progress(message: str) -> None:
            progress_state["sequence"] += 1
            emit(build_progress_event(mode, message, progress_state["sequence"]))

        try:
            bundle = _execute_request(
                mode=mode,
                requirement=requirement,
                params_raw=params,
                roles_raw=roles,
                extra_prompt=extra_prompt,
                historical_findings=historical_findings,
                context_id=context_id,
                files=files,
                status_callback=emit_progress,
            )

            result = bundle.execution.result
            if result and not str(result).startswith("Error:"):
                _persist_execution(bundle, requirement)
                insight = _build_execution_insight(bundle, emit_progress)
                emit(build_result_event(
                    result=result,
                    insight=insight,
                    context_id=bundle.execution.context_id,
                    cache_hit=bundle.execution.cache_hit,
                    meta=bundle.execution.meta,
                ))
            else:
                emit(build_error_event(_normalize_error_message(result)))
        except Exception as e:
            logger.exception("Error during stream skill execution")
            emit(build_error_event(str(e)))
        finally:
            event_queue.put(sentinel)

    def event_generator():
        worker_thread = Thread(target=worker, daemon=True)
        worker_thread.start()

        while True:
            payload = event_queue.get()
            if payload is sentinel:
                break
            yield encode_stream_event(payload)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@router.get("/api/dashboard/stats")
async def get_dashboard_stats():
    """获取仪表盘统计数据"""
    try:
        stats = db_manager.get_dashboard_stats()
        return stats
    except Exception as e:
        logger.error(f"Failed to fetch dashboard stats: {e}")
        return {"metrics": [], "recent_activities": []}


@router.get("/api/history/reports")
async def get_history_reports(
    types: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    type_filters = [value.strip() for value in str(types or "").split(",") if value.strip()]
    items = history_report_service.list_reports(type_filters or None, limit=limit)
    return {"items": items}


@router.get("/api/history/reports/{report_id}")
async def get_history_report(report_id: str):
    report = history_report_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="History report not found")
    return report


@router.get("/api/history/reports/{report_id}/artifacts/{artifact_key}")
async def download_history_report_artifact(report_id: str, artifact_key: str):
    artifact_path = history_report_service.get_report_artifact_path(report_id, artifact_key)
    if not artifact_path:
        raise HTTPException(status_code=404, detail="History artifact not found")

    media_type, _ = mimetypes.guess_type(artifact_path)
    return FileResponse(
        artifact_path,
        media_type=media_type or "application/octet-stream",
        filename=os.path.basename(artifact_path),
    )


@router.get("/api/tapd/story")
async def get_tapd_story(input: str = Query(..., min_length=1)):
    normalized_input = str(input or "").strip()
    story_id = TAPDClient.parse_story_id(normalized_input)
    if not story_id:
        if "doc.weixin.qq.com" in normalized_input.lower():
            raise HTTPException(
                status_code=400,
                detail="已识别为腾讯文档链接。读取 TAPD 仅支持 TAPD Story 链接或纯数字 ID。",
            )
        raise HTTPException(status_code=400, detail="无效的 TAPD ID 或链接，仅支持 tapd.cn Story 链接或纯数字 ID。")

    if not review_service.tapd_client:
        raise HTTPException(status_code=503, detail="TAPD 功能未配置，请检查凭据。")

    content = review_service.fetch_requirement_from_tapd(story_id)
    if not content:
        raise HTTPException(status_code=502, detail="TAPD 需求获取失败，请检查需求 ID 或权限。")

    return {
        "success": True,
        "story_id": story_id,
        "content": content,
    }


@router.post("/api/test-cases/export")
async def export_test_cases(payload: Dict[str, Any]):
    export_format = str(payload.get("format") or "").strip().lower()
    result = str(payload.get("result") or "")
    filename = _build_export_basename(str(payload.get("filename") or "测试用例"))

    if export_format not in {"excel", "xmind"}:
        raise HTTPException(status_code=400, detail="仅支持 excel 或 xmind 导出格式。")

    cases = parse_test_cases_from_text(result)
    if not cases:
        raise HTTPException(status_code=400, detail="当前结果无法解析为结构化测试用例。")

    temp_dir = None
    try:
        temp_dir = _create_temp_dir("qa_exp_")
        if export_format == "excel":
            download_name = f"{filename}_测试用例.xlsx"
            output_path = os.path.join(temp_dir, download_name)
            export_to_excel(cases, output_path)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            download_name = f"{filename}_测试用例.xmind"
            output_path = os.path.join(temp_dir, download_name)
            export_to_xmind(cases, output_path)
            media_type = "application/octet-stream"

        with open(output_path, "rb") as exported_file:
            content = exported_file.read()

        return Response(
            content=content,
            media_type=media_type,
            headers=_build_download_headers(download_name),
        )
    finally:
        _cleanup_temp_dir(temp_dir)


def create_app() -> FastAPI:
    application = FastAPI(title="QA Workbench API Bridge")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 实际环境应限制为前端地址
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )
    application.include_router(router)
    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
