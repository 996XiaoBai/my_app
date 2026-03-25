from pathlib import Path
from subprocess import CompletedProcess

from test_platform.core.services.api_test_execution_service import ApiTestExecutionService


def test_api_test_execution_service_executes_pytest_and_collects_artifacts(tmp_path, monkeypatch):
    service = ApiTestExecutionService(
        history_base_dir=str(tmp_path),
        python_executable="/usr/bin/python3",
    )

    captured = {}

    def fake_run(command, cwd, capture_output, text, timeout):
        captured["command"] = command
        captured["cwd"] = cwd

        junit_path = Path(cwd) / "junit.xml"
        junit_path.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="2" failures="0" errors="0" skipped="0" time="1.23"/>
</testsuites>
""",
            encoding="utf-8",
        )
        return CompletedProcess(
            args=command,
            returncode=0,
            stdout="2 passed in 1.23s",
            stderr="",
        )

    monkeypatch.setattr("test_platform.core.services.api_test_execution_service.subprocess.run", fake_run)

    result = service.execute_pack(
        spec={
            "title": "默认模块",
            "servers": [{"url": "https://example.com"}],
            "resources": [
                {
                    "resource_key": "platformGoods",
                    "lookup_fields": ["title", "businessId", "jumpUrl"],
                }
            ],
            "operations": [
                {
                    "operation_id": "POST /admin/platformGoods/add",
                    "path": "/admin/platformGoods/add",
                    "method": "POST",
                    "category": "create",
                    "resource_key": "platformGoods",
                    "request_field_specs": {
                        "title": {"type": "string"},
                        "businessId": {"type": "integer"},
                        "jumpUrl": {"type": "string"},
                    },
                }
            ],
        },
        cases=[
            {
                "case_id": "platformGoods_add_success",
                "title": "新增平台带货成功",
                "operation_id": "POST /admin/platformGoods/add",
                "resource_key": "platformGoods",
                "category": "create",
                "depends_on": [],
                "extract": [],
            }
        ],
        scenes=[],
        params={
            "base_url": "https://example.com",
            "headers": {"Authorization": "Bearer demo"},
            "cookies": {"userId": "1001"},
            "timeout": 15,
            "verify_ssl": False,
        },
        script="import pytest\n\ndef test_demo():\n    assert True\n",
    )

    assert result["status"] == "passed"
    assert result["stats"]["total"] == 2
    assert result["stats"]["passed"] == 2
    assert result["artifacts"]["run_dir"].startswith(str(tmp_path))
    assert Path(result["artifacts"]["compiled_script"]).exists()
    assert Path(result["artifacts"]["asset_snapshot"]).exists()
    assert Path(result["artifacts"]["case_snapshot"]).exists()
    assert Path(result["artifacts"]["scene_snapshot"]).exists()
    assert Path(result["artifacts"]["execution_summary"]).exists()
    assert '"base_url": "https://example.com"' in result["runtime_config_content"]
    assert '"title": "默认模块"' in result["asset_snapshot_content"]
    assert '"case_id": "platformGoods_add_success"' in result["case_snapshot_content"]
    assert result["scene_snapshot_content"] == "[]"
    compiled_script = Path(result["artifacts"]["compiled_script"]).read_text(encoding="utf-8")
    assert "https://example.com" in compiled_script
    assert "Authorization" in compiled_script
    assert result["junit_xml_content"].startswith('<?xml version="1.0" encoding="utf-8"?>')
    assert captured["command"][:3] == ["/usr/bin/python3", "-m", "pytest"]


def test_api_test_execution_service_marks_failed_when_junit_reports_failures(tmp_path, monkeypatch):
    service = ApiTestExecutionService(
        history_base_dir=str(tmp_path),
        python_executable="/usr/bin/python3",
    )

    def fake_run(command, cwd, capture_output, text, timeout):
        junit_path = Path(cwd) / "junit.xml"
        junit_path.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="3" failures="1" errors="0" skipped="0" time="2.34"/>
</testsuites>
""",
            encoding="utf-8",
        )
        return CompletedProcess(
            args=command,
            returncode=1,
            stdout="1 failed, 2 passed in 2.34s",
            stderr="AssertionError: failed",
        )

    monkeypatch.setattr("test_platform.core.services.api_test_execution_service.subprocess.run", fake_run)

    result = service.execute_pack(
        spec={"title": "默认模块", "servers": [{"url": "https://example.com"}], "resources": [], "operations": []},
        cases=[],
        scenes=[],
        params={},
        script="",
    )

    assert result["status"] == "failed"
    assert result["stats"]["failed"] == 1
    assert "1 failed" in result["stdout"]


def test_api_test_execution_service_collects_allure_artifacts_when_supported(tmp_path, monkeypatch):
    service = ApiTestExecutionService(
        history_base_dir=str(tmp_path),
        python_executable="/usr/bin/python3",
    )
    monkeypatch.setattr(service, "_supports_allure_results", lambda: True)

    captured = {}

    def fake_run(command, cwd, capture_output, text, timeout):
        captured["command"] = command
        run_dir = Path(cwd)
        (run_dir / "junit.xml").write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0" time="0.45"/>
</testsuites>
""",
            encoding="utf-8",
        )
        allure_dir = run_dir / "allure-results"
        allure_dir.mkdir(parents=True, exist_ok=True)
        (allure_dir / "result.json").write_text('{"name": "demo"}', encoding="utf-8")
        return CompletedProcess(
            args=command,
            returncode=0,
            stdout="1 passed in 0.45s",
            stderr="",
        )

    monkeypatch.setattr("test_platform.core.services.api_test_execution_service.subprocess.run", fake_run)

    result = service.execute_pack(
        spec={"title": "默认模块", "servers": [{"url": "https://example.com"}], "resources": [], "operations": []},
        cases=[],
        scenes=[],
        params={},
        script="",
    )

    assert "--alluredir=allure-results" in captured["command"]
    assert result["artifacts"]["allure_results"].endswith("allure-results")
    assert result["artifacts"]["allure_archive"].endswith("allure-results.zip")
    assert Path(result["artifacts"]["allure_results"]).is_dir()
    assert Path(result["artifacts"]["allure_archive"]).is_file()


def test_api_test_execution_service_compiled_script_supports_json_style_booleans(tmp_path, monkeypatch):
    service = ApiTestExecutionService(
        history_base_dir=str(tmp_path),
        python_executable="/usr/bin/python3",
    )

    def fake_run(command, cwd, capture_output, text, timeout):
        junit_path = Path(cwd) / "junit.xml"
        junit_path.write_text(
            """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="1" failures="0" errors="0" skipped="0" time="0.05"/>
</testsuites>
""",
            encoding="utf-8",
        )
        return CompletedProcess(
            args=command,
            returncode=0,
            stdout="1 passed in 0.05s",
            stderr="",
        )

    monkeypatch.setattr("test_platform.core.services.api_test_execution_service.subprocess.run", fake_run)

    result = service.execute_pack(
        spec={
            "title": "布尔配置验证",
            "servers": [{"url": "https://example.com"}],
            "resources": [],
            "operations": [],
            "flags": {"enabled": True},
        },
        cases=[],
        scenes=[],
        params={
            "base_url": "https://example.com",
            "verify_ssl": True,
            "headers": {"X-Debug": "1"},
            "request_overrides": {"demo_case": {"enabled": True, "nullable": None}},
        },
        script="",
    )

    compiled_script = Path(result["artifacts"]["compiled_script"]).read_text(encoding="utf-8")

    exec(compiled_script, {"__name__": "test_module"})
