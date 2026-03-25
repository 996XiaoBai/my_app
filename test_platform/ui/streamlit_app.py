"""旧 Streamlit 入口的兼容壳。"""

import runpy


def main() -> None:
    """统一回流到主入口，避免继续维护两套 Streamlit 页面。"""
    runpy.run_module("test_platform.app", run_name="__main__")


if __name__ == "__main__":
    main()
