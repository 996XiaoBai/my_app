import test_platform.api_server as api_server


def test_create_app_registers_core_routes():
    app = api_server.create_app()
    route_paths = {route.path for route in app.router.routes}

    assert app.title == "QA Workbench API Bridge"
    assert "/health" in route_paths
    assert "/recommend-experts" in route_paths
    assert "/run" in route_paths
    assert "/run/stream" in route_paths
    assert "/api/dashboard/stats" in route_paths
    assert "/api/history/reports" in route_paths
    assert "/api/history/reports/{report_id}" in route_paths
    assert "/api/history/reports/{report_id}/artifacts/{artifact_key}" in route_paths
    assert "/api/tapd/story" in route_paths
    assert "/api/test-cases/export" in route_paths
