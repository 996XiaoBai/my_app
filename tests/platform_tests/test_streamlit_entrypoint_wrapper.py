from pathlib import Path


def test_app_entrypoint_is_a_wrapper_without_sys_path_hack():
    source = Path("test_platform/app.py").read_text(encoding="utf-8")

    assert 'runpy.run_module("test_platform.ui.main_streamlit_app", run_name="__main__")' in source
    assert "sys.path.insert" not in source
    assert "sys.path.append" not in source


def test_main_streamlit_app_contains_actual_ui_implementation():
    source = Path("test_platform/ui/main_streamlit_app.py").read_text(encoding="utf-8")

    assert "st.set_page_config(" in source
    assert "from test_platform.core.services.review_service import ReviewService" in source
