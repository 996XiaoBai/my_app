from pathlib import Path


def test_start_web_ui_avoids_hardcoded_python_path_and_uses_shared_port():
    source = Path("start_web_ui.sh").read_text(encoding="utf-8")

    assert "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" not in source
    assert "TEST_PLATFORM_STREAMLIT_PORT" in source
    assert "PYTHON_BIN" in source
    assert "test_platform/app.py" in source


def test_cli_ui_uses_shared_streamlit_port_variable():
    source = Path("cli.py").read_text(encoding="utf-8")

    assert 'os.getenv("TEST_PLATFORM_STREAMLIT_PORT", "8501")' in source
    assert '--server.port", streamlit_port' in source
