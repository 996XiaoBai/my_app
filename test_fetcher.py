import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_news_bot.qa_news_fetcher import QANewsFetcher


def test_qa_fetcher_loads_repo_config():
    """验证根目录执行 pytest 时，QA 抓取器仍能正确加载配置。"""
    config_path = PROJECT_ROOT / "ai_news_bot" / "config" / "qa_tools_config.yaml"

    fetcher = QANewsFetcher(str(config_path))

    assert fetcher.filter_config.get("max_count") == 10
