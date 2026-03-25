"""测试平台 Streamlit 主入口兼容壳。"""

import runpy
from pathlib import Path


def main() -> None:
    """优先按模块方式回流；若启动器未注入包路径，则回退到文件路径执行。"""
    try:
        runpy.run_module("test_platform.ui.main_streamlit_app", run_name="__main__")
    except ModuleNotFoundError:
        runpy.run_path(
            str(Path(__file__).with_name("ui").joinpath("main_streamlit_app.py")),
            run_name="__main__",
        )


if __name__ == "__main__":
    main()
