import json
import logging
from queue import Queue
from threading import Thread
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from test_platform.api.runtime import (
    ApiServices,
    build_recommendation_content,
    cleanup_temp_dir,
    create_temp_dir,
    execute_skill_request,
    generate_dynamic_insight,
    parse_json_mapping,
    parse_json_string_list,
    persist_execution_result,
    store_uploads,
)
from test_platform.core.services.progress_event_service import (
    build_error_event,
    build_progress_event,
    build_result_event,
    encode_stream_event,
    normalize_mode,
)
from test_platform.core.skill_modes import SkillMode
from test_platform.services.dify_client import DifyRateLimitError


logger = logging.getLogger(__name__)


def _normalize_error_message(result: Any) -> str:
    message = str(result or "执行失败").strip()
    if message.startswith("Error:"):
        return message.split("Error:", 1)[1].strip() or "执行失败"
    return message or "执行失败"


def _emit_initial_progress(
    normalized_mode: str,
    uploaded_paths: List[str],
    emit_progress: Callable[[str], None],
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
    if normalized_mode == SkillMode.TEST_DATA:
        emit_progress("📄 正在解析技术文档内容...")
        return
    emit_progress("📄 正在解析文档并提取上下文...")


def create_run_router(get_services: Callable[[], ApiServices]) -> APIRouter:
    router = APIRouter()

    @router.post("/recommend-experts")
    async def recommend_experts(
        requirement: str = Form(""),
        files: List[UploadFile] = File(None),
    ) -> dict:
        temp_dir = None
        try:
            content = requirement
            if files and not content:
                temp_dir = create_temp_dir("qa_rec_")
                content = build_recommendation_content(requirement, files, temp_dir)

            recommended = get_services().review_service.recommend_experts(content)
            return {"success": True, "recommended": recommended}
        except Exception as error:
            logger.error("Error in recommend_experts: %s", error)
            return {"success": False, "recommended": ["product", "test"]}
        finally:
            cleanup_temp_dir(temp_dir)

    @router.post("/run")
    async def run_skill(
        mode: str = Form(...),
        requirement: str = Form(""),
        params: Optional[str] = Form(None),
        roles: Optional[str] = Form(None),
        extra_prompt: Optional[str] = Form(""),
        historical_findings: Optional[str] = Form(None),
        context_id: Optional[str] = Form(None),
        files: List[UploadFile] = File(None),
    ) -> dict:
        temp_dir = None
        try:
            services = get_services()
            normalized_mode = normalize_mode(mode)
            parsed_params = parse_json_mapping(params)
            parsed_roles = parse_json_string_list(roles)

            temp_dir = create_temp_dir("qa_wb_")
            main_file_path, uploaded_paths = store_uploads(files, temp_dir)

            logger.info("Running mode: %s for requirement length: %s", normalized_mode, len(requirement))

            execution = execute_skill_request(
                services=services,
                mode=normalized_mode,
                requirement=requirement,
                params=parsed_params,
                roles=parsed_roles,
                extra_prompt=extra_prompt or "",
                historical_findings=historical_findings,
                context_id=context_id,
                main_file_path=main_file_path,
                uploaded_paths=uploaded_paths,
            )

            insight = None
            if execution.result and not str(execution.result).startswith("Error:"):
                persist_execution_result(
                    services=services,
                    execution=execution,
                    requirement=requirement,
                    main_file_path=main_file_path,
                    roles=parsed_roles,
                    params=parsed_params,
                )
                insight = generate_dynamic_insight(services, execution.normalized_mode, execution.result)

                return {
                    "success": True,
                    "result": execution.result,
                    "insight": insight,
                    "context_id": execution.context_id,
                    "cache_hit": execution.cache_hit,
                    "meta": execution.meta,
                }
            return {
                "success": False,
                "result": "",
                "error": _normalize_error_message(execution.result),
                "context_id": execution.context_id,
                "cache_hit": execution.cache_hit,
                "meta": execution.meta,
            }
        except DifyRateLimitError as error:
            logger.warning("Dify 吞吐受限: %s", error)
            raise HTTPException(status_code=503, detail=str(error))
        except Exception as error:
            logger.exception("Error during skill execution")
            raise HTTPException(status_code=500, detail=str(error))
        finally:
            cleanup_temp_dir(temp_dir)

    @router.post("/run/stream")
    async def run_skill_stream(
        mode: str = Form(...),
        requirement: str = Form(""),
        params: Optional[str] = Form(None),
        roles: Optional[str] = Form(None),
        extra_prompt: Optional[str] = Form(""),
        historical_findings: Optional[str] = Form(None),
        context_id: Optional[str] = Form(None),
        files: List[UploadFile] = File(None),
    ) -> StreamingResponse:
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
                services = get_services()
                normalized_mode = normalize_mode(mode)
                parsed_params = parse_json_mapping(params)
                parsed_roles = parse_json_string_list(roles)

                temp_dir = create_temp_dir("qa_wb_")
                main_file_path, uploaded_paths = store_uploads(files, temp_dir)

                _emit_initial_progress(normalized_mode, uploaded_paths, emit_progress)

                if normalized_mode == SkillMode.TEST_CASE:
                    if historical_findings:
                        emit_progress("🔗 已关联历史评审风险点...")
                    else:
                        emit_progress("🔗 已跳过关联历史评审风险点，本次无需关联...")
                    emit_progress("🧩 已完成需求模块拆解...")
                    emit_progress("🧠 正在匹配工程化测试策略...")
                elif normalized_mode == SkillMode.TEST_CASE_REVIEW:
                    emit_progress("🔗 正在对齐需求与测试用例...")
                elif normalized_mode == SkillMode.WEEKLY_REPORT:
                    emit_progress("🧠 AI 正在清洗和总结周报内容...")

                execution = execute_skill_request(
                    services=services,
                    mode=normalized_mode,
                    requirement=requirement,
                    params=parsed_params,
                    roles=parsed_roles,
                    extra_prompt=extra_prompt or "",
                    historical_findings=historical_findings,
                    context_id=context_id,
                    main_file_path=main_file_path,
                    uploaded_paths=uploaded_paths,
                    status_callback=emit_progress,
                )

                if execution.result and not str(execution.result).startswith("Error:"):
                    persist_execution_result(
                        services=services,
                        execution=execution,
                        requirement=requirement,
                        main_file_path=main_file_path,
                        roles=parsed_roles,
                        params=parsed_params,
                    )

                    if normalized_mode in {
                        SkillMode.AUTO_SCRIPT_GEN,
                        SkillMode.API_TEST_GEN,
                        SkillMode.API_PERF_TEST,
                    }:
                        emit_progress("🧾 正在整理输出结果...")
                        insight = None
                    elif normalized_mode == SkillMode.WEEKLY_REPORT:
                        if execution.meta.get("publish_requested"):
                            emit_progress("📝 正在写入飞书文档...")
                        emit_progress("🧾 正在整理周报输出结果...")
                        insight = None
                    elif normalized_mode != SkillMode.TEST_CASE:
                        emit_progress("💡 正在提炼动态风险洞察...")
                        insight = generate_dynamic_insight(services, normalized_mode, execution.result)
                    else:
                        insight = generate_dynamic_insight(services, normalized_mode, execution.result)

                    emit(
                        build_result_event(
                            result=execution.result,
                            insight=insight,
                            context_id=execution.context_id,
                            cache_hit=execution.cache_hit,
                            meta=execution.meta,
                        )
                    )
                else:
                    emit(build_error_event(_normalize_error_message(execution.result)))
            except Exception as error:
                logger.exception("Error during stream skill execution")
                emit(build_error_event(str(error)))
            finally:
                cleanup_temp_dir(temp_dir)
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

    return router
