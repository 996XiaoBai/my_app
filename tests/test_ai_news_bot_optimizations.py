import importlib
import os
import sys
import asyncio
import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ai_news_bot.ai_news_fetcher import AINewsFetcher, NewsItem
from ai_news_bot.qa_news_fetcher import QANewsFetcher
from ai_news_bot.services.common.dify_client import DifyRateLimitError
from ai_news_bot import main_news_bot
from ai_news_bot import run_scheduler, run_qa_bot
import cli


class _FakeAsyncResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    async def json(self):
        return self._payload

    async def text(self):
        if isinstance(self._payload, str):
            return self._payload
        return json.dumps(self._payload, ensure_ascii=False)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, get_payload=None, post_payload=None):
        self.get_payload = get_payload
        self.post_payload = post_payload
        self.last_post_json = None

    def get(self, *args, **kwargs):
        return _FakeAsyncResponse(self.get_payload)

    def post(self, *args, **kwargs):
        self.last_post_json = kwargs.get("json")
        return _FakeAsyncResponse(self.post_payload)


@pytest.mark.parametrize(
    "module_name",
    [
        "ai_news_bot.qa_news_fetcher",
        "ai_news_bot.wecom_bot_notifier",
        "ai_news_bot.run_qa_bot",
        "ai_news_bot.main_news_bot",
        "ai_news_bot.run_scheduler",
    ],
)
def test_ai_news_bot_modules_support_package_imports(module_name):
    module = importlib.import_module(module_name)
    assert module is not None


def test_is_within_time_window_filters_expired_entries():
    fetcher = AINewsFetcher()
    fetcher.filter_config = {"time_window_hours": 24}

    fresh_entry = {
        "published": format_datetime(datetime.now(timezone.utc) - timedelta(hours=1))
    }
    expired_entry = {
        "published": format_datetime(datetime.now(timezone.utc) - timedelta(hours=72))
    }

    assert fetcher._is_within_time_window(fresh_entry) is True
    assert fetcher._is_within_time_window(expired_entry) is False


def test_is_within_time_window_supports_source_specific_override():
    fetcher = AINewsFetcher()
    fetcher.filter_config = {"time_window_hours": 48}
    entry = {
        "published": format_datetime(datetime.now(timezone.utc) - timedelta(days=5))
    }

    assert fetcher._is_within_time_window(entry) is False
    assert fetcher._is_within_time_window(entry, time_window_hours=24 * 7) is True


def test_fetch_rss_source_supports_source_specific_exclude_keywords():
    fetcher = AINewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["Appium"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload="""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <item>
              <title>@appium/fake-plugin@4.1.1</title>
              <link>https://example.com/fake-plugin</link>
              <pubDate>Sat, 22 Mar 2026 08:00:00 GMT</pubDate>
              <description>Appium fake plugin release</description>
            </item>
            <item>
              <title>Appium 3.2.2 Released</title>
              <link>https://example.com/appium-3-2-2</link>
              <pubDate>Sat, 22 Mar 2026 07:00:00 GMT</pubDate>
              <description>Appium server release with testing workflow fixes</description>
            </item>
          </channel>
        </rss>
        """
    )

    items = asyncio.run(
        fetcher._fetch_rss_source(
            session,
            {
                "name": "Appium 官方版本发布",
                "url": "https://example.com/appium.xml",
                "type": "rss",
                "exclude_keywords": ["fake-plugin", "@appium/"],
            },
        )
    )

    assert [item.title for item in items] == ["Appium 3.2.2 Released"]


def test_fetch_rss_source_uses_source_name_for_release_relevance():
    fetcher = AINewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["Cucumber"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload="""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>v7.34.3</title>
            <link href="https://example.com/cucumber-jvm-v7-34-3"/>
            <updated>2026-03-21T08:00:00Z</updated>
            <content type="html">Fixed dependency updates for the JVM implementation.</content>
          </entry>
        </feed>
        """
    )

    items = asyncio.run(
        fetcher._fetch_rss_source(
            session,
            {
                "name": "Cucumber JVM 官方版本发布",
                "url": "https://example.com/cucumber-jvm.atom",
                "type": "rss",
            },
        )
    )

    assert [item.title for item in items] == ["v7.34.3"]


def test_fetch_rss_source_supports_source_specific_exclude_title_patterns():
    fetcher = AINewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["Selenium"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload="""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Nightly</title>
            <link href="https://example.com/selenium-nightly"/>
            <updated>2026-03-22T08:00:00Z</updated>
            <content type="html">Nightly build for Selenium.</content>
          </entry>
          <entry>
            <title>Selenium 4.41.0</title>
            <link href="https://example.com/selenium-4-41-0"/>
            <updated>2026-03-21T08:00:00Z</updated>
            <content type="html">Stable Selenium release with WebDriver fixes.</content>
          </entry>
          <entry>
            <title>Selenium 4.42.0-rc1</title>
            <link href="https://example.com/selenium-4-42-0-rc1"/>
            <updated>2026-03-20T08:00:00Z</updated>
            <content type="html">Release candidate for Selenium.</content>
          </entry>
        </feed>
        """
    )

    items = asyncio.run(
        fetcher._fetch_rss_source(
            session,
                {
                    "name": "Selenium 官方版本发布",
                    "url": "https://example.com/selenium.atom",
                    "type": "rss",
                    "exclude_title_patterns": [r"(?i)\bnightly\b", r"(?i)\brc\d+\b"],
                },
            )
        )

    assert [item.title for item in items] == ["Selenium 4.41.0"]


def test_fetch_rss_source_allows_prerelease_titles_when_enabled():
    fetcher = AINewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["Selenium"],
        "exclude_keywords": [],
        "allow_prerelease_titles": True,
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload="""<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <entry>
            <title>Nightly</title>
            <link href="https://example.com/selenium-nightly"/>
            <updated>2026-03-22T08:00:00Z</updated>
            <content type="html">Nightly build for Selenium.</content>
          </entry>
          <entry>
            <title>Selenium 4.41.0</title>
            <link href="https://example.com/selenium-4-41-0"/>
            <updated>2026-03-21T08:00:00Z</updated>
            <content type="html">Stable Selenium release with WebDriver fixes.</content>
          </entry>
          <entry>
            <title>Selenium 4.42.0-rc1</title>
            <link href="https://example.com/selenium-4-42-0-rc1"/>
            <updated>2026-03-20T08:00:00Z</updated>
            <content type="html">Release candidate for Selenium.</content>
          </entry>
        </feed>
        """
    )

    items = asyncio.run(
        fetcher._fetch_rss_source(
            session,
            {
                "name": "Selenium 官方版本发布",
                "url": "https://example.com/selenium.atom",
                "type": "rss",
                "exclude_title_patterns": [r"(?i)\bnightly\b", r"(?i)\brc\d+\b"],
            },
        )
    )

    assert [item.title for item in items] == ["Nightly", "Selenium 4.41.0", "Selenium 4.42.0-rc1"]


def test_is_relevant_with_reason_supports_source_require_keywords():
    fetcher = AINewsFetcher()
    fetcher.filter_config = {
        "keywords": ["AI", "测试"],
        "exclude_keywords": [],
    }

    is_valid, reject_reason = fetcher._is_relevant_with_reason(
        "The most exciting moment in software history",
        source={
            "name": "mabl 官方博客",
            "require_keywords": ["quality", "testing", "automation", "Playwright"],
        },
    )

    assert is_valid is False
    assert reject_reason == "missing_required_keywords"

    is_valid, reject_reason = fetcher._is_relevant_with_reason(
        "Playwright automation improves quality at scale",
        source={
            "name": "mabl 官方博客",
            "require_keywords": ["quality", "testing", "automation", "Playwright"],
        },
    )

    assert is_valid is True
    assert reject_reason == "whitelist_hit"


def test_fetch_all_async_returns_candidate_pool_before_publish_cutoff(monkeypatch):
    fetcher = AINewsFetcher()
    fetcher.sources = [
        {"name": "高优先级", "priority": 1},
        {"name": "次优先级", "priority": 2},
    ]
    fetcher.filter_config = {"max_count": 2, "candidate_pool_multiplier": 3}

    async def fake_fetch_source(_session, source):
        if source["name"] == "高优先级":
            return [
                NewsItem("A1", "https://a1", "2026-03-21", "高优先级"),
                NewsItem("A2", "https://a2", "2026-03-21", "高优先级"),
            ]
        return [
            NewsItem("B1", "https://b1", "2026-03-21", "次优先级"),
            NewsItem("B2", "https://b2", "2026-03-21", "次优先级"),
        ]

    monkeypatch.setattr(fetcher, "_fetch_source", fake_fetch_source)

    items = asyncio.run(fetcher.fetch_all_async())

    assert [item.title for item in items] == ["A1", "A2", "B1", "B2"]


def test_fetch_all_async_disables_source_cap_when_global_max_per_source_is_zero(monkeypatch):
    fetcher = AINewsFetcher()
    fetcher.sources = [
        {"name": "高优先级", "priority": 1, "max_per_source": 1},
        {"name": "次优先级", "priority": 2, "max_per_source": 1},
    ]
    fetcher.filter_config = {"max_count": 2, "candidate_pool_multiplier": 3, "max_per_source": 0}

    async def fake_fetch_source(_session, source):
        if source["name"] == "高优先级":
            return [
                NewsItem("A1", "https://a1", "2026-03-21", "高优先级"),
                NewsItem("A2", "https://a2", "2026-03-21", "高优先级"),
            ]
        return [
            NewsItem("B1", "https://b1", "2026-03-21", "次优先级"),
            NewsItem("B2", "https://b2", "2026-03-21", "次优先级"),
        ]

    monkeypatch.setattr(fetcher, "_fetch_source", fake_fetch_source)

    items = asyncio.run(fetcher.fetch_all_async())

    assert [item.title for item in items] == ["A1", "A2", "B1", "B2"]


def test_fetch_all_async_deduplicates_by_normalized_url_and_title(monkeypatch):
    fetcher = AINewsFetcher()
    fetcher.sources = [{"name": "测试源", "priority": 1}]
    fetcher.filter_config = {"max_count": 5, "candidate_pool_multiplier": 1}

    async def fake_fetch_source(_session, source):
        return [
            NewsItem("OpenAI 发布新模型", "https://example.com/post?id=1&utm_source=wechat", "2026-03-21", "测试源"),
            NewsItem("OpenAI 发布新模型", "https://example.com/post?id=1", "2026-03-21", "测试源"),
            NewsItem("OpenAI 发布 新模型", "https://mirror.example.com/repost/123", "2026-03-21", "测试源"),
        ]

    monkeypatch.setattr(fetcher, "_fetch_source", fake_fetch_source)

    items = asyncio.run(fetcher.fetch_all_async())

    assert len(items) == 1
    assert items[0].link == "https://example.com/post?id=1&utm_source=wechat"


def test_sent_history_filters_by_title_fingerprint(tmp_path):
    fetcher = AINewsFetcher()
    fetcher.history_file = str(tmp_path / "sent_articles.json")
    fetcher.sent_history = []

    fetcher.save_to_history([
        NewsItem("OpenAI 发布新模型", "https://example.com/post?id=1", "2026-03-21", "测试源")
    ])

    assert fetcher._is_in_sent_history("https://mirror.example.com/repost/1", "OpenAI 发布 新模型") is True


def test_summarize_news_uses_score_to_reorder_results(monkeypatch):
    responses = {
        "低分文章": json.dumps(
            {
                "title": "低分文章",
                "summary": "一般",
                "highlights": "",
                "score": 6,
                "category": "其他",
                "score_breakdown": {"timeliness": 4, "source_authority": 7, "technical_depth": 5, "practical_value": 6},
            },
            ensure_ascii=False,
        ),
        "高分文章": json.dumps(
            {
                "title": "高分文章",
                "summary": "很好",
                "highlights": "",
                "score": 9,
                "category": "其他",
                "score_breakdown": {"timeliness": 8, "source_authority": 9, "technical_depth": 9, "practical_value": 8},
            },
            ensure_ascii=False,
        ),
    }

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, _content, prompt_template=None):
            return responses[title]

    monkeypatch.setattr(main_news_bot, "DifyClient", FakeDifyClient)

    bot = main_news_bot.NewsBot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {"min_quality_score": 3, "max_count": 20}

    news_items = [
        NewsItem("低分文章", "https://low", "2026-03-21", "源A", summary="摘要"),
        NewsItem("高分文章", "https://high", "2026-03-21", "源B", summary="摘要"),
    ]

    summarized = bot._summarize_news(news_items)

    assert [item.title for item in summarized] == ["高分文章", "低分文章"]
    assert summarized[0].score_breakdown["technical_depth"] == 9


def test_summarize_news_drops_items_when_dify_output_is_invalid(monkeypatch):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, _content, prompt_template=None):
            return "not-json"

    monkeypatch.setattr(main_news_bot, "DifyClient", FakeDifyClient)

    bot = main_news_bot.NewsBot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {"min_quality_score": 3, "max_count": 20}

    news_items = [
        NewsItem("无效输出", "https://invalid", "2026-03-21", "源A", summary="摘要"),
    ]

    summarized = bot._summarize_news(news_items)

    assert summarized == []


