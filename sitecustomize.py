import warnings


# 在 Python 启动阶段提前屏蔽 Python 3.7 下 cryptography 的已知弃用告警，
# 避免 pytest 初始化期间在导入第三方库时输出无业务价值的噪音。
warnings.filterwarnings(
    "ignore",
    message=r"Python 3\.7 is no longer supported by the Python core team.*",
)
