import os
from dotenv import load_dotenv  # type: ignore

# 加载环境变量
load_dotenv()


def _get_preferred_env(primary_env_name: str, fallback_env_name: str, default=None):
    """优先读取测试平台专用环境变量，未配置时回退到通用变量。"""
    primary_value = os.getenv(primary_env_name)
    if primary_value:
        return primary_value

    if default is None:
        return os.getenv(fallback_env_name)
    return os.getenv(fallback_env_name, default)


def get_test_platform_dify_api_base() -> str:
    """读取测试平台使用的 Dify 地址。"""
    return os.getenv("DIFY_API_BASE", "https://dify.cvte.com/v1")


def get_test_platform_dify_api_key():
    """读取测试平台使用的 Dify Key。"""
    return _get_preferred_env("TEST_PLATFORM_DIFY_API_KEY", "DIFY_API_KEY")


def get_test_platform_dify_user_id(default: str = "anonymous") -> str:
    """读取测试平台使用的 Dify 用户标识。"""
    return _get_preferred_env("TEST_PLATFORM_DIFY_USER_ID", "DIFY_USER_ID", default)

class AgentConfig:
    # 项目根目录
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    
    # Dify API
    DIFY_API_BASE = get_test_platform_dify_api_base()
    DIFY_API_KEY = get_test_platform_dify_api_key()
    DIFY_USER_ID = get_test_platform_dify_user_id()
    
    # TAPD API
    TAPD_API_USER = os.getenv("TAPD_API_USER")
    TAPD_API_PASSWORD = os.getenv("TAPD_API_PASSWORD")
    TAPD_WORKSPACE_ID = os.getenv("TAPD_WORKSPACE_ID")
    
    # 飞书 API
    FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
    FEISHU_FOLDER_TOKEN = os.getenv("FEISHU_FOLDER_TOKEN", "")
    FEISHU_OWNER_USER_ID = os.getenv("FEISHU_OWNER_USER_ID", "")
    # 周报专用的知识库节点 Token
    FEISHU_WEEKLY_REPORT_FOLDER_TOKEN = os.getenv("FEISHU_WEEKLY_REPORT_FOLDER_TOKEN", "")
    
    # 技能目录
    SKILLS_DIR = os.path.join(PROJECT_ROOT, ".agent/skills")
    
    # PDF 处理
    PDF_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
    DEFAULT_MAX_PAGES = 10
    DEFAULT_IMAGE_WIDTH = 1024
    image_quality = 85
    chunk_size = 5

    @classmethod
    def get_skill_path(cls, skill_name: str) -> str:
        return os.path.join(cls.SKILLS_DIR, skill_name, "SKILL.md")

    @classmethod
    def validate(cls):
        if not cls.DIFY_API_KEY:
            raise ValueError("Missing TEST_PLATFORM_DIFY_API_KEY or DIFY_API_KEY. Please check your .env file.")