def test_summarize_news_falls_back_to_original_title_when_dify_title_is_empty(monkeypatch):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, _content, prompt_template=None):
            return json.dumps(
                {
                    "title": "   ",
                    "summary": "这是有效摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "其他",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "technical_depth": 7,
                        "practical_value": 7,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(main_news_bot, "DifyClient", FakeDifyClient)

    bot = main_news_bot.NewsBot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {"min_quality_score": 3, "max_count": 20}

    news_items = [
        NewsItem("OpenAI releases GPT-5.1", "https://example.com/gpt51", "2026-03-21", "OpenAI", summary="摘要"),
    ]

    summarized = bot._summarize_news(news_items)

    assert len(summarized) == 1
    assert summarized[0].title == "OpenAI releases GPT-5.1"
    assert summarized[0].original_title == "OpenAI releases GPT-5.1"


def test_summarize_news_prefers_full_content_over_summary(monkeypatch):
    captured_queries = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            captured_queries.append(content)
            return json.dumps(
                {
                    "title": title,
                    "summary": "正文摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "模型进展",
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(main_news_bot, "DifyClient", FakeDifyClient)

    bot = main_news_bot.NewsBot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {"min_quality_score": 3, "max_count": 20}

    item = NewsItem("正文优先文章", "https://full-text", "2026-03-21", "源A", summary="短摘要")
    item.content_text = "这是更完整的正文内容，用于质量判断。"

    bot._summarize_news([item])

    assert captured_queries == ["这是更完整的正文内容，用于质量判断。"]


def test_qa_summarize_prompt_mentions_official_testing_framework_updates(monkeypatch):
    captured_prompt_templates = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            captured_prompt_templates.append(prompt_template)
            return json.dumps(
                {
                    "title": title,
                    "summary": "这是测试框架版本更新摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试框架",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 7,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "max_per_source_final": 20,
        "max_per_category_final": 20,
    }

    news_items = [
        NewsItem("Cypress v15.12.0", "https://example.com/cypress", "2026-03-21", "Cypress 官方版本发布", summary="修复与增强")
    ]

    summarized = bot._summarize_news(news_items)

    assert len(summarized) == 1
    assert "主流测试框架或工具链的官方版本更新" in captured_prompt_templates[0]


def test_qa_summarize_prompt_mentions_testing_methodology_and_release_safety(monkeypatch):
    captured_prompt_templates = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            captured_prompt_templates.append(prompt_template)
            return json.dumps(
                {
                    "title": title,
                    "summary": "这是测试方法论文章摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试策略与质量工程",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "max_per_source_final": 20,
        "max_per_category_final": 20,
    }

    news_items = [
        NewsItem(
            "The Way of TDD",
            "https://example.com/tdd",
            "2026-03-21",
            "Google Testing Blog",
            summary="Testing methodology and safe rollout practices",
        )
    ]

    summarized = bot._summarize_news(news_items)

    assert len(summarized) == 1
    assert "测试驱动开发（TDD）" in captured_prompt_templates[0]
    assert "功能开关默认值" in captured_prompt_templates[0]
    assert "测试方法论、质量工程策略" in captured_prompt_templates[0]


def test_qa_summarize_news_passes_source_and_scenario_context_to_dify(monkeypatch, tmp_path):
    captured_contents = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            captured_contents.append(content)
            return json.dumps(
                {
                    "title": title,
                    "summary": "这是有效测试策略摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试策略与质量工程",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.fetcher.filter_config["min_quality_score"] = 6
    bot.fetcher.filter_config["max_count"] = 20

    news_items = [
        NewsItem(
            "The Way of TDD",
            "https://example.com/tdd",
            "2026-03-21",
            "Google Testing Blog",
            summary="Testing methodology and safe rollout practices",
            content_text="正文内容：围绕 TDD、发布安全与回归预防展开。",
            scenario_tags=["测试策略", "质量效能"],
        )
    ]

    summarized = bot._summarize_news(news_items)

    assert len(summarized) == 1
    assert "来源: Google Testing Blog" in captured_contents[0]
    assert "预识别测试场景标签" in captured_contents[0]
    assert "测试策略" in captured_contents[0]
    assert "质量效能" in captured_contents[0]
    assert "正文内容：围绕 TDD、发布安全与回归预防展开。" in captured_contents[0]


def test_qa_summarize_news_falls_back_to_original_title_when_dify_title_is_wrapped_json(monkeypatch, tmp_path):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            return json.dumps(
                {
                    "title": "```json {\"title\": \"AI 测试实践摘要\"} ```",
                    "summary": "这是有效测试摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "智能测试与AI赋能",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.fetcher.filter_config["min_quality_score"] = 6
    bot.fetcher.filter_config["max_count"] = 20

    news_items = [
        NewsItem(
            "Writing tests with Claude Code - part 1 - initial results",
            "https://example.com/claude-tests",
            "2026-03-21",
            "On Test Automation",
            summary="Claude Code testing article",
        )
    ]

    summarized = bot._summarize_news(news_items)

    assert len(summarized) == 1
    assert summarized[0].title == "Writing tests with Claude Code - part 1 - initial results"
    assert summarized[0].original_title == "Writing tests with Claude Code - part 1 - initial results"


def test_qa_summarize_news_rescues_high_confidence_testing_strategy_item(monkeypatch, tmp_path):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            return json.dumps(
                {
                    "title": title,
                    "summary": "这是一篇关于 TDD 与发布安全的实践文章。",
                    "highlights": "",
                    "score": 2,
                    "category": "工程方法",
                    "score_breakdown": {
                        "timeliness": 7,
                        "source_authority": 8,
                        "testing_relevance": 2,
                        "practical_value": 6,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.fetcher.filter_config["min_quality_score"] = 6
    bot.fetcher.filter_config["max_count"] = 20

    news_items = [
        NewsItem(
            "The Way of TDD",
            "https://example.com/tdd",
            "2026-03-21",
            "Google Testing Blog",
            summary="Testing methodology and safe rollout practices",
            content_text="文章讨论测试驱动开发、功能开关默认值、灰度发布与回归预防。",
            scenario_tags=["测试策略", "质量效能"],
            source_priority=1,
        )
    ]

    summarized = bot._summarize_news(news_items)

    assert len(summarized) == 1
    assert summarized[0].score >= 6
    assert bot._current_run_source_metrics["Google Testing Blog"]["low_quality_count"] == 0


def test_qa_low_quality_rejected_items_are_exported_for_review(monkeypatch, tmp_path):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            return json.dumps(
                {
                    "title": title,
                    "summary": "这是一篇泛工程随笔。",
                    "highlights": "",
                    "score": 2,
                    "category": "工程随笔",
                    "score_breakdown": {
                        "timeliness": 5,
                        "source_authority": 6,
                        "testing_relevance": 1,
                        "practical_value": 2,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.review_export_dir = str(tmp_path / "review_exports")
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.fetcher.filter_config["min_quality_score"] = 6
    bot.fetcher.filter_config["max_count"] = 20

    summarized = bot._summarize_news(
        [
            NewsItem(
                "Engineering Leadership Notes",
                "https://example.com/leadership",
                "2026-03-21",
                "Google Testing Blog",
                summary="How to mentor and align engineering teams",
                content_text="文章主要讨论团队协作、沟通和职业成长，没有测试落地机制。",
                source_priority=1,
            )
        ]
    )

    export_path = bot._export_review_report(date_label="2026-03-21")

    assert summarized == []
    assert len(bot.latest_review_report["low_quality_rejected_items"]) == 1
    assert bot._current_run_source_metrics["Google Testing Blog"]["low_quality_count"] == 1
    with open(export_path, "r", encoding="utf-8") as file:
        content = file.read()
    assert "## 被质量闸门丢弃" in content
    assert "Engineering Leadership Notes" in content


def test_qa_summarize_news_keeps_high_confidence_item_with_local_fallback_after_dify_rate_limit(monkeypatch, tmp_path):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            raise DifyRateLimitError("Requests have exceeded the throughput limit")

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)
    monkeypatch.setattr(run_qa_bot.time, "sleep", lambda _seconds: None)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "dify_rate_limit_abort_threshold": 1,
        "dify_rate_limit_retry_rounds": 0,
        "max_per_source_final": 20,
        "max_per_category_final": 20,
    }

    summarized = bot._summarize_news(
        [
            NewsItem(
                "AI 赋能测试实践 03——深度拆解 Agent Browser",
                "https://example.com/agent-browser",
                "2026-03-22",
                "TesterHome AI测试",
                summary="围绕 Agent Browser、Playwright 与 AI 原生浏览器交互展开测试实践复盘。",
                content_text="文章详细复盘了 Agent Browser 与 Playwright 的落地方式，讨论 AI 原生浏览器交互、测试脚本编排和回归验证策略。",
                scenario_tags=["AI赋能测试", "UI自动化"],
                source_priority=2,
            )
        ]
    )

    assert len(summarized) == 1
    assert summarized[0].title == "AI 赋能测试实践 03——深度拆解 Agent Browser"
    assert "Agent Browser" in summarized[0].summary
    assert summarized[0].score == 6
    assert summarized[0].category == "智能测试与AI赋能"
    assert bot.latest_review_report["rate_limit_skipped_items"] == []


def test_qa_summarize_news_keeps_high_confidence_item_with_local_fallback_after_invalid_json(monkeypatch, tmp_path):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            return "not-json"

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "max_per_source_final": 20,
        "max_per_category_final": 20,
    }

    summarized = bot._summarize_news(
        [
            NewsItem(
                "The Way of TDD",
                "https://example.com/tdd",
                "2026-03-22",
                "Google Testing Blog",
                summary="文章围绕 TDD、发布安全和回归预防给出测试工程实践建议。",
                content_text="文章围绕 TDD、发布安全和回归预防给出测试工程实践建议，并讨论如何将质量内建前移到开发阶段。",
                scenario_tags=["测试策略", "质量效能"],
                source_priority=1,
            )
        ]
    )

    assert len(summarized) == 1
    assert summarized[0].title == "The Way of TDD"
    assert "发布安全" in summarized[0].summary
    assert summarized[0].category == "测试策略与质量工程"
    assert summarized[0].score == 6


def test_qa_summarize_news_backs_off_after_dify_rate_limit(monkeypatch):
    sleep_calls = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            self.calls = 0

        def summarize_content(self, title, content, prompt_template=None):
            self.calls += 1
            if self.calls == 1:
                raise DifyRateLimitError("Requests have exceeded the throughput limit")
            return json.dumps(
                {
                    "title": title,
                    "summary": "有效摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试框架",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)
    monkeypatch.setattr(run_qa_bot.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "max_per_source_final": 20,
        "max_per_category_final": 20,
    }

    news_items = [
        NewsItem("第一条", "https://example.com/1", "2026-03-22", "源A", summary="摘要1"),
        NewsItem("第二条", "https://example.com/2", "2026-03-22", "源A", summary="摘要2"),
    ]

    summarized = bot._summarize_news(news_items)

    assert [item.title for item in summarized] == ["第一条", "第二条"]
    assert sleep_calls == [6, 18]
    assert bot._current_run_source_metrics["源A"]["low_quality_count"] == 0


def test_qa_summarize_news_aborts_after_consecutive_dify_rate_limits(monkeypatch):
    sleep_calls = []
    called_titles = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            called_titles.append(title)
            raise DifyRateLimitError("Requests have exceeded the throughput limit")

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)
    monkeypatch.setattr(run_qa_bot.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "dify_rate_limit_abort_threshold": 2,
    }

    news_items = [
        NewsItem(
            "第一条",
            "https://example.com/1",
            "2026-03-22",
            "源A",
            summary="摘要1",
            published_at=datetime(2026, 3, 22, 8, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "第二条",
            "https://example.com/2",
            "2026-03-22",
            "源A",
            summary="摘要2",
            published_at=datetime(2026, 3, 22, 7, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "第三条",
            "https://example.com/3",
            "2026-03-22",
            "源A",
            summary="摘要3",
            published_at=datetime(2026, 3, 22, 6, 0, tzinfo=timezone.utc),
        ),
    ]

    summarized = bot._summarize_news(news_items)

    assert summarized == []
    assert called_titles == ["第一条", "第二条", "第一条", "第二条"]
    assert sleep_calls == [6, 6, 18, 6, 6]


def test_qa_summarize_news_retries_remaining_items_after_rate_limit_abort(monkeypatch):
    sleep_calls = []
    called_titles = []
    attempts_by_title = {}

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            called_titles.append(title)
            attempts_by_title[title] = attempts_by_title.get(title, 0) + 1
            if attempts_by_title[title] == 1 and title in {"第一条", "第二条"}:
                raise DifyRateLimitError("Requests have exceeded the throughput limit")
            return json.dumps(
                {
                    "title": title,
                    "summary": f"{title} 的有效摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试实践",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)
    monkeypatch.setattr(run_qa_bot.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "dify_rate_limit_abort_threshold": 2,
        "max_per_source_final": 20,
        "max_per_category_final": 20,
    }

    news_items = [
        NewsItem("第一条", "https://example.com/1", "2026-03-22", "源A", summary="摘要1"),
        NewsItem("第二条", "https://example.com/2", "2026-03-22", "源A", summary="摘要2"),
        NewsItem("第三条", "https://example.com/3", "2026-03-22", "源A", summary="摘要3"),
    ]

    summarized = bot._summarize_news(news_items)

    assert len(summarized) == 3
    assert {item.title for item in summarized} == {"第一条", "第二条", "第三条"}
    assert called_titles.count("第一条") == 2
    assert called_titles.count("第二条") == 2
    assert called_titles.count("第三条") == 1
    assert sleep_calls == [6, 6, 18]


def test_qa_rate_limited_items_are_exported_for_review(monkeypatch, tmp_path):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            raise DifyRateLimitError("Requests have exceeded the throughput limit")

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)
    monkeypatch.setattr(run_qa_bot.time, "sleep", lambda _seconds: None)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.review_export_dir = str(tmp_path / "review_exports")
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "dify_rate_limit_abort_threshold": 1,
        "dify_rate_limit_retry_rounds": 1,
    }

    summarized = bot._summarize_news(
        [
            NewsItem("第一条", "https://example.com/1", "2026-03-22", "源A", summary="摘要1"),
            NewsItem("第二条", "https://example.com/2", "2026-03-22", "源A", summary="摘要2"),
        ]
    )

    export_path = bot._export_review_report(date_label="2026-03-22")

    assert summarized == []
    assert len(bot.latest_review_report["rate_limit_skipped_items"]) == 2
    with open(export_path, "r", encoding="utf-8") as file:
        content = file.read()
    assert "## 被 Dify 限流跳过" in content
    assert "第一条" in content
    assert "第二条" in content


def test_qa_rate_limited_low_confidence_items_still_exported_for_review(monkeypatch, tmp_path):
    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            raise DifyRateLimitError("Requests have exceeded the throughput limit")

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)
    monkeypatch.setattr(run_qa_bot.time, "sleep", lambda _seconds: None)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.review_export_dir = str(tmp_path / "review_exports")
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "dify_rate_limit_abort_threshold": 1,
        "dify_rate_limit_retry_rounds": 0,
    }

    summarized = bot._summarize_news(
        [
            NewsItem("泛测试闲聊", "https://example.com/chat", "2026-03-22", "源A", summary="测试"),
        ]
    )

    export_path = bot._export_review_report(date_label="2026-03-22")

    assert summarized == []
    assert len(bot.latest_review_report["rate_limit_skipped_items"]) == 1
    with open(export_path, "r", encoding="utf-8") as file:
        content = file.read()
    assert "## 被 Dify 限流跳过" in content
    assert "泛测试闲聊" in content


def test_qa_summarize_news_prioritizes_high_value_candidates_before_dify(monkeypatch):
    called_titles = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            called_titles.append(title)
            return json.dumps(
                {
                    "title": title,
                    "summary": "有效摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试实践",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {"min_quality_score": 6, "max_count": 20}

    news_items = [
        NewsItem(
            "Nightly",
            "https://example.com/nightly",
            "2026-03-22",
            "Selenium 官方版本发布",
            summary="Nightly build",
            source_priority=1,
            scenario_tags=["UI自动化"],
            published_at=datetime(2026, 3, 22, 8, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "v7.34.3",
            "https://example.com/cucumber",
            "2026-03-21",
            "Cucumber JVM 官方版本发布",
            summary="Stable release",
            source_priority=2,
            scenario_tags=["测试框架"],
            published_at=datetime(2026, 3, 21, 8, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "The Way of TDD",
            "https://example.com/tdd",
            "2026-03-20",
            "Google Testing Blog",
            summary="Testing methodology",
            source_priority=1,
            scenario_tags=["测试框架", "质量效能"],
            published_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
        ),
    ]

    bot._summarize_news(news_items)

    assert called_titles == ["The Way of TDD", "v7.34.3", "Nightly"]


def test_qa_summarize_news_limits_dify_candidates_after_prioritization(monkeypatch):
    called_titles = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            called_titles.append(title)
            return json.dumps(
                {
                    "title": title,
                    "summary": "有效摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试实践",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {"min_quality_score": 6, "max_count": 20, "dify_candidate_limit": 2}

    news_items = [
        NewsItem(
            "Nightly",
            "https://example.com/nightly",
            "2026-03-22",
            "Selenium 官方版本发布",
            summary="Nightly build",
            source_priority=1,
            scenario_tags=["UI自动化"],
            published_at=datetime(2026, 3, 22, 8, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "v7.34.3",
            "https://example.com/cucumber",
            "2026-03-21",
            "Cucumber JVM 官方版本发布",
            summary="Stable release",
            source_priority=2,
            scenario_tags=["测试框架"],
            published_at=datetime(2026, 3, 21, 8, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "The Way of TDD",
            "https://example.com/tdd",
            "2026-03-20",
            "Google Testing Blog",
            summary="Testing methodology",
            source_priority=1,
            scenario_tags=["测试框架", "质量效能"],
            published_at=datetime(2026, 3, 20, 8, 0, tzinfo=timezone.utc),
        ),
    ]

    bot._summarize_news(news_items)

    assert called_titles == ["The Way of TDD", "v7.34.3"]


def test_qa_summarize_news_aggressively_reserves_dify_slots_for_exploration_sources(monkeypatch):
    called_titles = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            called_titles.append(title)
            return json.dumps(
                {
                    "title": title,
                    "summary": "有效摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试实践",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "dify_candidate_limit": 4,
        "dify_exploration_slots": 2,
        "dify_candidate_max_per_source": 1,
    }
    bot.fetcher.sources = [
        {"name": "Google Testing Blog", "priority": 1},
        {"name": "Cypress 官方博客", "priority": 1},
        {"name": "Robot Framework 官方版本发布", "priority": 2},
        {"name": "LaunchDarkly 官方博客", "priority": 3, "dify_exploration": True},
        {"name": "Ministry of Testing - Test Automation", "priority": 4, "dify_exploration": True},
    ]

    news_items = [
        NewsItem(
            "The Way of TDD",
            "https://example.com/tdd",
            "2026-03-23",
            "Google Testing Blog",
            summary="Testing methodology",
            source_priority=1,
            scenario_tags=["测试策略", "质量效能"],
            published_at=datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "Set Safe Defaults for Flags",
            "https://example.com/flags",
            "2026-03-23",
            "Google Testing Blog",
            summary="Feature flag defaults",
            source_priority=1,
            scenario_tags=["测试策略"],
            published_at=datetime(2026, 3, 23, 8, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "cy.prompt can now wait for network requests",
            "https://example.com/cypress",
            "2026-03-23",
            "Cypress 官方博客",
            summary="UI automation improvement",
            source_priority=1,
            scenario_tags=["UI自动化"],
            published_at=datetime(2026, 3, 23, 7, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "Robot Framework 7.4.2",
            "https://example.com/robot",
            "2026-03-23",
            "Robot Framework 官方版本发布",
            summary="Stable release",
            source_priority=2,
            scenario_tags=["测试框架"],
            published_at=datetime(2026, 3, 23, 6, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "Defining regression thresholds for guarded rollouts",
            "https://example.com/launchdarkly",
            "2026-03-23",
            "LaunchDarkly 官方博客",
            summary="Feature flag regression control",
            source_priority=3,
            scenario_tags=["测试策略", "质量效能"],
            published_at=datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "Writing tests with Claude Code - part 1 - initial results",
            "https://example.com/mot",
            "2026-03-23",
            "Ministry of Testing - Test Automation",
            summary="AI-assisted testing workflow",
            source_priority=4,
            scenario_tags=["AI赋能测试", "UI自动化"],
            published_at=datetime(2026, 3, 23, 11, 0, tzinfo=timezone.utc),
        ),
    ]

    bot._summarize_news(news_items)

    assert called_titles == [
        "Defining regression thresholds for guarded rollouts",
        "Writing tests with Claude Code - part 1 - initial results",
        "The Way of TDD",
        "cy.prompt can now wait for network requests",
    ]


def test_qa_summarize_news_backfills_general_candidates_when_exploration_slots_not_enough(monkeypatch):
    called_titles = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            called_titles.append(title)
            return json.dumps(
                {
                    "title": title,
                    "summary": "有效摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试实践",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "dify_candidate_limit": 4,
        "dify_exploration_slots": 3,
        "dify_candidate_max_per_source": 1,
    }
    bot.fetcher.sources = [
        {"name": "Google Testing Blog", "priority": 1},
        {"name": "Cypress 官方博客", "priority": 1},
        {"name": "Robot Framework 官方版本发布", "priority": 2},
        {"name": "LaunchDarkly 官方博客", "priority": 3, "dify_exploration": True},
    ]

    news_items = [
        NewsItem(
            "The Way of TDD",
            "https://example.com/tdd",
            "2026-03-23",
            "Google Testing Blog",
            summary="Testing methodology",
            source_priority=1,
            scenario_tags=["测试策略", "质量效能"],
            published_at=datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "cy.prompt can now wait for network requests",
            "https://example.com/cypress",
            "2026-03-23",
            "Cypress 官方博客",
            summary="UI automation improvement",
            source_priority=1,
            scenario_tags=["UI自动化"],
            published_at=datetime(2026, 3, 23, 7, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "Robot Framework 7.4.2",
            "https://example.com/robot",
            "2026-03-23",
            "Robot Framework 官方版本发布",
            summary="Stable release",
            source_priority=2,
            scenario_tags=["测试框架"],
            published_at=datetime(2026, 3, 23, 6, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "Defining regression thresholds for guarded rollouts",
            "https://example.com/launchdarkly",
            "2026-03-23",
            "LaunchDarkly 官方博客",
            summary="Feature flag regression control",
            source_priority=3,
            scenario_tags=["测试策略", "质量效能"],
            published_at=datetime(2026, 3, 23, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    bot._summarize_news(news_items)

    assert called_titles == [
        "Defining regression thresholds for guarded rollouts",
        "The Way of TDD",
        "cy.prompt can now wait for network requests",
        "Robot Framework 7.4.2",
    ]


def test_qa_summarize_news_prefers_ai_practice_candidates_for_dify(monkeypatch):
    called_titles = []

    class FakeDifyClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def summarize_content(self, title, content, prompt_template=None):
            called_titles.append(title)
            return json.dumps(
                {
                    "title": title,
                    "summary": "有效摘要",
                    "highlights": "",
                    "score": 8,
                    "category": "测试实践",
                    "score_breakdown": {
                        "timeliness": 8,
                        "source_authority": 8,
                        "testing_relevance": 8,
                        "practical_value": 8,
                    },
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr(run_qa_bot, "DifyClient", FakeDifyClient)

    bot = run_qa_bot.QABot()
    bot.dify_base = "http://fake"
    bot.dify_key = "fake-key"
    bot.dify_user = "tester"
    bot.fetcher.filter_config = {
        "min_quality_score": 6,
        "max_count": 20,
        "dify_candidate_limit": 2,
        "dify_candidate_max_per_source": 1,
        "preferred_scenario_tags": ["AI生成脚本", "AI回归优化", "AI测试数据"],
    }
    bot.fetcher.sources = [
        {"name": "Google Testing Blog", "priority": 1},
        {"name": "Cypress 官方博客", "priority": 1},
        {"name": "DevAssure 官方博客", "priority": 3},
    ]

    news_items = [
        NewsItem(
            "The Way of TDD",
            "https://example.com/tdd",
            "2026-03-23",
            "Google Testing Blog",
            summary="Testing methodology",
            source_priority=1,
            scenario_tags=["测试策略", "质量效能"],
            published_at=datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "cy.prompt can now wait for network requests",
            "https://example.com/cypress",
            "2026-03-23",
            "Cypress 官方博客",
            summary="UI automation improvement",
            source_priority=1,
            scenario_tags=["UI自动化"],
            published_at=datetime(2026, 3, 23, 8, 0, tzinfo=timezone.utc),
        ),
        NewsItem(
            "AI test impact analysis for regression flows",
            "https://example.com/devassure",
            "2026-03-23",
            "DevAssure 官方博客",
            summary="AI regression optimization",
            source_priority=3,
            scenario_tags=["AI回归优化", "AI赋能测试"],
            published_at=datetime(2026, 3, 23, 7, 0, tzinfo=timezone.utc),
        ),
    ]

    bot._summarize_news(news_items)

    assert called_titles == [
        "AI test impact analysis for regression flows",
        "The Way of TDD",
    ]


def test_qa_select_dify_candidates_allows_multiple_from_same_source_when_source_limit_disabled():
    bot = run_qa_bot.QABot()
    bot.fetcher.filter_config = {
        "dify_candidate_limit": 3,
        "dify_candidate_max_per_source": 0,
        "preferred_scenario_tags": ["AI生成脚本", "AI回归优化", "AI测试数据"],
    }

    prioritized_items = [
        NewsItem(
            "Google A",
            "https://example.com/google-a",
            "2026-03-23",
            "Google Testing Blog",
            summary="A",
            source_priority=1,
            scenario_tags=["测试策略"],
        ),
        NewsItem(
            "Google B",
            "https://example.com/google-b",
            "2026-03-23",
            "Google Testing Blog",
            summary="B",
            source_priority=1,
            scenario_tags=["质量效能"],
        ),
        NewsItem(
            "Cypress C",
            "https://example.com/cypress-c",
            "2026-03-23",
            "Cypress 官方博客",
            summary="C",
            source_priority=1,
            scenario_tags=["UI自动化"],
        ),
    ]

    selected = bot._select_dify_candidates_for_summarization(prioritized_items, 3)

    assert [item.title for item in selected] == ["Google A", "Google B", "Cypress C"]


def test_qa_fetch_juejin_filters_expired_articles():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24,
        "keywords": ["测试"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        post_payload={
            "data": [
                {
                    "result_model": {
                        "article_info": {
                            "title": "最新测试实践",
                            "article_id": "fresh",
                            "brief_content": "测试平台建设经验",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
                        }
                    }
                },
                {
                    "result_model": {
                        "article_info": {
                            "title": "陈旧测试文章",
                            "article_id": "stale",
                            "brief_content": "测试平台建设经验",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(days=5)).timestamp()),
                        }
                    }
                },
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_juejin(session, {"name": "掘金-测试", "keyword": "测试平台"})
    )

    assert [item.link for item in items] == ["https://juejin.cn/post/fresh"]
    assert session.last_post_json["sort_type"] == 2


def test_qa_fetch_juejin_assigns_scenario_tags():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24,
        "keywords": ["测试"],
        "exclude_keywords": [],
        "scenario_keywords": {
            "接口自动化": ["接口自动化", "API测试"],
            "AI赋能测试": ["AI测试", "智能测试"],
        },
    }
    fetcher.sent_history = []
    session = _FakeSession(
        post_payload={
            "data": [
                {
                    "result_model": {
                        "article_info": {
                            "title": "接口自动化回归实践",
                            "article_id": "fresh-tagged",
                            "brief_content": "结合 AI测试 提升接口回归效率",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
                        }
                    }
                }
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_juejin(session, {"name": "掘金-测试", "keyword": "接口自动化"})
    )

    assert len(items) == 1
    assert items[0].scenario_tags == ["接口自动化", "AI赋能测试"]


def test_qa_fetch_juejin_supports_llm_keyword_filters_for_community_sources():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 14,
        "keywords": ["测试", "LLM", "Claude Code", "MCP", "Function Calling"],
        "exclude_keywords": [],
        "scenario_keywords": {
            "AI赋能测试": ["MCP", "Function Calling", ["MCP", "Skill"]],
            "LLM应用评测": ["LLM evaluation", ["RAG", "evaluation"]],
        },
    }
    fetcher.sent_history = []
    session = _FakeSession(
        post_payload={
            "data": [
                {
                    "result_model": {
                        "article_info": {
                            "title": "Claude Code + MCP Skill 在测试 Agent 中的落地",
                            "article_id": "llm-practice",
                            "brief_content": "结合 Function Calling、RAG evaluation 与测试工作流做实战复盘",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(hours=4)).timestamp()),
                        }
                    }
                },
                {
                    "result_model": {
                        "article_info": {
                            "title": "Claude Code 提示词大全",
                            "article_id": "noise-prompt",
                            "brief_content": "分享通用提示词模板，不涉及测试场景",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(hours=3)).timestamp()),
                        }
                    }
                },
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_juejin(
            session,
            {
                "name": "掘金 - Claude Code 与测试Agent",
                "keyword": "Claude Code 测试 Agent",
                "priority": 3,
                "time_window_hours": 24 * 14,
                "require_keywords": ["Claude Code", "MCP", "Function Calling", "LLM"],
                "exclude_keywords": ["提示词大全", "模板", "招聘"],
            },
        )
    )

    assert [item.title for item in items] == ["Claude Code + MCP Skill 在测试 Agent 中的落地"]
    assert "AI赋能测试" in items[0].scenario_tags
    assert "LLM应用评测" in items[0].scenario_tags


def test_qa_fetch_juejin_supports_combined_require_keywords_for_llm_sources():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 14,
        "keywords": ["测试", "Claude Code", "MCP"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        post_payload={
            "data": [
                {
                    "result_model": {
                        "article_info": {
                            "title": "Claude Code 完全指南",
                            "article_id": "generic-guide",
                            "brief_content": "介绍安装、使用方式和效率技巧，聚焦日常编程提效",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
                        }
                    }
                },
                {
                    "result_model": {
                        "article_info": {
                            "title": "MCP 测试 Agent 实践",
                            "article_id": "mcp-test-agent",
                            "brief_content": "结合 Claude Code 做自动化测试编排与回归验证",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
                        }
                    }
                },
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_juejin(
            session,
            {
                "name": "掘金 - 测试 Agent 与 MCP 实践",
                "keyword": "测试 Agent MCP 实践",
                "priority": 3,
                "time_window_hours": 24 * 14,
                "require_keywords": [["Claude Code", "测试"], ["MCP", "测试"], ["自动化测试", "Agent"]],
                "exclude_keywords": [],
            },
        )
    )

    assert [item.title for item in items] == ["MCP 测试 Agent 实践"]


def test_qa_fetch_juejin_relaxed_playwright_community_source_allows_automation_practice():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["测试", "自动化", "Playwright"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        post_payload={
            "data": [
                {
                    "result_model": {
                        "article_info": {
                            "title": "使用 Playwright 搭建自动化测试工程",
                            "article_id": "playwright-auto-project",
                            "brief_content": "围绕前端自动化回归、工程搭建和调试流程展开实践",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(days=12)).timestamp()),
                        }
                    }
                }
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_juejin(
            session,
            {
                "name": "掘金 - Playwright MCP 与 Skill",
                "keyword": "Playwright MCP Skill 测试",
                "priority": 3,
                "time_window_hours": 24 * 30,
                "require_keywords": [["Playwright", "自动化"], ["Playwright", "测试"], ["MCP", "测试"]],
                "exclude_keywords": ["提示词大全", "招聘"],
            },
        )
    )

    assert [item.title for item in items] == ["使用 Playwright 搭建自动化测试工程"]


def test_qa_fetch_testerhome_filters_expired_topics():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24,
        "keywords": ["测试"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload={
            "topics": [
                {
                    "title": "测试平台实践",
                    "id": 1,
                    "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                },
                {
                    "title": "旧的测试话题",
                    "id": 2,
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
                },
            ]
        }
    )

    items = asyncio.run(fetcher._fetch_testerhome(session, {"name": "TesterHome"}))

    assert [item.link for item in items] == ["https://testerhome.com/topics/1"]


def test_qa_fetch_testerhome_uses_body_for_relevance():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24,
        "keywords": ["Playwright"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload={
            "topics": [
                {
                    "title": "自动化框架升级记录",
                    "id": 10,
                    "body": "我们最近把 Playwright 接入回归流水线，并补齐 UI 自动化基建。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                }
            ]
        }
    )

    items = asyncio.run(fetcher._fetch_testerhome(session, {"name": "TesterHome"}))

    assert len(items) == 1
    assert items[0].link == "https://testerhome.com/topics/10"


def test_qa_fetch_testerhome_supports_domestic_ai_testing_node_filters():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24,
        "keywords": ["测试", "AI", "Playwright"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload={
            "topics": [
                {
                    "title": "AI 赋能测试实践 03：深度拆解 Agent Browser 与 Playwright 落地",
                    "id": 21,
                    "body": "围绕 AI测试、浏览器自动化测试和 Agent 工作流展开实践复盘。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
                },
                {
                    "title": "大家都用哪些 ai 测试工具",
                    "id": 22,
                    "body": "想讨论一下选型思路。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
                },
                {
                    "title": "随笔：AI 对测试行业的冲击",
                    "id": 23,
                    "body": "一些泛化感想。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
                },
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_testerhome(
            session,
            {
                "name": "TesterHome AI测试",
                "url": "https://testerhome.com/api/v3/topics.json?limit=20&node_id=134",
                "require_keywords": ["AI测试", "Playwright", "Agent", "MCP", "自动化测试"],
                "exclude_keywords": ["大家都用哪些", "都用哪些", "随笔", "冲击"],
            },
        )
    )

    assert [item.title for item in items] == [
        "AI 赋能测试实践 03：深度拆解 Agent Browser 与 Playwright 落地"
    ]
    assert items[0].link == "https://testerhome.com/topics/21"


def test_qa_fetch_testerhome_supports_domestic_automation_tool_node_filters():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["自动化", "测试", "Playwright", "MCP"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload={
            "topics": [
                {
                    "title": "部分自动化测试可被 AI 取代了-playwright mcp 体验",
                    "id": 31,
                    "body": "围绕 Playwright MCP、自然语言驱动 UI 自动化和回归验证展开实践复盘。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                },
                {
                    "title": "小调查：AI 在 UI 自动化测试中应用",
                    "id": 32,
                    "body": "想了解大家的使用情况和选型思路。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
                },
                {
                    "title": "求助！！！基于 Midscene 搭建了一个 UI 自动化平台",
                    "id": 33,
                    "body": "容器云部署后页面一直卡住，求助排查。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                },
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_testerhome(
            session,
            {
                "name": "TesterHome 自动化工具",
                "url": "https://testerhome.com/api/v3/topics.json?limit=20&node_id=2",
                "require_keywords": ["自动化", "UI 自动化", "Playwright", "MCP", "Selenium", "Maestro"],
                "exclude_keywords": ["小调查", "使用情况", "求助", "迷茫"],
            },
        )
    )

    assert [item.title for item in items] == [
        "部分自动化测试可被 AI 取代了-playwright mcp 体验"
    ]
    assert items[0].link == "https://testerhome.com/topics/31"


def test_qa_fetch_testerhome_supports_source_specific_exclude_title_patterns():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["测试", "JMeter", "测开"],
        "exclude_keywords": [],
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload={
            "topics": [
                {
                    "title": "40 岁测试失业了，还有必要继续找测试的工作吗",
                    "id": 41,
                    "body": "职业焦虑讨论，但不属于测试实践。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                },
                {
                    "title": "零基础测开学习 23——JMeter 定时器 + 分布式 + 测试报告 + 第三方插件",
                    "id": 42,
                    "body": "围绕压测脚本、执行编排和测试报告生成展开实操记录。",
                    "created_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                },
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_testerhome(
            session,
            {
                "name": "TesterHome 最新话题",
                "exclude_title_patterns": ["失业", r"\d+\s*岁"],
            },
        )
    )

    assert [item.title for item in items] == [
        "零基础测开学习 23——JMeter 定时器 + 分布式 + 测试报告 + 第三方插件"
    ]


def test_qa_fetch_juejin_uses_shared_sent_history_keys(tmp_path):
    fetcher = QANewsFetcher()
    fetcher.history_file = str(tmp_path / "qa_sent_articles.json")
    fetcher.sent_history = []
    fetcher.filter_config = {
        "time_window_hours": 24,
        "keywords": ["测试"],
        "exclude_keywords": [],
    }
    fetcher.save_to_history(
        [NewsItem("接口测试实战", "https://juejin.cn/post/history-1", "2026-03-21", "掘金")]
    )
    session = _FakeSession(
        post_payload={
            "data": [
                {
                    "result_model": {
                        "article_info": {
                            "title": "接口测试实战",
                            "article_id": "history-1",
                            "brief_content": "测试平台建设经验",
                            "ctime": int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()),
                        }
                    }
                }
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_juejin(session, {"name": "掘金-测试", "keyword": "接口测试"})
    )

    assert items == []


def test_qa_bot_apply_runtime_storage_tag_isolates_state_files(tmp_path):
    bot = run_qa_bot.QABot()
    bot.fetcher.history_file = str(tmp_path / "qa_sent_articles.json")
    bot.fetcher.sent_history = []
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")
    bot.publish_state_store = run_qa_bot.PublishStateStore(str(tmp_path / "qa_publish_records.json"))
    bot.review_export_dir = str(tmp_path / "review_exports")

    tagged_history_file = tmp_path / "qa_sent_articles__prompt_verify.json"
    with open(tagged_history_file, "w", encoding="utf-8") as file:
        json.dump(["url:https://example.com/already-sent"], file, ensure_ascii=False, indent=2)

    bot._apply_runtime_storage_tag("prompt-verify")

    assert bot.fetcher.history_file.endswith("qa_sent_articles__prompt_verify.json")
    assert bot.fetcher._is_in_sent_history("https://example.com/already-sent") is True
    assert bot.recent_topic_store.file_path.endswith("qa_recent_topics__prompt_verify.json")
    assert bot.source_quality_store.file_path.endswith("qa_source_quality__prompt_verify.json")
    assert bot.publish_state_store.file_path.endswith("qa_publish_records__prompt_verify.json")
    assert bot.review_export_dir.endswith("review_exports/prompt_verify")


def test_qa_run_reassigns_scenario_tags_after_content_enrichment(monkeypatch):
    bot = run_qa_bot.QABot()
    bot.fetcher.filter_config = {
        "scenario_keywords": {
            "接口自动化": ["REST Assured", "acceptance test"],
            "AI赋能测试": ["Claude Code"],
        }
    }

    item = NewsItem(
        "Writing tests with Claude Code - part 1 - initial results",
        "https://example.com/on-test-automation",
        "2026-03-23",
        "On Test Automation",
        summary="仅从标题看不出接口自动化细节",
        scenario_tags=[],
    )

    async def fake_fetch_all_async():
        return [item]

    async def fake_enrich_items_with_full_content_async(news_items):
        news_items[0].content_text = "Claude Code generated REST Assured acceptance tests for a Spring Boot API."
        return news_items

    captured_tags = []

    def fake_summarize_news(news_items):
        captured_tags.append(list(news_items[0].scenario_tags))
        return []

    monkeypatch.setattr(bot.fetcher, "fetch_all_async", fake_fetch_all_async)
    monkeypatch.setattr(bot.fetcher, "enrich_items_with_full_content_async", fake_enrich_items_with_full_content_async)
    monkeypatch.setattr(bot, "_retry_pending_wecom_notifications", lambda: None)
    monkeypatch.setattr(bot, "_summarize_news", fake_summarize_news)

    asyncio.run(bot.run(date_label="2026-03-23"))

    assert captured_tags == [["接口自动化", "AI赋能测试"]]


def test_qa_fetch_source_assigns_scenario_tags_for_rss_items(monkeypatch):
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "scenario_keywords": {
            "UI自动化": ["Playwright", "E2E"],
            "质量效能": ["CI/CD", "流水线"],
        }
    }

    async def fake_parent_fetch(_self, _session, source):
        return [
            NewsItem(
                "Playwright 版本更新",
                "https://example.com/playwright-release",
                "2026-03-21",
                source["name"],
                summary="新增 E2E 调试能力，并优化 CI/CD 流水线集成",
            )
        ]

    monkeypatch.setattr(AINewsFetcher, "_fetch_source", fake_parent_fetch)

    items = asyncio.run(
        fetcher._fetch_source(_FakeSession(), {"name": "Playwright 官方版本发布", "type": "rss"})
    )

    assert len(items) == 1
    assert items[0].scenario_tags == ["UI自动化", "质量效能"]


def test_assign_scenario_tags_uses_source_name_context():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "scenario_keywords": {
            "测试框架": ["Cucumber", "Robot Framework"],
            "接口自动化": ["Karate", "Newman"],
        }
    }

    items = fetcher._assign_scenario_tags(
        [
            NewsItem(
                "v7.34.3",
                "https://example.com/cucumber-jvm-v7-34-3",
                "2026-03-21",
                "Cucumber JVM 官方版本发布",
                summary="Fixed dependency updates.",
            ),
            NewsItem(
                "v6.2.2",
                "https://example.com/newman-v6-2-2",
                "2026-03-21",
                "Newman 官方版本发布",
                summary="Release v6.2.2",
            ),
        ]
    )

    assert items[0].scenario_tags == ["测试框架"]
    assert items[1].scenario_tags == ["接口自动化"]


def test_qa_extract_scenario_tags_covers_claude_code_api_acceptance_testing():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "Writing tests with Claude Code for Spring Boot API using REST Assured acceptance tests"
    )

    assert "接口自动化" in tags
    assert "AI赋能测试" in tags


def test_qa_extract_scenario_tags_does_not_mark_ai_for_generic_defect_analysis_text():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "缺陷分析缺失，需分析全链路测试数据，可通过 AI 优化测试策略，如预测高风险用例。"
    )

    assert "AI赋能测试" not in tags


def test_qa_extract_scenario_tags_marks_ai_agent_practice_as_ai_testing():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "Rebuilding an AI Agent the Right Way for test creation workflows"
    )

    assert "AI赋能测试" in tags


def test_qa_extract_scenario_tags_marks_ai_case_and_script_generation():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "AI test case generation and AI test script generation for Playwright UI flows"
    )

    assert "AI赋能测试" in tags
    assert "AI生成用例" in tags
    assert "AI生成脚本" in tags
    assert "UI自动化" in tags


def test_qa_extract_scenario_tags_marks_ai_diagnosis_regression_and_evaluation():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "LLM evaluation for AI bug triage, root cause analysis, and AI test impact analysis in regression testing"
    )

    assert "AI赋能测试" in tags
    assert "AI辅助缺陷诊断" in tags
    assert "AI回归优化" in tags
    assert "LLM应用评测" in tags


def test_qa_extract_scenario_tags_marks_ai_test_data_generation():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "AI synthetic test data generation with mock server for API testing regression flows"
    )

    assert "AI赋能测试" in tags
    assert "AI测试数据" in tags
    assert "测试数据" in tags
    assert "接口自动化" in tags


def test_qa_extract_scenario_tags_marks_mcp_skill_and_function_calling_as_ai_testing():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "Using MCP skill and function calling for RAG evaluation in LLM test agent workflows"
    )

    assert "AI赋能测试" in tags
    assert "LLM应用评测" in tags


def test_qa_extract_scenario_tags_does_not_mark_test_data_for_generic_quality_text():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "需分析全链路测试数据，建立持续反馈闭环，并识别高风险模块。"
    )

    assert "测试数据" not in tags


def test_qa_extract_scenario_tags_marks_test_data_for_mock_and_data_factory():
    fetcher = QANewsFetcher()

    tags = fetcher._extract_scenario_tags(
        "通过 Mock 服务、测试数据工厂和自动造数优化接口回归准备效率。"
    )

    assert "测试数据" in tags


def test_fetch_mot_news_html_source_extracts_cards_and_filters_noise():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["AI测试", "Cypress", "Claude", "E2E"],
        "exclude_keywords": [],
        "scenario_keywords": {
            "AI赋能测试": ["AI Testing", "Claude Code"],
            "UI自动化": ["Cypress", "E2E"],
        },
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload="""
        <div class='card shadow summary-card'>
          <div class='card-body position-relative'>
            <div class='details'>
              <div class='info'>
                <div class='title'>
                  <a target="_blank" class="stretched-link text-black" href="https://example.com/ai-testing-production-logs">AI Testing: How to Ensure Quality in Non-Deterministic Systems with Adam Sandman</a>
                </div>
                <div class='summary'>
                  Source: Joe Colantonio
                </div>
              </div>
            </div>
          </div>
          <div class='card-footer d-flex flex-column'>
            <div class='info d-flex align-items-center justify-content-between'>
              <a target="_top" class="card-link text-black" href="/software-testing-news/list?feed=test-automation">Test Automation</a>
              <div class='published fs-6'>
                10 Mar
              </div>
            </div>
          </div>
        </div>
        <div class='card shadow summary-card'>
          <div class='card-body position-relative'>
            <div class='details'>
              <div class='info'>
                <div class='title'>
                  <a target="_blank" class="stretched-link text-black" href="https://example.com/cypress-public-env">Public Environment Variables For Your Tests Using cypress-expose Plugin</a>
                </div>
                <div class='summary'>
                  Source: Gleb Bahmutov
                </div>
              </div>
            </div>
          </div>
          <div class='card-footer d-flex flex-column'>
            <div class='info d-flex align-items-center justify-content-between'>
              <a target="_top" class="card-link text-black" href="/software-testing-news/list?feed=test-automation">Test Automation</a>
              <div class='published fs-6'>
                12 Mar
              </div>
            </div>
          </div>
        </div>
        <div class='card shadow summary-card'>
          <div class='card-body position-relative'>
            <div class='details'>
              <div class='info'>
                <div class='title'>
                  <a target="_blank" class="stretched-link text-black" href="https://example.com/claude-code-tests">Writing tests with Claude Code - part 1 - initial results</a>
                </div>
                <div class='summary'>
                  Source: Bas Dijkstra
                </div>
              </div>
            </div>
          </div>
          <div class='card-footer d-flex flex-column'>
            <div class='info d-flex align-items-center justify-content-between'>
              <a target="_top" class="card-link text-black" href="/software-testing-news/list?feed=test-automation">Test Automation</a>
              <div class='published fs-6'>
                09 Mar
              </div>
            </div>
          </div>
        </div>
        <div class='card shadow summary-card'>
          <div class='card-body position-relative'>
            <div class='details'>
              <div class='info'>
                <div class='title'>
                  <a target="_blank" class="stretched-link text-black" href="https://example.com/polkadot">Exploring Off-Chain Computation on Polkadot: Possibilities with Substrate Extensions</a>
                </div>
                <div class='summary'>
                  Source: Arogbonlo Isaac
                </div>
              </div>
            </div>
          </div>
          <div class='card-footer d-flex flex-column'>
            <div class='info d-flex align-items-center justify-content-between'>
              <a target="_top" class="card-link text-black" href="/software-testing-news/list?feed=test-automation">Test Automation</a>
              <div class='published fs-6'>
                09 Mar
              </div>
            </div>
          </div>
        </div>
        <div class='card shadow summary-card advert'>
          <div class='card-body'>
            <a class="stretched-link" target="_blank" href="https://example.com/ad">Meet Maestro Studio, free desktop app for UI tests</a>
          </div>
        </div>
        """
    )

    items = asyncio.run(
        fetcher._fetch_source(
            session,
            {
                "name": "Ministry of Testing - Test Automation",
                "url": "https://www.ministryoftesting.com/software-testing-news/list?feed=test-automation",
                "type": "mot_news_html",
                "require_keywords": ["AI Testing", "Cypress", "Claude Code", "E2E"],
                "exclude_keywords": ["Polkadot"],
            },
        )
    )

    assert [item.title for item in items] == [
        "AI Testing: How to Ensure Quality in Non-Deterministic Systems with Adam Sandman",
        "Public Environment Variables For Your Tests Using cypress-expose Plugin",
        "Writing tests with Claude Code - part 1 - initial results",
    ]
    assert items[0].published_at is not None
    assert "AI赋能测试" in items[0].scenario_tags
    assert "UI自动化" in items[1].scenario_tags


def test_fetch_testmu_blog_html_extracts_cards_and_filters_noise():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["AI", "automation", "testing", "Selenium", "Playwright"],
        "exclude_keywords": [],
        "scenario_keywords": {
            "AI赋能测试": ["AI", "prompting"],
            "UI自动化": ["Selenium", "Playwright", "automation"],
        },
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload="""
        <div class="block">
          <div class="flex items-center flex-wrap mb-8 gap-8">
            <a href="https://www.testmuai.com/blog/category/ai/" class="text-[#4D4D4D] uppercase text-[14px] font-normal ">AI</a>
            <span class="w-5 h-5 bg-[#121212] flex-shrink-0"></span>
            <a href="https://www.testmuai.com/blog/category/testing/" class="text-[#4D4D4D] uppercase text-[14px] font-normal ">Testing</a>
          </div>
          <a href="https://www.testmuai.com/blog/15-prompting-techniques/" class="text-size-18 text-[#121212] font-medium leading-height-22 hover:underline block">15 Prompting Techniques Every Tester Should Know [2026]</a>
          <p class="text-size-16 text-[#4D4D4D] font-normal mt-4">Learn 15 prompting techniques for testers, from direct instruction to prompt chaining.</p>
          <div class="mt-12 flex items-center gap-10 flex-wrap ">
            <p class="text-[#4D4D4D] 2xl:text-size-14 text-size-12 font-normal">Mar 17, 2026</p>
          </div>
        </div>
        <div class="desktop:mt-20 bg-white p-24 smtablet:p-16">
          <div class="flex items-center flex-wrap mb-8 gap-8">
            <a href="https://www.testmuai.com/blog/category/automation/" class="text-[#4D4D4D] uppercase text-[14px] font-normal ">Automation</a>
            <span class="w-5 h-5 bg-[#121212] flex-shrink-0"></span>
            <a href="https://www.testmuai.com/blog/category/tutorial/" class="text-[#4D4D4D] uppercase text-[14px] font-normal ">Tutorial</a>
          </div>
          <a href="https://www.testmuai.com/blog/expected-conditions-in-selenium-examples/" class="text-size-18 text-[#121212] font-medium leading-height-22 hover:underline block">ExpectedConditions in Selenium: Python &amp; Java Examples [2026]</a>
          <p class="text-size-16 text-[#4D4D4D] font-normal mt-4">ExpectedConditions let you wait for elements to be clickable, visible, or present.</p>
          <div class="mt-12 flex items-center gap-10 flex-wrap ">
            <p class="text-[#4D4D4D] 2xl:text-size-14 text-size-12 font-normal">Mar 17, 2026</p>
          </div>
        </div>
        <div class="desktop:mt-20 bg-white p-24 smtablet:p-16">
          <div class="flex items-center flex-wrap mb-8 gap-8">
            <a href="https://www.testmuai.com/blog/category/ai/" class="text-[#4D4D4D] uppercase text-[14px] font-normal ">AI</a>
          </div>
          <a href="https://www.testmuai.com/blog/spartans-summit-2026-recap/" class="text-size-18 text-[#121212] font-medium leading-height-22 hover:underline block">Spartans Summit 2026: A Quick Recap</a>
          <p class="text-size-16 text-[#4D4D4D] font-normal mt-4">Spartans Summit 2026 by TestMu AI covered AI agent evaluation and MCP security.</p>
          <div class="mt-12 flex items-center gap-10 flex-wrap ">
            <p class="text-[#4D4D4D] 2xl:text-size-14 text-size-12 font-normal">Mar 16, 2026</p>
          </div>
        </div>
        """
    )

    items = asyncio.run(
        fetcher._fetch_source(
            session,
            {
                "name": "TestMu AI 官方博客",
                "url": "https://www.testmuai.com/blog/",
                "type": "testmu_blog_html",
                "require_keywords": ["AI", "automation", "testing", "Selenium", "Playwright"],
                "exclude_keywords": ["recap", "summit", "community", "webinar"],
            },
        )
    )

    assert [item.title for item in items] == [
        "15 Prompting Techniques Every Tester Should Know [2026]",
        "ExpectedConditions in Selenium: Python & Java Examples [2026]",
    ]
    assert items[0].link == "https://www.testmuai.com/blog/15-prompting-techniques/"
    assert items[0].published_at is not None
    assert "AI赋能测试" in items[0].scenario_tags
    assert "UI自动化" in items[1].scenario_tags


def test_fetch_saucelabs_next_data_json_extracts_articles_and_filters_noise():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 30,
        "keywords": ["testing", "automation", "Playwright", "Selenium", "AI"],
        "exclude_keywords": [],
        "scenario_keywords": {
            "AI赋能测试": ["AI", "test authoring"],
            "UI自动化": ["Playwright", "Selenium", "automation"],
        },
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload={
            "pageProps": {
                "featured": {
                    "cards": [
                        {
                            "fields": {
                                "feedType": "Blog",
                                "title": "Comparing the Best AI Automation Testing Tools in 2026",
                                "excerpt": "Struggling with flaky tests and slow automation? Explore the best AI-powered testing tools of 2026.",
                                "slug": "comparing-the-best-ai-automation-testing-tools-in-2026",
                            },
                            "sys": {
                                "createdAt": "2026-03-11T09:00:00Z",
                                "updatedAt": "2026-03-12T09:00:00Z",
                            },
                        },
                        {
                            "fields": {
                                "feedType": "Blog",
                                "title": "Webinar: QA Leadership Summit 2026",
                                "excerpt": "Join our summit to hear leadership stories.",
                                "slug": "qa-leadership-summit-2026",
                            },
                            "sys": {
                                "createdAt": "2026-03-15T09:00:00Z",
                                "updatedAt": "2026-03-15T09:00:00Z",
                            },
                        },
                        {
                            "fields": {
                                "feedType": "Case Study",
                                "title": "Case Study: Mobile Quality Transformation",
                                "excerpt": "Customer story about team transformation.",
                                "slug": "mobile-quality-transformation",
                            },
                            "sys": {
                                "createdAt": "2026-03-14T09:00:00Z",
                                "updatedAt": "2026-03-14T09:00:00Z",
                            },
                        },
                    ]
                }
            }
        }
    )

    items = asyncio.run(
        fetcher._fetch_source(
            session,
            {
                "name": "Sauce Labs 官方博客",
                "url": "https://saucelabs.com/_next/data/build/resources/blog.json?type=blog",
                "type": "saucelabs_next_data_json",
                "require_keywords": ["AI", "automation", "testing", "Playwright", "Selenium"],
                "exclude_keywords": ["webinar", "summit", "case study"],
            },
        )
    )

    assert [item.title for item in items] == [
        "Comparing the Best AI Automation Testing Tools in 2026"
    ]
    assert items[0].link == "https://saucelabs.com/resources/blog/comparing-the-best-ai-automation-testing-tools-in-2026"
    assert items[0].published_at is not None
    assert "AI赋能测试" in items[0].scenario_tags


def test_fetch_zendesk_help_center_api_extracts_articles_and_filters_irrelevant_updates():
    fetcher = QANewsFetcher()
    fetcher.filter_config = {
        "time_window_hours": 24 * 90,
        "keywords": ["visual", "Playwright", "Selenium", "Ultrafast"],
        "exclude_keywords": [],
        "scenario_keywords": {
            "UI自动化": ["visual", "Selenium", "Playwright", "Applitools"],
        },
    }
    fetcher.sent_history = []
    session = _FakeSession(
        get_payload={
            "articles": [
                {
                    "title": "Testing of floating UI elements",
                    "html_url": "https://help.applitools.com/hc/en-us/articles/360006915292-Testing-of-floating-UI-elements",
                    "updated_at": "2026-03-18T20:29:34Z",
                    "label_names": [],
                    "body": "<p>This feature helps teams perform functional test scenarios and visual validation without extra coding.</p>",
                },
                {
                    "title": "Integrating Applitools Ultrafast Grid and Tricentis Tosca",
                    "html_url": "https://help.applitools.com/hc/en-us/articles/4424137058957-Integrating-Applitools-Ultrafast-Grid-and-Tricentis-Tosca",
                    "updated_at": "2026-03-18T20:29:34Z",
                    "label_names": ["UFG", "Tosca", "Applitools", "UltrafastGrid"],
                    "body": "<p>Use Ultrafast Grid to speed up visual testing for UI automation suites.</p>",
                },
                {
                    "title": "Applitools billing FAQ",
                    "html_url": "https://help.applitools.com/hc/en-us/articles/000000000000-Applitools-billing-FAQ",
                    "updated_at": "2026-03-18T20:29:34Z",
                    "label_names": ["billing"],
                    "body": "<p>Understand invoices, plan changes, and payment cycles.</p>",
                },
            ]
        }
    )

    items = asyncio.run(
        fetcher._fetch_source(
            session,
            {
                "name": "Applitools Help Center",
                "url": "https://help.applitools.com/api/v2/help_center/en-us/sections/360001567572/articles.json",
                "type": "zendesk_help_center_api",
                "require_keywords": ["visual", "Selenium", "Playwright", "Ultrafast"],
                "exclude_keywords": ["billing", "invoice", "payment"],
            },
        )
    )

    assert [item.title for item in items] == [
        "Testing of floating UI elements",
        "Integrating Applitools Ultrafast Grid and Tricentis Tosca",
    ]
    assert items[0].link == "https://help.applitools.com/hc/en-us/articles/360006915292-Testing-of-floating-UI-elements"
    assert items[0].published_at is not None
    assert "UI自动化" in items[0].scenario_tags


def test_qa_config_prioritizes_official_tool_sources():
    fetcher = QANewsFetcher()

    source_names = {source.get("name") for source in fetcher.sources}
    juejin_sources = [source for source in fetcher.sources if source.get("type") == "juejin_api"]
    official_release_sources = [
        source for source in fetcher.sources if str(source.get("url", "")).endswith("/releases.atom")
    ]
    source_map = {source.get("name"): source for source in fetcher.sources}

    assert {
        "TesterHome 社区精选",
        "TesterHome AI测试",
        "TesterHome 自动化工具",
        "Playwright 官方版本发布",
        "Selenium 官方版本发布",
        "Cypress 官方博客",
        "Google Testing Blog",
        "InfoQ Testing News",
        "pytest 官方版本发布",
        "k6 官方版本发布",
        "Robot Framework 官方版本发布",
        "Newman 官方版本发布",
        "Cucumber JVM 官方版本发布",
        "Locust 官方版本发布",
        "Gatling 官方版本发布",
        "WireMock 官方版本发布",
        "Airtest 官方版本发布",
        "MeterSphere 官方版本发布",
        "Checkly 官方博客",
        "mabl 官方博客",
        "Gleb Bahmutov 博客",
        "On Test Automation",
        "Martin Fowler",
        "LaunchDarkly 官方博客",
        "PactFlow 官方博客",
        "BrowserStack 官方博客",
        "Maestro 官方博客",
        "QA Wolf 官方博客",
        "MuukTest 官方博客",
        "Qase 官方博客",
        "DevAssure 官方博客",
        "TestMu AI 官方博客",
        "Sauce Labs 官方博客",
        "Ministry of Testing - Test Automation",
        "Applitools Help Center",
        "Postman API Pulse",
        "TesterHome 最新话题",
        "WebdriverIO 官方版本发布",
        "Midscene 官方版本发布",
        "掘金 - Claude Code 与测试Agent",
        "掘金 - Playwright MCP 与 Skill",
        "掘金 - AI 测试用例与脚本生成",
        "掘金 - RAG 与 LLM 测试评测",
    }.issubset(source_names)
    assert len(juejin_sources) <= 6
    assert official_release_sources
    assert source_map["TesterHome AI测试"]["type"] == "testerhome_api"
    assert source_map["TesterHome AI测试"]["priority"] == 2
    assert source_map["TesterHome AI测试"]["max_per_source"] == 1
    assert source_map["TesterHome AI测试"]["time_window_hours"] == 720
    assert source_map["TesterHome AI测试"]["dify_exploration"] is True
    assert source_map["TesterHome AI测试"]["require_keywords"]
    assert source_map["TesterHome AI测试"]["exclude_keywords"]
    assert "AI辅助测试" in source_map["TesterHome AI测试"]["require_keywords"]
    assert "AI 赋能测试" in source_map["TesterHome AI测试"]["require_keywords"]
    assert ["AI", "测试用例"] in source_map["TesterHome AI测试"]["require_keywords"]
    assert ["AI", "测试脚本"] in source_map["TesterHome AI测试"]["require_keywords"]
    assert ["RAG", "评测"] in source_map["TesterHome AI测试"]["require_keywords"]
    assert source_map["TesterHome 自动化工具"]["type"] == "testerhome_api"
    assert source_map["TesterHome 自动化工具"]["priority"] == 2
    assert source_map["TesterHome 自动化工具"]["max_per_source"] == 1
    assert source_map["TesterHome 自动化工具"]["time_window_hours"] == 720
    assert source_map["TesterHome 自动化工具"]["dify_exploration"] is True
    assert source_map["TesterHome 自动化工具"]["require_keywords"]
    assert source_map["TesterHome 自动化工具"]["exclude_keywords"]
    assert "Postman" in source_map["TesterHome 自动化工具"]["require_keywords"]
    assert "WireMock" in source_map["TesterHome 自动化工具"]["require_keywords"]
    assert "JMeter" in source_map["TesterHome 自动化工具"]["require_keywords"]
    assert ["发布", "验证"] in source_map["TesterHome 自动化工具"]["require_keywords"]
    assert ["测试环境", "治理"] in source_map["TesterHome 自动化工具"]["require_keywords"]
    assert source_map["TesterHome 最新话题"]["exclude_keywords"]
    assert source_map["TesterHome 最新话题"]["exclude_title_patterns"]
    assert "失业" in source_map["TesterHome 最新话题"]["exclude_keywords"]
    assert "求助" in source_map["TesterHome 最新话题"]["exclude_keywords"]
    assert source_map["Playwright 官方版本发布"]["time_window_hours"] == 336
    assert source_map["Selenium 官方版本发布"]["time_window_hours"] == 336
    assert source_map["pytest 官方版本发布"]["time_window_hours"] == 336
    assert source_map["k6 官方版本发布"]["time_window_hours"] == 336
    assert source_map["Newman 官方版本发布"]["time_window_hours"] == 336
    assert source_map["Robot Framework 官方版本发布"]["time_window_hours"] == 720
    assert source_map["Cucumber JVM 官方版本发布"]["time_window_hours"] == 720
    assert source_map["Locust 官方版本发布"]["time_window_hours"] == 720
    assert source_map["Gatling 官方版本发布"]["time_window_hours"] == 720
    assert source_map["WireMock 官方版本发布"]["time_window_hours"] == 720
    assert source_map["Airtest 官方版本发布"]["time_window_hours"] == 720
    assert source_map["MeterSphere 官方版本发布"]["time_window_hours"] == 720
    assert source_map["WebdriverIO 官方版本发布"]["time_window_hours"] == 336
    assert source_map["Midscene 官方版本发布"]["time_window_hours"] == 336
    assert any(
        "beta" in pattern.lower()
        for pattern in source_map["WireMock 官方版本发布"]["exclude_title_patterns"]
    )
    assert source_map["Checkly 官方博客"]["priority"] >= 3
    assert source_map["Checkly 官方博客"]["max_per_source"] == 1
    assert source_map["Checkly 官方博客"]["require_keywords"]
    assert source_map["mabl 官方博客"]["priority"] >= 3
    assert source_map["mabl 官方博客"]["max_per_source"] == 1
    assert source_map["mabl 官方博客"]["time_window_hours"] == 720
    assert source_map["mabl 官方博客"]["require_keywords"]
    assert source_map["Gleb Bahmutov 博客"]["priority"] == 3
    assert source_map["Gleb Bahmutov 博客"]["dify_exploration"] is True
    assert source_map["Gleb Bahmutov 博客"]["max_per_source"] == 1
    assert source_map["Gleb Bahmutov 博客"]["require_keywords"]
    assert source_map["On Test Automation"]["priority"] == 3
    assert source_map["On Test Automation"]["dify_exploration"] is True
    assert source_map["On Test Automation"]["max_per_source"] == 1
    assert source_map["On Test Automation"]["require_keywords"]
    assert source_map["Martin Fowler"]["priority"] == 4
    assert source_map["Martin Fowler"]["max_per_source"] == 1
    assert source_map["Martin Fowler"]["exclude_title_patterns"]
    assert source_map["Martin Fowler"]["require_keywords"]
    assert source_map["LaunchDarkly 官方博客"]["max_per_source"] == 1
    assert source_map["LaunchDarkly 官方博客"]["dify_exploration"] is True
    assert source_map["LaunchDarkly 官方博客"]["require_keywords"]
    assert source_map["PactFlow 官方博客"]["max_per_source"] == 1
    assert source_map["PactFlow 官方博客"]["dify_exploration"] is True
    assert source_map["PactFlow 官方博客"]["require_keywords"]
    assert source_map["BrowserStack 官方博客"]["priority"] == 3
    assert source_map["BrowserStack 官方博客"]["max_per_source"] == 1
    assert source_map["BrowserStack 官方博客"]["dify_exploration"] is True
    assert source_map["BrowserStack 官方博客"]["require_keywords"]
    assert source_map["Maestro 官方博客"]["priority"] == 3
    assert source_map["Maestro 官方博客"]["max_per_source"] == 1
    assert source_map["Maestro 官方博客"]["require_keywords"]
    assert source_map["QA Wolf 官方博客"]["priority"] == 3
    assert source_map["QA Wolf 官方博客"]["max_per_source"] == 1
    assert source_map["QA Wolf 官方博客"]["dify_exploration"] is True
    assert source_map["QA Wolf 官方博客"]["require_keywords"]
    assert source_map["MuukTest 官方博客"]["priority"] >= 3
    assert source_map["MuukTest 官方博客"]["max_per_source"] == 1
    assert source_map["MuukTest 官方博客"]["dify_exploration"] is True
    assert source_map["MuukTest 官方博客"]["require_keywords"]
    assert source_map["Qase 官方博客"]["priority"] == 3
    assert source_map["Qase 官方博客"]["max_per_source"] == 1
    assert source_map["Qase 官方博客"]["dify_exploration"] is True
    assert source_map["Qase 官方博客"]["require_keywords"]
    assert "meetup" in source_map["Qase 官方博客"]["exclude_keywords"]
    assert source_map["DevAssure 官方博客"]["priority"] == 3
    assert source_map["DevAssure 官方博客"]["max_per_source"] == 1
    assert source_map["DevAssure 官方博客"]["dify_exploration"] is True
    assert source_map["DevAssure 官方博客"]["require_keywords"]
    assert source_map["TestMu AI 官方博客"]["type"] == "testmu_blog_html"
    assert source_map["TestMu AI 官方博客"]["priority"] >= 4
    assert source_map["TestMu AI 官方博客"]["max_per_source"] == 1
    assert source_map["TestMu AI 官方博客"]["dify_exploration"] is True
    assert source_map["TestMu AI 官方博客"]["require_keywords"]
    assert source_map["Sauce Labs 官方博客"]["type"] == "saucelabs_next_data_json"
    assert source_map["Sauce Labs 官方博客"]["priority"] >= 4
    assert source_map["Sauce Labs 官方博客"]["max_per_source"] == 1
    assert source_map["Sauce Labs 官方博客"]["dify_exploration"] is True
    assert source_map["Sauce Labs 官方博客"]["require_keywords"]
    assert source_map["Ministry of Testing - Test Automation"]["type"] == "mot_news_html"
    assert source_map["Ministry of Testing - Test Automation"]["max_per_source"] == 1
    assert source_map["Ministry of Testing - Test Automation"]["dify_exploration"] is True
    assert source_map["Ministry of Testing - Test Automation"]["require_keywords"]
    assert source_map["Applitools Help Center"]["type"] == "zendesk_help_center_api"
    assert source_map["Applitools Help Center"]["max_per_source"] == 1
    assert source_map["Applitools Help Center"]["dify_exploration"] is True
    assert source_map["Applitools Help Center"]["require_keywords"]
    assert source_map["Applitools Help Center"]["exclude_title_patterns"]
    assert "moved" in source_map["Applitools Help Center"]["exclude_keywords"]
    assert any(
        "migrat" in pattern.lower()
        for pattern in source_map["Applitools Help Center"]["exclude_title_patterns"]
    )
    assert source_map["Postman API Pulse"]["max_per_source"] == 1
    assert source_map["Postman API Pulse"]["dify_exploration"] is True
    assert source_map["Postman API Pulse"]["require_keywords"]
    assert "API testing" in source_map["Postman API Pulse"]["require_keywords"]
    assert "contract testing" in source_map["Postman API Pulse"]["require_keywords"]
    assert any(
        "a new postman is here" in pattern.lower()
        for pattern in source_map["Postman API Pulse"]["exclude_title_patterns"]
    )
    assert source_map["掘金 - Playwright 与自动化测试"]["max_per_source"] == 1
    assert source_map["掘金 - Playwright 与自动化测试"]["time_window_hours"] == 720
    assert source_map["掘金 - Playwright 与自动化测试"]["require_keywords"]
    assert source_map["掘金 - Playwright 与自动化测试"]["exclude_keywords"]
    assert source_map["掘金 - AI赋能测试"]["max_per_source"] == 1
    assert source_map["掘金 - AI赋能测试"]["time_window_hours"] == 720
    assert source_map["掘金 - AI赋能测试"]["require_keywords"]
    assert source_map["掘金 - AI赋能测试"]["exclude_keywords"]
    assert source_map["掘金 - Claude Code 与测试Agent"]["priority"] == 3
    assert source_map["掘金 - Claude Code 与测试Agent"]["max_per_source"] == 1
    assert source_map["掘金 - Claude Code 与测试Agent"]["time_window_hours"] == 720
    assert source_map["掘金 - Claude Code 与测试Agent"]["require_keywords"]
    assert source_map["掘金 - Claude Code 与测试Agent"]["exclude_keywords"]
    assert source_map["掘金 - Playwright MCP 与 Skill"]["priority"] == 3
    assert source_map["掘金 - Playwright MCP 与 Skill"]["max_per_source"] == 1
    assert source_map["掘金 - Playwright MCP 与 Skill"]["time_window_hours"] == 720
    assert source_map["掘金 - Playwright MCP 与 Skill"]["require_keywords"]
    assert source_map["掘金 - Playwright MCP 与 Skill"]["exclude_keywords"]
    assert source_map["掘金 - AI 测试用例与脚本生成"]["priority"] == 3
    assert source_map["掘金 - AI 测试用例与脚本生成"]["max_per_source"] == 1
    assert source_map["掘金 - AI 测试用例与脚本生成"]["time_window_hours"] == 720
    assert source_map["掘金 - AI 测试用例与脚本生成"]["require_keywords"]
    assert source_map["掘金 - AI 测试用例与脚本生成"]["exclude_keywords"]
    assert source_map["掘金 - RAG 与 LLM 测试评测"]["priority"] == 3
    assert source_map["掘金 - RAG 与 LLM 测试评测"]["max_per_source"] == 1
    assert source_map["掘金 - RAG 与 LLM 测试评测"]["time_window_hours"] == 720
    assert source_map["掘金 - RAG 与 LLM 测试评测"]["require_keywords"]
    assert source_map["掘金 - RAG 与 LLM 测试评测"]["exclude_keywords"]
    assert source_map["Gleb Bahmutov 博客"]["priority"] < source_map["Ministry of Testing - Test Automation"]["priority"]
    assert source_map["On Test Automation"]["priority"] < source_map["Ministry of Testing - Test Automation"]["priority"]
    assert fetcher.filter_config["max_per_source"] == 0
    assert fetcher.filter_config["max_per_source_final"] == 0
    assert fetcher.filter_config["allow_prerelease_titles"] is True
    assert fetcher.filter_config["dify_candidate_limit"] == 7
    assert fetcher.filter_config["dify_candidate_max_per_source"] == 0
    assert fetcher.filter_config["dify_exploration_slots"] == 4
    assert fetcher.filter_config["min_quality_score"] == 5
    assert fetcher.filter_config["dify_rate_limit_abort_threshold"] == 2
    assert fetcher.filter_config["dify_rate_limit_cooldown_seconds"] == 18
    assert fetcher.filter_config["dify_rate_limit_retry_rounds"] == 1
    assert fetcher.filter_config["preferred_scenario_tags"]
    assert "AI生成脚本" in fetcher.filter_config["preferred_scenario_tags"]
    assert "AI回归优化" in fetcher.filter_config["preferred_scenario_tags"]
    assert "AI测试数据" in fetcher.filter_config["preferred_scenario_tags"]
    assert "测试策略" in fetcher.filter_config.get("scenario_keywords", {})
    assert "AI赋能测试" in fetcher.filter_config.get("scenario_keywords", {})
    assert "AI生成用例" in fetcher.filter_config.get("scenario_keywords", {})
    assert "AI生成脚本" in fetcher.filter_config.get("scenario_keywords", {})
    assert "AI辅助缺陷诊断" in fetcher.filter_config.get("scenario_keywords", {})
    assert "AI回归优化" in fetcher.filter_config.get("scenario_keywords", {})
    assert "AI测试数据" in fetcher.filter_config.get("scenario_keywords", {})
    assert "LLM应用评测" in fetcher.filter_config.get("scenario_keywords", {})
    assert "WebdriverIO" in fetcher.filter_config.get("keywords", [])
    assert "Locust" in fetcher.filter_config.get("keywords", [])
    assert "Gatling" in fetcher.filter_config.get("keywords", [])
    assert "WireMock" in fetcher.filter_config.get("keywords", [])
    assert "Airtest" in fetcher.filter_config.get("keywords", [])
    assert "MeterSphere" in fetcher.filter_config.get("keywords", [])
    assert "Claude Code" in fetcher.filter_config.get("keywords", [])
    assert "LLM" in fetcher.filter_config.get("keywords", [])
    assert "Function Calling" in fetcher.filter_config.get("keywords", [])
    assert "Tool Calling" in fetcher.filter_config.get("keywords", [])
    assert "WebdriverIO" in fetcher.filter_config.get("scenario_keywords", {}).get("UI自动化", [])
    assert "Airtest" in fetcher.filter_config.get("scenario_keywords", {}).get("UI自动化", [])
    assert "MeterSphere" in fetcher.filter_config.get("scenario_keywords", {}).get("测试平台", [])
    assert "WireMock" in fetcher.filter_config.get("scenario_keywords", {}).get("接口自动化", [])
    assert "Function Calling" in fetcher.filter_config.get("scenario_keywords", {}).get("AI赋能测试", [])
    assert "Tool Calling" in fetcher.filter_config.get("scenario_keywords", {}).get("AI赋能测试", [])
    assert "Locust" in fetcher.filter_config.get("scenario_keywords", {}).get("性能工程", [])
    assert "Gatling" in fetcher.filter_config.get("scenario_keywords", {}).get("性能工程", [])



def test_publish_to_feishu_persists_failed_wecom_status(tmp_path, monkeypatch):
    saved_links = []

    class FakePublisher:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_document(self, title):
            return {"document_id": "doc_123", "is_wiki": False}

        def add_collaborator(self, *args, **kwargs):
            return True

        def set_public_sharing(self, *args, **kwargs):
            return True

        def transfer_owner(self, *args, **kwargs):
            return True

        def write_blocks(self, *args, **kwargs):
            return True

        def get_document_url(self, *args, **kwargs):
            return "https://feishu.cn/docx/doc_123"

    class FakeNotifier:
        def __init__(self, webhook_url):
            self.webhook_url = webhook_url

        def notify_feishu_doc(self, title, doc_url, news_items):
            return False

    monkeypatch.setattr(main_news_bot, "FeishuPublisher", FakePublisher)
    monkeypatch.setattr(main_news_bot, "WeComBotNotifier", FakeNotifier)

    bot = main_news_bot.NewsBot()
    bot.feishu_app_id = "app"
    bot.feishu_app_secret = "secret"
    bot.wecom_webhook_url = "https://example.com/webhook"
    bot.fetcher.save_to_history = lambda links: saved_links.extend(links)
    bot.publish_state_store = main_news_bot.PublishStateStore(str(tmp_path / "publish_records.json"))

    news_items = [
        NewsItem("高质量AI资讯", "https://example.com/news-1", "2026-03-21", "OpenAI", summary="摘要")
    ]

    bot._publish_to_feishu(news_items, date_label="2026-03-21")

    records = bot.publish_state_store.load_records()
    assert len(saved_links) == 1
    assert saved_links[0].link == "https://example.com/news-1"
    assert len(records) == 1
    assert records[0]["channels"]["feishu"]["status"] == "success"
    assert records[0]["channels"]["wecom"]["status"] == "failed"
    assert records[0]["doc_url"] == "https://feishu.cn/docx/doc_123"


def test_publish_to_feishu_skips_wecom_when_flag_enabled(tmp_path, monkeypatch):
    class FakePublisher:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_document(self, title):
            return {"document_id": "doc_skip_wecom", "is_wiki": False}

        def add_collaborator(self, *args, **kwargs):
            return True

        def set_public_sharing(self, *args, **kwargs):
            return True

        def transfer_owner(self, *args, **kwargs):
            return True

        def write_blocks(self, *args, **kwargs):
            return True

        def get_document_url(self, *args, **kwargs):
            return "https://feishu.cn/docx/doc_skip_wecom"

    class FakeNotifier:
        called = False

        def __init__(self, webhook_url):
            self.webhook_url = webhook_url

        def notify_feishu_doc(self, title, doc_url, news_items):
            FakeNotifier.called = True
            return True

    monkeypatch.setattr(main_news_bot, "FeishuPublisher", FakePublisher)
    monkeypatch.setattr(main_news_bot, "WeComBotNotifier", FakeNotifier)

    bot = main_news_bot.NewsBot()
    bot.feishu_app_id = "app"
    bot.feishu_app_secret = "secret"
    bot.wecom_webhook_url = "https://example.com/webhook"
    bot.skip_wecom_notifications = True
    bot.fetcher.save_to_history = lambda links: None
    bot.publish_state_store = main_news_bot.PublishStateStore(str(tmp_path / "publish_records.json"))

    bot._publish_to_feishu(
        [NewsItem("测试联调文章", "https://example.com/a", "2026-03-21", "OpenAI", summary="摘要")],
        date_label="2026-03-21",
    )

    records = bot.publish_state_store.load_records()
    assert FakeNotifier.called is False
    assert records[0]["channels"]["wecom"]["status"] == "skipped"


def test_retry_pending_wecom_notifications_updates_status_to_success(tmp_path, monkeypatch):
    class FakeNotifier:
        sent_titles = []

        def __init__(self, webhook_url):
            self.webhook_url = webhook_url

        def notify_feishu_doc(self, title, doc_url, news_items):
            FakeNotifier.sent_titles.append(title)
            return True

    monkeypatch.setattr(main_news_bot, "WeComBotNotifier", FakeNotifier)

    bot = main_news_bot.NewsBot()
    bot.wecom_webhook_url = "https://example.com/webhook"
    bot.publish_state_store = main_news_bot.PublishStateStore(str(tmp_path / "publish_records.json"))
    bot.publish_state_store.create_record(
        bot_type="ai_news",
        doc_title="AI 每日新闻速递 (2026-03-21)",
        doc_url="https://feishu.cn/docx/doc_retry",
        news_items=[
            {"title": "待补发文章", "link": "https://example.com/retry", "source": "OpenAI", "summary": "摘要"}
        ],
        article_links=["https://example.com/retry"],
        wecom_title="AI 每日新闻速递 (2026-03-21)",
        channels={
            "feishu": {"status": "success"},
            "wecom": {"status": "failed", "retry_count": 1},
        },
    )

    bot._retry_pending_wecom_notifications()

    records = bot.publish_state_store.load_records()
    assert FakeNotifier.sent_titles == ["AI 每日新闻速递 (2026-03-21)"]
    assert records[0]["channels"]["wecom"]["status"] == "success"
    assert records[0]["channels"]["wecom"]["retry_count"] == 2


def test_retry_pending_wecom_notifications_skips_when_flag_enabled(tmp_path, monkeypatch):
    class FakeNotifier:
        sent_titles = []

        def __init__(self, webhook_url):
            self.webhook_url = webhook_url

        def notify_feishu_doc(self, title, doc_url, news_items):
            FakeNotifier.sent_titles.append(title)
            return True

    monkeypatch.setattr(main_news_bot, "WeComBotNotifier", FakeNotifier)

    bot = main_news_bot.NewsBot()
    bot.wecom_webhook_url = "https://example.com/webhook"
    bot.skip_wecom_notifications = True
    bot.publish_state_store = main_news_bot.PublishStateStore(str(tmp_path / "publish_records.json"))
    bot.publish_state_store.create_record(
        bot_type="ai_news",
        doc_title="AI 每日新闻速递 (2026-03-21)",
        doc_url="https://feishu.cn/docx/doc_retry",
        news_items=[
            {"title": "待补发文章", "link": "https://example.com/retry", "source": "OpenAI", "summary": "摘要"}
        ],
        article_links=["https://example.com/retry"],
        wecom_title="AI 每日新闻速递 (2026-03-21)",
        channels={
            "feishu": {"status": "success"},
            "wecom": {"status": "failed", "retry_count": 1},
        },
    )

    bot._retry_pending_wecom_notifications()

    records = bot.publish_state_store.load_records()
    assert FakeNotifier.sent_titles == []
    assert records[0]["channels"]["wecom"]["status"] == "failed"
    assert records[0]["channels"]["wecom"]["retry_count"] == 1


def test_cli_run_news_bot_executes_async_main(monkeypatch):
    awaited = {"value": False}

    async def fake_main():
        awaited["value"] = True

    monkeypatch.setattr(main_news_bot, "main", fake_main)

    cli.run_news_bot()

    assert awaited["value"] is True


def test_publish_to_feishu_writes_blocks_before_public_sharing(tmp_path, monkeypatch):
    call_order = []

    class FakePublisher:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_document(self, title):
            call_order.append("create_document")
            return {"document_id": "doc_safe", "is_wiki": False}

        def add_collaborator(self, *args, **kwargs):
            call_order.append("add_collaborator")
            return True

        def set_public_sharing(self, *args, **kwargs):
            call_order.append("set_public_sharing")
            return True

        def transfer_owner(self, *args, **kwargs):
            call_order.append("transfer_owner")
            return True

        def write_blocks(self, *args, **kwargs):
            call_order.append("write_blocks")
            return True

        def get_document_url(self, *args, **kwargs):
            return "https://feishu.cn/docx/doc_safe"

    class FakeNotifier:
        def __init__(self, webhook_url):
            self.webhook_url = webhook_url

        def notify_feishu_doc(self, title, doc_url, news_items):
            return True

    monkeypatch.setattr(main_news_bot, "FeishuPublisher", FakePublisher)
    monkeypatch.setattr(main_news_bot, "WeComBotNotifier", FakeNotifier)

    bot = main_news_bot.NewsBot()
    bot.feishu_app_id = "app"
    bot.feishu_app_secret = "secret"
    bot.feishu_owner_user_id = "owner"
    bot.wecom_webhook_url = "https://example.com/webhook"
    bot.fetcher.save_to_history = lambda links: None
    bot.publish_state_store = main_news_bot.PublishStateStore(str(tmp_path / "publish_records.json"))

    bot._publish_to_feishu([NewsItem("标题", "https://example.com/a", "2026-03-21", "源", summary="摘要")], date_label="2026-03-21")

    assert call_order.index("write_blocks") < call_order.index("add_collaborator")
    assert call_order.index("write_blocks") < call_order.index("set_public_sharing")
    assert call_order.index("write_blocks") < call_order.index("transfer_owner")


def test_run_scheduler_now_executes_once_without_starting_scheduler(monkeypatch):
    events = []

    class FakeScheduler:
        def __init__(self, *args, **kwargs):
            events.append("scheduler_init")

        def add_job(self, func, trigger, id):
            events.append(f"add_job:{id}")

        def start(self):
            events.append("scheduler_start")

    monkeypatch.setattr(run_scheduler, "BlockingScheduler", FakeScheduler)
    monkeypatch.setattr(run_scheduler, "CronTrigger", lambda *args, **kwargs: ("cron", kwargs))
    monkeypatch.setattr(run_scheduler, "load_config", lambda path="config/news_config.yaml": {"scheduler": {"enabled": True}})
    monkeypatch.setattr(run_scheduler, "qa_job", lambda: events.append("qa_job"))
    monkeypatch.setattr(run_scheduler, "news_job", lambda: events.append("news_job"))
    monkeypatch.setattr(run_scheduler.sys, "argv", ["run_scheduler.py", "--now"])

    run_scheduler.main()

    assert "qa_job" in events
    assert "news_job" in events
    assert "scheduler_start" not in events


def test_qa_bot_reads_wecom_webhook_from_env(monkeypatch):
    monkeypatch.setenv("WECOM_QA_BOT_WEBHOOK_URL", "https://example.com/qa-hook")
    monkeypatch.delenv("WECOM_BOT_WEBHOOK_URL", raising=False)

    bot = run_qa_bot.QABot()

    assert bot.wecom_webhook_url == "https://example.com/qa-hook"


def test_qa_get_reference_time_normalizes_mixed_timezone_values():
    bot = run_qa_bot.QABot()

    items = [
        NewsItem(
            "仅日期字符串",
            "https://example.com/date-only",
            "2026-03-23",
            "来源A",
        ),
        NewsItem(
            "带时区时间",
            "https://example.com/aware",
            "2026-03-23T09:00:00+00:00",
            "来源B",
            published_at=datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc),
        ),
    ]

    reference_time = bot._get_reference_time(items)

    assert reference_time == datetime(2026, 3, 23, 9, 0, tzinfo=timezone.utc)


def test_qa_publish_to_feishu_skips_wecom_when_flag_enabled(tmp_path, monkeypatch):
    class FakePublisher:
        def __init__(self, *_args, **_kwargs):
            pass

        def create_document(self, title):
            return {"document_id": "doc_qa_skip_wecom", "is_wiki": False}

        def add_collaborator(self, *args, **kwargs):
            return True

        def set_public_sharing(self, *args, **kwargs):
            return True

        def transfer_owner(self, *args, **kwargs):
            return True

        def write_blocks(self, *args, **kwargs):
            return True

        def get_document_url(self, *args, **kwargs):
            return "https://feishu.cn/docx/doc_qa_skip_wecom"

    class FakeNotifier:
        called = False

        def __init__(self, webhook_url):
            self.webhook_url = webhook_url

        def notify_feishu_doc(self, title, doc_url, news_items):
            FakeNotifier.called = True
            return True

    monkeypatch.setattr(run_qa_bot, "FeishuPublisher", FakePublisher)
    monkeypatch.setattr(run_qa_bot, "WeComBotNotifier", FakeNotifier)

    bot = run_qa_bot.QABot()
    bot.feishu_app_id = "app"
    bot.feishu_app_secret = "secret"
    bot.wecom_webhook_url = "https://example.com/qa-webhook"
    bot.skip_wecom_notifications = True
    bot.fetcher.save_to_history = lambda links: None
    bot.publish_state_store = run_qa_bot.PublishStateStore(str(tmp_path / "qa_publish_records.json"))
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")

    bot._publish_to_feishu(
        [NewsItem("QA 联调文章", "https://example.com/qa", "2026-03-21", "TesterHome", summary="摘要")],
        date_label="2026-03-21",
    )

    records = bot.publish_state_store.load_records()
    assert FakeNotifier.called is False
    assert records[0]["channels"]["wecom"]["status"] == "skipped"


def test_extract_readable_text_from_html_removes_noise():
    fetcher = AINewsFetcher()
    html = """
    <html>
      <head>
        <title>测试</title>
        <style>.hidden { display:none; }</style>
        <script>console.log('ignore')</script>
      </head>
      <body>
        <nav>导航</nav>
        <article>
          <h1>模型发布</h1>
          <p>这是正文第一段。</p>
          <p>这是正文第二段。</p>
        </article>
        <footer>版权信息</footer>
      </body>
    </html>
    """

    text = fetcher._extract_readable_text_from_html(html)

    assert "这是正文第一段" in text
    assert "这是正文第二段" in text
    assert "console.log" not in text
    assert "导航" not in text


def test_apply_diversity_constraints_limits_same_source_and_category():
    bot = main_news_bot.NewsBot()
    bot.fetcher.filter_config = {"max_count": 10, "max_per_source_final": 1, "max_per_category_final": 2}

    items = [
        NewsItem("OpenAI A", "https://a", "2026-03-21", "OpenAI", category="模型发布", score=10),
        NewsItem("OpenAI B", "https://b", "2026-03-21", "OpenAI", category="模型发布", score=9),
        NewsItem("Google A", "https://c", "2026-03-21", "Google", category="模型发布", score=8),
        NewsItem("NVIDIA A", "https://d", "2026-03-21", "NVIDIA", category="工程实践", score=7),
    ]

    selected = bot._apply_diversity_constraints(items)

    assert [item.title for item in selected] == ["OpenAI A", "Google A", "NVIDIA A"]


def test_qa_rank_news_items_prefers_more_scenario_tags_when_scores_equal(tmp_path):
    bot = run_qa_bot.QABot()
    bot.fetcher.filter_config = {
        "max_count": 10,
        "max_per_source_final": 10,
        "max_per_category_final": 10,
    }
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")

    items = [
        NewsItem(
            "多场景测试实践",
            "https://example.com/qa-multi",
            "2026-03-21",
            "官方源A",
            category="测试实践",
            score=8,
            source_priority=2,
            scenario_tags=["接口自动化", "AI赋能测试"],
            score_breakdown={
                "testing_relevance": 8,
                "practical_value": 8,
                "source_authority": 8,
                "timeliness": 8,
            },
        ),
        NewsItem(
            "单场景测试实践",
            "https://example.com/qa-single",
            "2026-03-21",
            "官方源B",
            category="测试实践",
            score=8,
            source_priority=2,
            scenario_tags=["接口自动化"],
            score_breakdown={
                "testing_relevance": 8,
                "practical_value": 8,
                "source_authority": 8,
                "timeliness": 8,
            },
        ),
    ]

    ranked = bot._rank_news_items(items)

    assert [item.title for item in ranked] == ["多场景测试实践", "单场景测试实践"]


def test_qa_rank_news_items_prefers_preferred_ai_scenarios_when_scores_equal(tmp_path):
    bot = run_qa_bot.QABot()
    bot.fetcher.filter_config = {
        "max_count": 10,
        "max_per_source_final": 10,
        "max_per_category_final": 10,
        "preferred_scenario_tags": ["AI生成脚本", "AI回归优化", "AI测试数据"],
    }
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")

    items = [
        NewsItem(
            "Z AI 回归优化实践",
            "https://example.com/qa-ai",
            "2026-03-21",
            "DevAssure 官方博客",
            category="测试实践",
            score=8,
            source_priority=3,
            scenario_tags=["AI回归优化", "AI赋能测试"],
            score_breakdown={
                "testing_relevance": 8,
                "practical_value": 8,
                "source_authority": 8,
                "timeliness": 8,
            },
        ),
        NewsItem(
            "A 测试策略实践",
            "https://example.com/qa-general",
            "2026-03-21",
            "Google Testing Blog",
            category="测试实践",
            score=8,
            source_priority=3,
            scenario_tags=["测试策略", "质量效能"],
            score_breakdown={
                "testing_relevance": 8,
                "practical_value": 8,
                "source_authority": 8,
                "timeliness": 8,
            },
        ),
    ]

    ranked = bot._rank_news_items(items)

    assert [item.title for item in ranked] == ["Z AI 回归优化实践", "A 测试策略实践"]


def test_qa_rank_news_items_prefers_direct_practice_source_over_release_notes_when_scores_equal(tmp_path):
    bot = run_qa_bot.QABot()
    bot.fetcher.filter_config = {
        "max_count": 10,
        "max_per_source_final": 10,
        "max_per_category_final": 10,
    }
    bot.recent_topic_store.file_path = str(tmp_path / "qa_recent_topics.json")
    bot.source_quality_store.file_path = str(tmp_path / "qa_source_quality.json")

    items = [
        NewsItem(
            "用 Claude Code 生成 REST Assured 接口验收测试",
            "https://example.com/on-test-automation",
            "2026-03-21",
            "On Test Automation",
            category="测试实践",
            score=7,
            source_priority=3,
            scenario_tags=["接口自动化", "AI赋能测试"],
            score_breakdown={
                "testing_relevance": 7,
                "practical_value": 6,
                "source_authority": 8,
                "timeliness": 7,
            },
        ),
        NewsItem(
            "Cucumber JVM v7.34.3 发布",
            "https://example.com/cucumber-release",
            "2026-03-21",
            "Cucumber JVM 官方版本发布",
            category="测试实践",
            score=7,
            source_priority=2,
            scenario_tags=["测试框架", "质量效能"],
            score_breakdown={
                "testing_relevance": 7,
                "practical_value": 6,
                "source_authority": 8,
                "timeliness": 7,
            },
        ),
    ]

    ranked = bot._rank_news_items(items)

    assert [item.source for item in ranked] == ["On Test Automation", "Cucumber JVM 官方版本发布"]


@pytest.mark.parametrize("bot_factory", [main_news_bot.NewsBot, run_qa_bot.QABot])
def test_rank_news_items_merges_same_event_and_keeps_highest_scored_entry(bot_factory):
    bot = bot_factory()
    bot.fetcher.filter_config = {"max_count": 10, "max_per_source_final": 10, "max_per_category_final": 10}

    items = [
        NewsItem("GPT-5 正式发布，OpenAI 新模型亮相", "https://36kr.com/p/1", "2026-03-21", "36Kr", category="模型发布", score=8),
        NewsItem("Anthropic 发布 Claude 新版本", "https://anthropic.com/claude", "2026-03-21", "Anthropic", category="模型发布", score=9),
        NewsItem("OpenAI 发布 GPT-5", "https://openai.com/gpt5", "2026-03-21", "OpenAI", category="模型发布", score=10),
    ]

    ranked = bot._rank_news_items(items)

    assert [item.title for item in ranked] == ["OpenAI 发布 GPT-5", "Anthropic 发布 Claude 新版本"]
    assert ranked[0].merged_count == 2
    assert set(ranked[0].related_sources) == {"36Kr"}


@pytest.mark.parametrize(
    ("bot_factory", "expected_file_prefix"),
    [
        (main_news_bot.NewsBot, "ai_news_review_"),
        (run_qa_bot.QABot, "qa_news_review_"),
    ],
)
def test_export_review_report_writes_markdown_sections(tmp_path, bot_factory, expected_file_prefix):
    bot = bot_factory()
    bot.review_export_dir = str(tmp_path)
    bot.fetcher.filter_config = {
        "max_count": 2,
        "max_per_source_final": 1,
        "max_per_category_final": 3,
    }

    items = [
        NewsItem("OpenAI 发布 GPT-5", "https://openai.com/gpt5", "2026-03-21", "OpenAI", category="模型发布", score=10),
        NewsItem("Anthropic 发布 Claude 新版本", "https://anthropic.com/claude", "2026-03-21", "Anthropic", category="模型发布", score=9),
        NewsItem("OpenAI 推出新 Agent 工具链", "https://openai.com/agent", "2026-03-21", "OpenAI", category="工程实践", score=8),
        NewsItem("GPT-5 正式发布，OpenAI 新模型亮相", "https://36kr.com/p/1", "2026-03-21", "36Kr", category="模型发布", score=8),
        NewsItem("MCP 自动化测试编排实践", "https://example.com/mcp", "2026-03-21", "InfoQ", category="测试实践", score=7),
        NewsItem("测试用例生成技巧汇总", "https://example.com/cases", "2026-03-21", "TesterHome", category="测试实践", score=3),
    ]

    ranked = bot._rank_news_items(items)
    export_path = bot._export_review_report(date_label="2026-03-21")

    assert [item.title for item in ranked] == ["OpenAI 发布 GPT-5", "Anthropic 发布 Claude 新版本"]
    assert export_path is not None
    assert os.path.basename(export_path).startswith(expected_file_prefix)

    with open(export_path, "r", encoding="utf-8") as file:
        content = file.read()

    assert "## 已入选" in content
    assert "## 高分未入选" in content
    assert "## 被多样性约束淘汰" in content
    assert "## 被同事件合并淘汰" in content
    assert "## 被近 7 天主题去重淘汰" in content
    assert "## 被 Dify 限流跳过" in content
    assert "## 信源降权观察项" in content
    assert "## 临界分内容" in content
    assert "OpenAI 推出新 Agent 工具链" in content
    assert "GPT-5 正式发布，OpenAI 新模型亮相" in content
    assert "测试用例生成技巧汇总" in content


@pytest.mark.parametrize("bot_factory", [main_news_bot.NewsBot, run_qa_bot.QABot])
def test_rank_news_items_filters_recent_topics_from_last_7_days(tmp_path, bot_factory):
    bot = bot_factory()
    bot.fetcher.filter_config = {
        "max_count": 10,
        "max_per_source_final": 10,
        "max_per_category_final": 10,
    }

    bot.recent_topic_store.file_path = str(tmp_path / "recent_topics.json")
    bot.recent_topic_store.add_topics(
        [
            NewsItem(
                "OpenAI 发布 GPT-5",
                "https://openai.com/gpt5-old",
                "2026-03-20",
                "OpenAI",
                category="模型发布",
                score=8,
                source_priority=2,
            )
        ],
        date_label="2026-03-20",
    )

    items = [
        NewsItem("GPT-5 正式发布，OpenAI 新模型亮相", "https://36kr.com/p/1", "2026-03-21", "36Kr", category="模型发布", score=9, source_priority=2),
        NewsItem("Anthropic 发布 Claude 新版本", "https://anthropic.com/claude", "2026-03-21", "Anthropic", category="模型发布", score=8, source_priority=2),
    ]

    ranked = bot._rank_news_items(items)

    assert [item.title for item in ranked] == ["Anthropic 发布 Claude 新版本"]
    assert len(bot.latest_review_report["recent_topic_rejected_items"]) == 1
    assert bot.latest_review_report["recent_topic_rejected_items"][0]["item"].title == "GPT-5 正式发布，OpenAI 新模型亮相"


@pytest.mark.parametrize("bot_factory", [main_news_bot.NewsBot, run_qa_bot.QABot])
def test_rank_news_items_allows_recent_topic_override_for_stronger_source(tmp_path, bot_factory):
    bot = bot_factory()
    bot.fetcher.filter_config = {
        "max_count": 10,
        "max_per_source_final": 10,
        "max_per_category_final": 10,
    }

    bot.recent_topic_store.file_path = str(tmp_path / "recent_topics.json")
    bot.recent_topic_store.add_topics(
        [
            NewsItem(
                "GPT-5 正式发布，OpenAI 新模型亮相",
                "https://media.example.com/gpt5",
                "2026-03-20",
                "自媒体",
                category="模型发布",
                score=7,
                source_priority=3,
            )
        ],
        date_label="2026-03-20",
    )

    items = [
        NewsItem("OpenAI 发布 GPT-5", "https://openai.com/gpt5", "2026-03-21", "OpenAI", category="模型发布", score=9, source_priority=1),
        NewsItem("Anthropic 发布 Claude 新版本", "https://anthropic.com/claude", "2026-03-21", "Anthropic", category="模型发布", score=8, source_priority=2),
    ]

    ranked = bot._rank_news_items(items)

    assert [item.title for item in ranked] == ["OpenAI 发布 GPT-5", "Anthropic 发布 Claude 新版本"]
    assert bot.latest_review_report["recent_topic_rejected_items"] == []


@pytest.mark.parametrize("bot_factory", [main_news_bot.NewsBot, run_qa_bot.QABot])
def test_rank_news_items_demotes_unhealthy_source_with_dynamic_adjustment(tmp_path, bot_factory):
    bot = bot_factory()
    bot.fetcher.filter_config = {
        "max_count": 10,
        "max_per_source_final": 10,
        "max_per_category_final": 10,
    }

    bot.source_quality_store.file_path = str(tmp_path / "source_quality.json")
    bot.source_quality_store.record_run(
        {
            "低质源": {
                "candidate_count": 10,
                "low_quality_count": 6,
                "same_event_merged_count": 2,
                "recent_topic_duplicate_count": 1,
                "selected_count": 1,
            },
            "稳定源": {
                "candidate_count": 10,
                "low_quality_count": 0,
                "same_event_merged_count": 0,
                "recent_topic_duplicate_count": 0,
                "selected_count": 7,
            },
        },
        date_label="2026-03-20",
    )

    items = [
        NewsItem("低质源文章", "https://low.example.com/1", "2026-03-21", "低质源", category="测试实践", score=8, source_priority=1),
        NewsItem("稳定源文章", "https://stable.example.com/1", "2026-03-21", "稳定源", category="测试实践", score=8, source_priority=2),
    ]

    ranked = bot._rank_news_items(items)

    assert [item.source for item in ranked] == ["稳定源", "低质源"]
    assert bot.latest_review_report["source_observations"][0]["source"] == "低质源"
