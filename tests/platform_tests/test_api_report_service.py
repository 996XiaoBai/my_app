from test_platform.core.services.api_report_service import ApiReportService


def test_api_report_service_builds_failure_summary_and_artifact_labels():
    service = ApiReportService()

    report = service.build_report(
        spec={"title": "默认模块"},
        cases=[
            {"case_id": "platformGoods_add_success"},
            {"case_id": "platformGoods_delete_success"},
        ],
        scenes=[{"scene_id": "platformGoods_crud_flow"}],
        execution={
            "status": "failed",
            "summary": "执行 3 条 pytest 用例，1 条失败。",
            "stats": {
                "total": 3,
                "passed": 1,
                "failed": 1,
                "errors": 1,
                "skipped": 0,
            },
            "junit_xml_content": """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="pytest" tests="3" failures="1" errors="1" skipped="0">
    <testcase classname="test_api_suite" name="test_add_platform_goods" />
    <testcase classname="test_api_suite" name="test_delete_platform_goods">
      <failure message="AssertionError">assert 500 == 200</failure>
    </testcase>
    <testcase classname="test_api_suite" name="test_verify_platform_goods">
      <error message="RuntimeError">lookup failed</error>
    </testcase>
  </testsuite>
</testsuites>""",
            "artifacts": {
                "run_dir": "/tmp/api_runs/run-001",
                "junit_xml": "/tmp/api_runs/run-001/junit.xml",
                "compiled_script": "/tmp/api_runs/run-001/test_api_suite.py",
            },
        },
    )

    assert report["status"] == "failed"
    assert report["headline"] == "默认模块：执行失败"
    assert report["summary_lines"] == [
        "总 3 / 通过 1 / 失败 1 / 异常 1 / 跳过 0",
        "结构化用例 2 条 / 关联场景 1 个",
        "执行 3 条 pytest 用例，1 条失败。",
    ]
    assert report["failure_cases"] == [
        {
            "key": "failure-0",
            "title": "test_api_suite::test_delete_platform_goods",
            "detail": "AssertionError",
            "kind": "failure",
        },
        {
            "key": "error-1",
            "title": "test_api_suite::test_verify_platform_goods",
            "detail": "RuntimeError",
            "kind": "error",
        },
    ]
    assert report["artifact_labels"] == [
        {"key": "compiled_script", "label": "执行脚本", "value": "/tmp/api_runs/run-001/test_api_suite.py"},
        {"key": "junit_xml", "label": "JUnit 报告", "value": "/tmp/api_runs/run-001/junit.xml"},
        {"key": "run_dir", "label": "运行目录", "value": "/tmp/api_runs/run-001"},
    ]


def test_api_report_service_returns_empty_failure_cases_for_non_execution_payload():
    service = ApiReportService()

    report = service.build_report(
        spec={"title": "默认模块"},
        cases=[],
        scenes=[],
        execution={},
    )

    assert report["status"] == "not_executed"
    assert report["failure_cases"] == []
    assert report["artifact_labels"] == []


def test_api_report_service_includes_allure_artifacts_when_present():
    service = ApiReportService()

    report = service.build_report(
        spec={"title": "默认模块"},
        cases=[],
        scenes=[],
        execution={
            "status": "passed",
            "stats": {"total": 1, "passed": 1, "failed": 0, "errors": 0, "skipped": 0},
            "artifacts": {
                "allure_results": "/tmp/api_runs/run-001/allure-results",
                "allure_archive": "/tmp/api_runs/run-001/allure-results.zip",
            },
        },
    )

    assert report["artifact_labels"] == [
        {"key": "allure_results", "label": "Allure 原始结果", "value": "/tmp/api_runs/run-001/allure-results"},
        {"key": "allure_archive", "label": "Allure 压缩包", "value": "/tmp/api_runs/run-001/allure-results.zip"},
    ]
