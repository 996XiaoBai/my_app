from pathlib import Path

import cli


def test_python_version_file_declares_311_baseline():
    version_file = Path(".python-version")

    assert version_file.exists()
    assert version_file.read_text(encoding="utf-8").strip() == "3.11"


def test_shared_python_resolver_enforces_python_311_or_newer():
    source = Path("test_platform/scripts/resolve_python.sh").read_text(encoding="utf-8")

    assert "MIN_PYTHON_MINOR=11" in source
    assert "sys.version_info" in source
    assert 'append_candidate "$PROJECT_ROOT/test_platform/.venv/bin/python"' in source


def test_start_scripts_use_shared_python_resolver():
    start_web_ui_source = Path("start_web_ui.sh").read_text(encoding="utf-8")
    start_api_source = Path("start.sh").read_text(encoding="utf-8")

    assert "test_platform/scripts/resolve_python.sh" in start_web_ui_source
    assert "test_platform/scripts/resolve_python.sh" in start_api_source


def test_cli_reports_supported_python_version_correctly():
    assert cli.is_supported_python_version((3, 11, 0)) is True
    assert cli.is_supported_python_version((3, 12, 2)) is True
    assert cli.is_supported_python_version((3, 10, 14)) is False


def test_makefile_uses_shared_python_resolver():
    source = Path("Makefile").read_text(encoding="utf-8")

    assert "test_platform/scripts/resolve_python.sh" in source
    assert "$(PYTHON_BIN) cli.py ui" in source
