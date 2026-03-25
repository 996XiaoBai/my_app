import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ApiSuiteRepository:
    """负责接口测试套件的本地沉淀与版本化存储。"""

    def __init__(self, base_dir: Optional[str] = None):
        project_root = Path(__file__).resolve().parents[3]
        self.base_dir = Path(base_dir) if base_dir else project_root / "history" / "api_suites"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_suite(
        self,
        spec: Dict[str, Any],
        cases: List[Dict[str, Any]],
        scenes: List[Dict[str, Any]],
        script: str = "",
        link_plan: Optional[Dict[str, Any]] = None,
        execution: Optional[Dict[str, Any]] = None,
        report: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        suite_id = self._build_suite_id(spec)
        suite_dir = self.base_dir / suite_id
        suite_dir.mkdir(parents=True, exist_ok=True)

        suite_version = self._resolve_next_version(suite_dir)
        storage_path = suite_dir / f"v{suite_version:03d}.json"
        payload = {
            "suite_id": suite_id,
            "suite_version": suite_version,
            "created_at": datetime.now().isoformat(),
            "spec": spec if isinstance(spec, dict) else {},
            "cases": cases if isinstance(cases, list) else [],
            "scenes": scenes if isinstance(scenes, list) else [],
            "script": str(script or ""),
            "link_plan": link_plan if isinstance(link_plan, dict) else {},
            "execution": execution if isinstance(execution, dict) else {},
            "report": report if isinstance(report, dict) else {},
        }
        storage_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "suite_id": suite_id,
            "suite_version": suite_version,
            "title": str((spec or {}).get("title") or "未命名接口套件").strip() or "未命名接口套件",
            "case_count": len(cases or []),
            "scene_count": len(scenes or []),
            "storage_path": str(storage_path),
        }

    def load_suite(self, suite_id: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        normalized_suite_id = str(suite_id or "").strip()
        if not normalized_suite_id:
            return None

        suite_dir = self.base_dir / normalized_suite_id
        if not suite_dir.exists():
            return None

        target_path = suite_dir / f"v{int(version):03d}.json" if version else self._resolve_latest_suite_file(suite_dir)
        if target_path is None or not target_path.exists():
            return None

        return json.loads(target_path.read_text(encoding="utf-8"))

    def list_suites(self, limit: int = 20) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for suite_dir in self.base_dir.iterdir():
            if not suite_dir.is_dir():
                continue
            latest_path = self._resolve_latest_suite_file(suite_dir)
            if latest_path is None:
                continue
            payload = json.loads(latest_path.read_text(encoding="utf-8"))
            items.append(
                {
                    "suite_id": str(payload.get("suite_id") or suite_dir.name),
                    "title": str((payload.get("spec") or {}).get("title") or "未命名接口套件").strip() or "未命名接口套件",
                    "latest_version": int(payload.get("suite_version") or 0),
                    "case_count": len(payload.get("cases") or []),
                    "scene_count": len(payload.get("scenes") or []),
                    "updated_at": str(payload.get("created_at") or ""),
                    "storage_path": str(latest_path),
                }
            )

        items.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return items[: max(int(limit or 20), 0)]

    def _build_suite_id(self, spec: Dict[str, Any]) -> str:
        title = str((spec or {}).get("title") or "api_suite").strip() or "api_suite"
        servers = (spec or {}).get("servers") if isinstance((spec or {}).get("servers"), list) else []
        first_server_url = ""
        if servers and isinstance(servers[0], dict):
            first_server_url = str(servers[0].get("url") or "").strip()
        fingerprint_seed = json.dumps(
            {
                "title": title,
                "server": first_server_url,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        fingerprint = hashlib.sha1(fingerprint_seed.encode("utf-8")).hexdigest()[:8]
        slug = re.sub(r"[^0-9A-Za-z]+", "_", title).strip("_").lower() or "api_suite"
        return f"{slug}_{fingerprint}"

    def _resolve_next_version(self, suite_dir: Path) -> int:
        latest_file = self._resolve_latest_suite_file(suite_dir)
        if latest_file is None:
            return 1
        match = re.search(r"v(\d+)\.json$", latest_file.name)
        if not match:
            return 1
        return int(match.group(1)) + 1

    def _resolve_latest_suite_file(self, suite_dir: Path) -> Optional[Path]:
        candidates = sorted(suite_dir.glob("v*.json"))
        if not candidates:
            return None
        return candidates[-1]
