import json
import os
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET


class ApiTestExecutionService:
    """负责编译并执行结构化接口测试资产。"""

    def __init__(self, history_base_dir: Optional[str] = None, python_executable: Optional[str] = None):
        project_root = Path(__file__).resolve().parents[3]
        self.history_base_dir = Path(history_base_dir) if history_base_dir else project_root / "history"
        self.python_executable = python_executable or self._resolve_python_executable(project_root)
        self._allure_support_cache: Optional[bool] = None

    def execute_pack(
        self,
        spec: Dict[str, Any],
        cases: List[Dict[str, Any]],
        scenes: List[Dict[str, Any]],
        params: Optional[Dict[str, Any]] = None,
        script: str = "",
    ) -> Dict[str, Any]:
        runtime_params = self._normalize_params(params)
        run_id = f"api_run_{uuid.uuid4().hex[:10]}"
        run_dir = self.history_base_dir / "api_test_runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        generated_script_path = run_dir / "generated_script.py"
        compiled_script_path = run_dir / "test_api_suite.py"
        junit_xml_path = run_dir / "junit.xml"
        runtime_config_path = run_dir / "runtime_config.json"
        asset_snapshot_path = run_dir / "openapi_asset.json"
        case_snapshot_path = run_dir / "api_cases.json"
        scene_snapshot_path = run_dir / "api_scenes.json"
        execution_summary_path = run_dir / "execution_summary.json"
        allure_results_path = run_dir / "allure-results"
        allure_archive_path = run_dir / "allure-results.zip"

        generated_script_path.write_text(str(script or "").strip() + ("\n" if str(script or "").strip() else ""), encoding="utf-8")
        runtime_config_path.write_text(
            json.dumps(runtime_params, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        asset_snapshot_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        case_snapshot_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
        scene_snapshot_path.write_text(json.dumps(scenes, ensure_ascii=False, indent=2), encoding="utf-8")
        compiled_script_path.write_text(
            self._build_compiled_script(spec=spec, cases=cases, scenes=scenes, params=runtime_params),
            encoding="utf-8",
        )

        command = [
            self.python_executable,
            "-m",
            "pytest",
            "-q",
            "--junitxml=junit.xml",
        ]
        if bool(runtime_params.get("collect_allure", True)) and self._supports_allure_results():
            command.append("--alluredir=allure-results")
        command.append(compiled_script_path.name)
        timeout_seconds = int(runtime_params.get("runner_timeout") or 120)

        completed = subprocess.run(
            command,
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        stats = self._parse_junit_xml(junit_xml_path)
        status = self._resolve_status(completed.returncode, stats)
        summary = self._build_summary(status, stats)
        execution_summary = {
            "run_id": run_id,
            "status": status,
            "summary": summary,
            "stats": stats,
            "command": " ".join(command),
            "stdout": str(completed.stdout or "").strip(),
            "stderr": str(completed.stderr or "").strip(),
        }
        execution_summary_path.write_text(
            json.dumps(execution_summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        junit_xml_content = junit_xml_path.read_text(encoding="utf-8") if junit_xml_path.exists() else ""
        runtime_config_content = runtime_config_path.read_text(encoding="utf-8") if runtime_config_path.exists() else ""
        asset_snapshot_content = asset_snapshot_path.read_text(encoding="utf-8") if asset_snapshot_path.exists() else ""
        case_snapshot_content = case_snapshot_path.read_text(encoding="utf-8") if case_snapshot_path.exists() else ""
        scene_snapshot_content = scene_snapshot_path.read_text(encoding="utf-8") if scene_snapshot_path.exists() else ""
        has_allure_results = allure_results_path.exists() and any(allure_results_path.iterdir())
        if has_allure_results:
            self._archive_allure_results(allure_results_path, allure_archive_path)

        return {
            "run_id": run_id,
            "status": status,
            "summary": summary,
            "stats": stats,
            "command": " ".join(command),
            "stdout": str(completed.stdout or "").strip(),
            "stderr": str(completed.stderr or "").strip(),
            "junit_xml_content": junit_xml_content,
            "execution_summary_content": json.dumps(execution_summary, ensure_ascii=False, indent=2),
            "runtime_config_content": runtime_config_content,
            "asset_snapshot_content": asset_snapshot_content,
            "case_snapshot_content": case_snapshot_content,
            "scene_snapshot_content": scene_snapshot_content,
            "artifacts": {
                "run_dir": str(run_dir),
                "generated_script": str(generated_script_path),
                "compiled_script": str(compiled_script_path),
                "junit_xml": str(junit_xml_path),
                "runtime_config": str(runtime_config_path),
                "asset_snapshot": str(asset_snapshot_path),
                "case_snapshot": str(case_snapshot_path),
                "scene_snapshot": str(scene_snapshot_path),
                "execution_summary": str(execution_summary_path),
                "allure_results": str(allure_results_path) if has_allure_results else "",
                "allure_archive": str(allure_archive_path) if allure_archive_path.exists() else "",
            },
        }

    def _resolve_python_executable(self, project_root: Path) -> str:
        candidates = [
            os.environ.get("PYTHON_BIN"),
            os.path.join(os.environ.get("VIRTUAL_ENV", ""), "bin", "python") if os.environ.get("VIRTUAL_ENV") else "",
            str(project_root / "test_platform" / ".venv" / "bin" / "python"),
            str(project_root / ".venv" / "bin" / "python"),
            sys.executable,
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return sys.executable

    def _normalize_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        raw_params = params if isinstance(params, dict) else {}
        headers = raw_params.get("headers") if isinstance(raw_params.get("headers"), dict) else {}
        cookies = raw_params.get("cookies") if isinstance(raw_params.get("cookies"), dict) else {}
        request_overrides = raw_params.get("request_overrides") if isinstance(raw_params.get("request_overrides"), dict) else {}
        return {
            "base_url": str(raw_params.get("base_url") or "").strip(),
            "headers": {str(key): value for key, value in headers.items()},
            "cookies": {str(key): value for key, value in cookies.items()},
            "request_overrides": request_overrides,
            "timeout": int(raw_params.get("timeout") or 15),
            "verify_ssl": bool(raw_params.get("verify_ssl", True)),
            "expected_status": int(raw_params.get("expected_status") or 200),
            "success_codes": raw_params.get("success_codes") if isinstance(raw_params.get("success_codes"), list) else [0],
            "runner_timeout": int(raw_params.get("runner_timeout") or 120),
            "collect_allure": bool(raw_params.get("collect_allure", True)),
        }

    def _supports_allure_results(self) -> bool:
        if self._allure_support_cache is not None:
            return self._allure_support_cache

        try:
            completed = subprocess.run(
                [self.python_executable, "-m", "pytest", "--help"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            help_text = f"{completed.stdout or ''}\n{completed.stderr or ''}"
            self._allure_support_cache = "--alluredir" in help_text
        except Exception:
            self._allure_support_cache = False

        return self._allure_support_cache

    def _archive_allure_results(self, allure_results_path: Path, allure_archive_path: Path) -> None:
        with zipfile.ZipFile(allure_archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for artifact_path in sorted(allure_results_path.rglob("*")):
                if artifact_path.is_file():
                    zip_file.write(artifact_path, artifact_path.relative_to(allure_results_path.parent))

    def _parse_junit_xml(self, junit_xml_path: Path) -> Dict[str, int]:
        if not junit_xml_path.exists():
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            }

        try:
            root = ET.fromstring(junit_xml_path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            }

        suite_nodes: List[ET.Element] = []
        if root.tag == "testsuite":
            suite_nodes = [root]
        elif root.tag == "testsuites":
            suite_nodes = [node for node in root if node.tag == "testsuite"]

        if suite_nodes:
            tests = sum(int(node.attrib.get("tests", 0) or 0) for node in suite_nodes)
            failures = sum(int(node.attrib.get("failures", 0) or 0) for node in suite_nodes)
            errors = sum(int(node.attrib.get("errors", 0) or 0) for node in suite_nodes)
            skipped = sum(int(node.attrib.get("skipped", 0) or 0) for node in suite_nodes)
        else:
            tests = int(root.attrib.get("tests", 0) or 0)
            failures = int(root.attrib.get("failures", 0) or 0)
            errors = int(root.attrib.get("errors", 0) or 0)
            skipped = int(root.attrib.get("skipped", 0) or 0)

        passed = max(tests - failures - errors - skipped, 0)
        return {
            "total": tests,
            "passed": passed,
            "failed": failures,
            "errors": errors,
            "skipped": skipped,
        }

    def _resolve_status(self, return_code: int, stats: Dict[str, int]) -> str:
        if stats.get("failed", 0) > 0 or stats.get("errors", 0) > 0:
            return "failed"
        if return_code == 0:
            return "passed"
        return "error"

    def _build_summary(self, status: str, stats: Dict[str, int]) -> str:
        total = int(stats.get("total", 0) or 0)
        passed = int(stats.get("passed", 0) or 0)
        failed = int(stats.get("failed", 0) or 0)
        errors = int(stats.get("errors", 0) or 0)
        skipped = int(stats.get("skipped", 0) or 0)

        if status == "passed":
            return f"执行 {total} 条 pytest 用例，全部通过。"
        if status == "failed":
            return f"执行 {total} 条 pytest 用例，{passed} 通过，{failed} 失败，{errors} 异常，{skipped} 跳过。"
        return f"执行异常，pytest 返回非零退出码，当前统计为：总数 {total}，通过 {passed}，失败 {failed}，异常 {errors}。"

    def _build_compiled_script(
        self,
        spec: Dict[str, Any],
        cases: List[Dict[str, Any]],
        scenes: List[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> str:
        spec_json_literal = self._build_embedded_json_literal(spec)
        cases_json_literal = self._build_embedded_json_literal(cases)
        scenes_json_literal = self._build_embedded_json_literal(scenes)
        params_json_literal = self._build_embedded_json_literal(params)

        parts: List[str] = [
            "import json\n",
            "from copy import deepcopy\n",
            "from typing import Any, Dict, List\n\n",
            "import pytest\n",
            "import requests\n\n",
            f"SPEC = json.loads({spec_json_literal})\n\n",
            f"CASES = json.loads({cases_json_literal})\n\n",
            f"SCENES = json.loads({scenes_json_literal})\n\n",
            f"CONFIG = json.loads({params_json_literal})\n\n",
            "OPERATIONS = {item['operation_id']: item for item in SPEC.get('operations', []) if isinstance(item, dict)}\n",
            "RESOURCES = {item.get('resource_key'): item for item in SPEC.get('resources', []) if isinstance(item, dict)}\n",
            "CASE_INDEX = {item['case_id']: item for item in CASES if isinstance(item, dict)}\n",
            "SCENE_INDEX = {item['scene_id']: item for item in SCENES if isinstance(item, dict)}\n\n",
            "def _new_runtime_context() -> Dict[str, Any]:\n",
            "    base_url = str(CONFIG.get('base_url') or '').strip()\n",
            "    if not base_url:\n",
            "        servers = SPEC.get('servers') if isinstance(SPEC.get('servers'), list) else []\n",
            "        if servers and isinstance(servers[0], dict):\n",
            "            base_url = str(servers[0].get('url') or '').strip()\n",
            "    assert base_url, '缺少 base_url，无法执行接口测试。'\n",
            "    return {\n",
            "        'base_url': base_url.rstrip('/'),\n",
            "        'headers': deepcopy(CONFIG.get('headers') or {}),\n",
            "        'cookies': deepcopy(CONFIG.get('cookies') or {}),\n",
            "        'timeout': int(CONFIG.get('timeout') or 15),\n",
            "        'verify_ssl': bool(CONFIG.get('verify_ssl', True)),\n",
            "        'expected_status': int(CONFIG.get('expected_status') or 200),\n",
            "        'success_codes': list(CONFIG.get('success_codes') or [0]),\n",
            "        'resources': {},\n",
            "        'variables': {},\n",
            "    }\n\n",
            "def _extract_value(payload: Any, path: str) -> Any:\n",
            "    current = payload\n",
            "    normalized_path = str(path or '').strip()\n",
            "    if normalized_path.startswith('response.'):\n",
            "        normalized_path = normalized_path[len('response.'):]\n",
            "    for segment in [part for part in normalized_path.split('.') if part]:\n",
            "        if '[' in segment and segment.endswith(']'):\n",
            "            field_name = segment[:segment.index('[')]\n",
            "            index_value = segment[segment.index('[') + 1:-1]\n",
            "            if field_name:\n",
            "                current = current.get(field_name) if isinstance(current, dict) else None\n",
            "            if not isinstance(current, list):\n",
            "                return None\n",
            "            index = int(index_value)\n",
            "            if index >= len(current):\n",
            "                return None\n",
            "            current = current[index]\n",
            "            continue\n",
            "        current = current.get(segment) if isinstance(current, dict) else None\n",
            "        if current is None:\n",
            "            return None\n",
            "    return current\n\n",
            "def _resource_state(runtime: Dict[str, Any], resource_key: str) -> Dict[str, Any]:\n",
            "    if resource_key not in runtime['resources']:\n",
            "        runtime['resources'][resource_key] = {\n",
            "            'created_payload': {},\n",
            "            'resource_id': None,\n",
            "            'lookup_values': {},\n",
            "        }\n",
            "    return runtime['resources'][resource_key]\n\n",
            "def _sample_value(resource_key: str, field_name: str, field_spec: Dict[str, Any], state: Dict[str, Any]) -> Any:\n",
            "    sample_type = str(field_spec.get('type') or '').strip()\n",
            "    if field_name == 'id':\n",
            "        return state.get('resource_id') or 10001\n",
            "    if field_name == 'ids':\n",
            "        return [state.get('resource_id') or 10001]\n",
            "    if field_name in {'page', 'size', 'limit'}:\n",
            "        return 20 if field_name != 'page' else 1\n",
            "    if field_name == 'offset':\n",
            "        return 0\n",
            "    if field_name == 'status':\n",
            "        return 'ENABLE'\n",
            "    if field_name == 'jumpUrl':\n",
            "        return state.get('created_payload', {}).get(field_name) or f'https://example.com/{resource_key}'\n",
            "    if field_name.endswith('Id') or sample_type in {'integer', 'number'}:\n",
            "        return state.get('created_payload', {}).get(field_name) or 10001\n",
            "    if sample_type == 'boolean':\n",
            "        return True\n",
            "    if sample_type == 'array':\n",
            "        item_type = str((field_spec.get('items') or {}).get('type') or '').strip()\n",
            "        return [10001] if item_type in {'integer', 'number'} else ['auto_item']\n",
            "    if sample_type == 'object':\n",
            "        return {}\n",
            "    return state.get('created_payload', {}).get(field_name) or f'auto_{resource_key}_{field_name}'\n\n",
            "def _pick_override(case: Dict[str, Any], operation: Dict[str, Any], resource_key: str, field_name: str) -> Any:\n",
            "    overrides = CONFIG.get('request_overrides') or {}\n",
            "    for key in (case.get('case_id'), operation.get('operation_id'), resource_key):\n",
            "        mapping = overrides.get(key) if isinstance(overrides, dict) else None\n",
            "        if isinstance(mapping, dict) and field_name in mapping:\n",
            "            return mapping[field_name]\n",
            "    return None\n\n",
            "def _build_payload(case: Dict[str, Any], operation: Dict[str, Any], runtime: Dict[str, Any]) -> Dict[str, Any]:\n",
            "    resource_key = str(case.get('resource_key') or operation.get('resource_key') or 'default')\n",
            "    state = _resource_state(runtime, resource_key)\n",
            "    field_specs = operation.get('request_field_specs') or {}\n",
            "    payload: Dict[str, Any] = {}\n",
            "    for field_name, field_spec in field_specs.items():\n",
            "        override_value = _pick_override(case, operation, resource_key, field_name)\n",
            "        if override_value is not None:\n",
            "            payload[field_name] = override_value\n",
            "            continue\n",
            "        payload[field_name] = _sample_value(resource_key, field_name, field_spec if isinstance(field_spec, dict) else {}, state)\n",
            "    if case.get('category') == 'list':\n",
            "        resource_meta = RESOURCES.get(resource_key) or {}\n",
            "        for field_name in resource_meta.get('lookup_fields') or []:\n",
            "            if field_name in payload:\n",
            "                continue\n",
            "            created_payload = state.get('created_payload') or {}\n",
            "            if field_name in created_payload:\n",
            "                payload[field_name] = created_payload[field_name]\n",
            "    if case.get('category') in {'update', 'status', 'delete'} and state.get('resource_id'):\n",
            "        if 'id' in field_specs:\n",
            "            payload['id'] = state['resource_id']\n",
            "        if 'ids' in field_specs:\n",
            "            payload['ids'] = [state['resource_id']]\n",
            "    if case.get('category') == 'create':\n",
            "        state['created_payload'] = deepcopy(payload)\n",
            "        resource_meta = RESOURCES.get(resource_key) or {}\n",
            "        state['lookup_values'] = {\n",
            "            field_name: payload.get(field_name)\n",
            "            for field_name in resource_meta.get('lookup_fields') or []\n",
            "            if field_name in payload\n",
            "        }\n",
            "    return payload\n\n",
            "def _matches_lookup(item: Dict[str, Any], state: Dict[str, Any]) -> bool:\n",
            "    lookup_values = state.get('lookup_values') or {}\n",
            "    if state.get('resource_id') is not None and item.get('id') == state.get('resource_id'):\n",
            "        return True\n",
            "    if not lookup_values:\n",
            "        return False\n",
            "    return all(item.get(key) == value for key, value in lookup_values.items())\n\n",
            "def _assert_response_success(response: requests.Response, body: Any, runtime: Dict[str, Any]) -> None:\n",
            "    assert response.status_code == runtime['expected_status'], f'HTTP 状态码不符合预期：{response.status_code}'\n",
            "    if isinstance(body, dict) and isinstance(body.get('state'), dict) and 'code' in body.get('state', {}):\n",
            "        assert body['state']['code'] in runtime['success_codes'], f\"业务返回码异常：{body['state']['code']}\"\n\n",
            "def _request(case: Dict[str, Any], runtime: Dict[str, Any]) -> Any:\n",
            "    operation = OPERATIONS[case['operation_id']]\n",
            "    method = str(operation.get('method') or 'GET').upper()\n",
            "    path = str(operation.get('path') or '').strip()\n",
            "    url = f\"{runtime['base_url']}{path}\"\n",
            "    payload = _build_payload(case, operation, runtime)\n",
            "    if method in {'GET', 'DELETE'}:\n",
            "        response = requests.request(\n",
            "            method,\n",
            "            url,\n",
            "            headers=runtime['headers'],\n",
            "            cookies=runtime['cookies'],\n",
            "            params=payload,\n",
            "            timeout=runtime['timeout'],\n",
            "            verify=runtime['verify_ssl'],\n",
            "        )\n",
            "    else:\n",
            "        response = requests.request(\n",
            "            method,\n",
            "            url,\n",
            "            headers=runtime['headers'],\n",
            "            cookies=runtime['cookies'],\n",
            "            json=payload,\n",
            "            timeout=runtime['timeout'],\n",
            "            verify=runtime['verify_ssl'],\n",
            "        )\n",
            "    try:\n",
            "        body = response.json()\n",
            "    except ValueError:\n",
            "        body = {}\n",
            "    return operation, payload, response, body\n\n",
            "def _apply_extract_rules(case: Dict[str, Any], body: Any, runtime: Dict[str, Any]) -> None:\n",
            "    resource_key = str(case.get('resource_key') or 'default')\n",
            "    state = _resource_state(runtime, resource_key)\n",
            "    for rule in case.get('extract') or []:\n",
            "        pick = str(rule.get('pick') or '').strip()\n",
            "        value = _extract_value(body, pick)\n",
            "        if value is None:\n",
            "            continue\n",
            "        variable_name = str(rule.get('name') or '').strip() or 'extracted_value'\n",
            "        runtime['variables'][variable_name] = value\n",
            "        if variable_name == 'resource_id' or pick.endswith('.id'):\n",
            "            state['resource_id'] = value\n\n",
            "def _run_case(case: Dict[str, Any], runtime: Dict[str, Any]) -> None:\n",
            "    _, _, response, body = _request(case, runtime)\n",
            "    _assert_response_success(response, body, runtime)\n",
            "    _apply_extract_rules(case, body, runtime)\n",
            "    resource_key = str(case.get('resource_key') or 'default')\n",
            "    state = _resource_state(runtime, resource_key)\n",
            "    if case.get('case_id', '').endswith('verify_deleted'):\n",
            "        rows = _extract_value(body, 'data.list') or []\n",
            "        assert isinstance(rows, list), '删除校验接口未返回列表结果'\n",
            "        assert not any(isinstance(item, dict) and _matches_lookup(item, state) for item in rows), '目标对象仍存在，删除校验失败'\n",
            "    if case.get('case_id', '').endswith('lookup_after_add'):\n",
            "        rows = _extract_value(body, 'data.list') or []\n",
            "        assert isinstance(rows, list) and rows, '回查未命中任何记录'\n",
            "        matched = next((item for item in rows if isinstance(item, dict) and _matches_lookup(item, state)), None)\n",
            "        if matched and matched.get('id') is not None:\n",
            "            state['resource_id'] = matched.get('id')\n\n",
            "def _run_scene(scene_id: str, case_ids: List[str]) -> None:\n",
            "    runtime = _new_runtime_context()\n",
            "    for case_id in case_ids:\n",
            "        _run_case(CASE_INDEX[case_id], runtime)\n\n",
        ]

        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            scene_id = str(scene.get("scene_id") or "").strip()
            if not scene_id:
                continue
            safe_name = self._safe_python_name(scene_id)
            parts.extend(
                [
                    f"def test_scene_{safe_name}() -> None:\n",
                    f"    scene = SCENE_INDEX[{json.dumps(scene_id, ensure_ascii=False)}]\n",
                    "    _run_scene(scene['scene_id'], scene.get('steps') or [])\n\n",
                ]
            )

        scene_case_ids = {
            str(case_id)
            for scene in scenes
            if isinstance(scene, dict)
            for case_id in (scene.get("steps") or [])
        }
        for case in cases:
            if not isinstance(case, dict):
                continue
            case_id = str(case.get("case_id") or "").strip()
            if not case_id or case_id in scene_case_ids:
                continue
            safe_name = self._safe_python_name(case_id)
            parts.extend(
                [
                    f"def test_case_{safe_name}() -> None:\n",
                    "    runtime = _new_runtime_context()\n",
                    f"    _run_case(CASE_INDEX[{json.dumps(case_id, ensure_ascii=False)}], runtime)\n\n",
                ]
            )

        if not scenes and not cases:
            parts.extend(
                [
                    "def test_empty_suite_placeholder() -> None:\n",
                    "    assert True\n",
                ]
            )

        return "".join(parts)

    @staticmethod
    def _build_embedded_json_literal(value: Any) -> str:
        return repr(json.dumps(value, ensure_ascii=False))

    def _safe_python_name(self, value: str) -> str:
        normalized = []
        for character in str(value or ""):
            if character.isalnum() or character == "_":
                normalized.append(character)
            else:
                normalized.append("_")
        collapsed = "".join(normalized).strip("_")
        return collapsed or "generated"
