import logging
import mimetypes
import os
from typing import Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from test_platform.api.runtime import ApiServices


logger = logging.getLogger(__name__)


def create_system_router(get_services: Callable[[], ApiServices]) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    async def health() -> dict:
        return {"status": "ok", "version": "1.2.0-hardened"}

    @router.get("/api/dashboard/stats")
    async def get_dashboard_stats() -> dict:
        try:
            return get_services().db_manager.get_dashboard_stats()
        except Exception as error:
            logger.error("Failed to fetch dashboard stats: %s", error)
            return {"metrics": [], "recent_activities": []}

    @router.get("/api/history/reports")
    async def get_history_reports(
        types: str = Query(None),
        limit: int = Query(20, ge=1, le=100),
    ) -> dict:
        type_filters = [value.strip() for value in str(types or "").split(",") if value.strip()]
        items = get_services().history_report_service.list_reports(type_filters or None, limit=limit)
        return {"items": items}

    @router.get("/api/history/reports/{report_id}")
    async def get_history_report(report_id: str) -> dict:
        report = get_services().history_report_service.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="History report not found")
        return report

    @router.get("/api/history/reports/{report_id}/artifacts/{artifact_key}")
    async def download_history_report_artifact(report_id: str, artifact_key: str):
        artifact_path = get_services().history_report_service.get_report_artifact_path(report_id, artifact_key)
        if not artifact_path:
            raise HTTPException(status_code=404, detail="History artifact not found")

        media_type, _ = mimetypes.guess_type(artifact_path)
        return FileResponse(
            artifact_path,
            media_type=media_type or "application/octet-stream",
            filename=os.path.basename(artifact_path),
        )

    return router
