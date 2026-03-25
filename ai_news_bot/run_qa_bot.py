import os
import sys
import asyncio
import logging
import json
import re
import time
from typing import Optional, List, Any, Dict, cast
from dotenv import load_dotenv # type: ignore

import datetime
# 注意这里引入的不再是原来的泛AI Fetcher，而是新写的 QA Fetcher
try:
    from qa_news_fetcher import QANewsFetcher, NewsItem # type: ignore
    from editorial_review import (
        apply_diversity_constraints,
        build_review_report,
        filter_recent_topic_duplicates,
        merge_same_event_items,
        write_review_export,
    )
    from recent_topic_store import RecentTopicStore
    from source_quality_store import SourceQualityStore
    from services.common.dify_client import DifyClient, DifyRequestError, DifyRateLimitError # type: ignore
    from feishu_publisher import FeishuPublisher, FeishuBlockBuilder # type: ignore
    from wecom_bot_notifier import WeComBotNotifier # type: ignore
    from publish_state_store import PublishStateStore # type: ignore
except ImportError:
    # 兼容本地运行路径
    from .qa_news_fetcher import QANewsFetcher, NewsItem # type: ignore
    from .editorial_review import (
        apply_diversity_constraints,
        build_review_report,
        filter_recent_topic_duplicates,
        merge_same_event_items,
        write_review_export,
    )
    from .recent_topic_store import RecentTopicStore
    from .source_quality_store import SourceQualityStore
    from .services.common.dify_client import DifyClient, DifyRequestError, DifyRateLimitError # type: ignore
    from .feishu_publisher import FeishuPublisher, FeishuBlockBuilder # type: ignore
    from .wecom_bot_notifier import WeComBotNotifier # type: ignore
    from .publish_state_store import PublishStateStore # type: ignore

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [QA_BOT] - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("QANewsBot")

class QABot:
    def __init__(self):
        # 显式声明属性以帮助 IDE/Pyre 类型推查
        self.feishu_app_id: Optional[str] = None
        self.feishu_app_secret: Optional[str] = None
        self.feishu_folder_token: str = ""
        self.feishu_owner_user_id: Optional[str] = None
        self.dify_base: Optional[str] = None
        self.dify_user: str = "lifeng16527"
        self.dify_key: Optional[str] = None
        self.wecom_webhook_url: str = ""
        self.skip_wecom_notifications: bool = False
        
        self._load_config()
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "qa_tools_config.yaml")
        self.fetcher = QANewsFetcher(config_path)
        current_bot_dir = os.path.dirname(os.path.abspath(__file__))
        state_file = os.path.join(current_bot_dir, "data", "qa_publish_records.json")
        self.publish_state_store = PublishStateStore(state_file)
        self.recent_topic_store = RecentTopicStore(os.path.join(current_bot_dir, "data", "qa_recent_topics.json"))
        self.source_quality_store = SourceQualityStore(os.path.join(current_bot_dir, "data", "qa_source_quality.json"))
        self.review_export_dir = os.path.join(current_bot_dir, "data", "review_exports")
        self.latest_review_report = {}
        self._current_run_source_metrics = {}
        self._source_adjustments = {}
        self._latest_low_quality_rejected_items = []
        self._latest_rate_limit_skipped_items = []

    def _sanitize_storage_tag(self, tag: str) -> str:
        """将运行标签规整为安全的文件名片段。"""
        normalized = re.sub(r"[^0-9a-zA-Z]+", "_", str(tag or "").strip())
        normalized = normalized.strip("_")
        return normalized or "isolated"

    def _build_tagged_file_path(self, file_path: str, storage_tag: str) -> str:
        """为单个状态文件生成带标签的隔离路径。"""
        directory, filename = os.path.split(file_path)
        basename, extension = os.path.splitext(filename)
        return os.path.join(directory, f"{basename}__{storage_tag}{extension}")

    def _apply_runtime_storage_tag(self, tag: str) -> None:
        """切换到带标签的隔离状态文件，便于同日重复联调且不污染正式记录。"""
        storage_tag = self._sanitize_storage_tag(tag)

        self.fetcher.history_file = self._build_tagged_file_path(self.fetcher.history_file, storage_tag)
        self.fetcher.sent_history = self.fetcher._load_sent_history()

        self.recent_topic_store.file_path = self._build_tagged_file_path(self.recent_topic_store.file_path, storage_tag)
        self.source_quality_store.file_path = self._build_tagged_file_path(self.source_quality_store.file_path, storage_tag)
        self.publish_state_store.file_path = self._build_tagged_file_path(self.publish_state_store.file_path, storage_tag)
        self.review_export_dir = os.path.join(self.review_export_dir, storage_tag)
        logger.info(f"当前运行已切换到隔离状态文件标签: {storage_tag}")

    def _is_wecom_enabled(self) -> bool:
        """判断当前运行是否允许发送 QA 企业微信通知。"""
        return bool(self.wecom_webhook_url) and not self.skip_wecom_notifications

    def _get_publish_limit(self) -> int:
        """读取 QA 日报最终发布上限"""
        return int(self.fetcher.filter_config.get("max_count", 10))

    def _get_breakdown_score(self, item: Any, key: str) -> int:
        """获取指定维度的子评分。"""
        score_breakdown = getattr(item, "score_breakdown", {}) or {}
        try:
            return int(score_breakdown.get(key, 0))
        except Exception:
            return 0

    def _get_dify_throttle_backoff_seconds(self) -> int:
        """获取 Dify 限流后的额外退避时间。"""
        return int(self.fetcher.filter_config.get("dify_throttle_backoff_seconds", 6))

    def _get_dify_rate_limit_cooldown_seconds(self) -> int:
        """获取 Dify 限流后的冷却重试等待时间。"""
        return int(self.fetcher.filter_config.get("dify_rate_limit_cooldown_seconds", 18))

    def _get_dify_rate_limit_retry_rounds(self) -> int:
        """获取 Dify 限流后的冷却重试轮次。"""
        return int(self.fetcher.filter_config.get("dify_rate_limit_retry_rounds", 1))

    def _get_dify_candidate_max_per_source(self) -> int:
        """读取进入 Dify 前的单信源候选上限。"""
        return int(self.fetcher.filter_config.get("dify_candidate_max_per_source", 1) or 0)

    def _get_dify_exploration_slots(self) -> int:
        """读取为新增信源预留的 Dify 探索名额。"""
        return int(self.fetcher.filter_config.get("dify_exploration_slots", 0) or 0)

    def _get_preferred_scenario_tags(self) -> set[str]:
        """读取需要优先保留的测试场景标签。"""
        preferred_tags = self.fetcher.filter_config.get("preferred_scenario_tags", []) or []
        return {str(tag) for tag in preferred_tags if tag}

    def _count_preferred_scenario_matches(self, item: Any) -> int:
        """统计当前条目命中的优先场景数量。"""
        preferred_tags = self._get_preferred_scenario_tags()
        if not preferred_tags:
            return 0
        scenario_tags = {str(tag) for tag in (getattr(item, "scenario_tags", []) or []) if tag}
        return sum(1 for tag in scenario_tags if tag in preferred_tags)

    def _resolve_generated_title(self, item: Any, generated_title: Any) -> str:
        """清洗 Dify 返回的标题，异常时回退原标题。"""
        fallback_title = re.sub(
            r"\s+",
            " ",
            str(getattr(item, "original_title", "") or getattr(item, "title", "") or "").replace("**", ""),
        ).strip()
        candidate_title = re.sub(r"\s+", " ", str(generated_title or "").replace("**", "")).strip()
        candidate_lower = candidate_title.lower()
        has_invalid_wrapper = (
            not candidate_title
            or "```" in candidate_title
            or candidate_title.startswith("{")
            or candidate_title.endswith("}")
            or '"title"' in candidate_lower
            or "'title'" in candidate_lower
            or '"summary"' in candidate_lower
            or "'summary'" in candidate_lower
            or candidate_lower.startswith("title:")
            or candidate_lower.startswith("title：")
            or candidate_title.startswith("标题:")
            or candidate_title.startswith("标题：")
        )
        if has_invalid_wrapper:
            if fallback_title and candidate_title != fallback_title:
                logger.warning(f"Dify 生成标题无效，回退原标题: {fallback_title[:20]}...")
            return fallback_title
        return candidate_title

    def _normalize_fallback_text(self, text: Any) -> str:
        """规整本地兜底摘要候选文本，必要时去除 HTML。"""
        normalized_text = str(text or "").strip()
        if not normalized_text:
            return ""
        if "<" in normalized_text and ">" in normalized_text:
            normalized_text = self.fetcher._extract_readable_text_from_html(normalized_text)
        normalized_text = re.sub(r"\s+", " ", normalized_text).strip()
        return normalized_text

    def _build_local_fallback_summary(self, item: Any, max_chars: int = 220) -> str:
        """在 Dify 失败时基于现有正文/摘要生成保守的本地摘要。"""
        title_text = self._resolve_generated_title(item, getattr(item, "title", ""))
        candidate_texts = [
            getattr(item, "content_text", ""),
            getattr(item, "summary", ""),
        ]
        for candidate_text in candidate_texts:
            normalized_text = self._normalize_fallback_text(candidate_text)
            if not normalized_text:
                continue
            if title_text and normalized_text.lower().startswith(title_text.lower()):
                normalized_text = normalized_text[len(title_text):].lstrip("：: -")
            normalized_text = normalized_text.strip()
            if len(normalized_text) < 20:
                continue
            if len(normalized_text) <= max_chars:
                return normalized_text
            return normalized_text[:max_chars].rstrip("，。；;,:： ") + "..."
        return ""

    def _infer_local_fallback_category(self, item: Any) -> str:
        """根据已有场景标签推断降级保留时的默认分类。"""
        scenario_category_map = {
            "AI赋能测试": "智能测试与AI赋能",
            "AI生成用例": "智能测试与AI赋能",
            "AI生成脚本": "智能测试与AI赋能",
            "AI辅助缺陷诊断": "智能测试与AI赋能",
            "AI回归优化": "智能测试与AI赋能",
            "AI测试数据": "智能测试与AI赋能",
            "LLM应用评测": "智能测试与AI赋能",
            "测试策略": "测试策略与质量工程",
            "质量效能": "研发效能与工具",
            "测试平台": "研发效能与工具",
            "接口自动化": "自动化工程实践",
            "UI自动化": "自动化工程实践",
            "测试框架": "自动化工程实践",
            "测试数据": "自动化工程实践",
            "性能工程": "自动化工程实践",
        }
        for scenario_tag in getattr(item, "scenario_tags", []) or []:
            if scenario_tag in scenario_category_map:
                return scenario_category_map[scenario_tag]
        return getattr(item, "category", "") or "测试实践"

    def _build_local_fallback_score_breakdown(self, item: Any, min_quality_score: int) -> Dict[str, int]:
        """为降级保留条目补齐保守的评分拆解。"""
        scenario_tag_count = len(getattr(item, "scenario_tags", []) or [])
        source_priority = int(getattr(item, "source_priority", 99) or 99)
        source_authority = max(5, 9 - min(source_priority, 4))
        testing_relevance = max(min_quality_score, 5 + min(scenario_tag_count, 2))
        practical_value = max(min_quality_score - 1, 6 if getattr(item, "content_text", "") else 5)
        return {
            "timeliness": max(min_quality_score, 6),
            "source_authority": source_authority,
            "testing_relevance": testing_relevance,
            "practical_value": practical_value,
        }

    def _can_use_local_fallback(self, item: Any, fallback_summary: str) -> bool:
        """判断当前条目是否适合在 Dify 失败时走本地兜底。"""
        if len(fallback_summary) < 20:
            return False
        source_priority = int(getattr(item, "source_priority", 99) or 99)
        scenario_tags = list(getattr(item, "scenario_tags", []) or [])
        if source_priority <= 2:
            return True
        return bool(scenario_tags) and source_priority <= 3

    def _apply_local_fallback_summary(self, item: Any, reason: str, min_quality_score: int) -> bool:
        """当 Dify 失败时，尝试用本地信息生成保守可发布的兜底结果。"""
        fallback_summary = self._build_local_fallback_summary(item)
        if not self._can_use_local_fallback(item, fallback_summary):
            return False

        item.original_title = item.original_title or item.title
        item.title = self._resolve_generated_title(item, item.title)
        item.summary = fallback_summary
        item.highlights = ""
        item.category = self._infer_local_fallback_category(item)
        item.score = min_quality_score
        item.score_breakdown = self._build_local_fallback_score_breakdown(item, min_quality_score)
        logger.warning(f"Dify 失败，已降级保留该条资讯: {item.title[:20]}... 原因: {reason}")
        return True

    def _reset_run_metrics(self) -> None:
        """清空本轮运行中的信源质量统计。"""
        self._current_run_source_metrics = {}
        self._latest_low_quality_rejected_items = []
        self._latest_rate_limit_skipped_items = []

    def _get_source_config(self, source_name: str) -> Dict[str, Any]:
        """按信源名称查找配置，便于读取 Dify 预选增强标记。"""
        for source in self.fetcher.sources:
            if str(source.get("name", "")) == str(source_name or ""):
                return source
        return {}

    def _is_dify_exploration_source(self, source_name: str) -> bool:
        """判断当前信源是否属于需要优先探索的新接入来源。"""
        source_config = self._get_source_config(source_name)
        return bool(source_config.get("dify_exploration", False))

    def _record_source_metric(self, source: str, metric_key: str, delta: int = 1) -> None:
        """记录当前运行中的信源质量指标。"""
        source_key = source or "未知来源"
        source_metrics = self._current_run_source_metrics.setdefault(
            source_key,
            {
                "candidate_count": 0,
                "low_quality_count": 0,
                "same_event_merged_count": 0,
                "recent_topic_duplicate_count": 0,
                "selected_count": 0,
            },
        )
        source_metrics[metric_key] = int(source_metrics.get(metric_key, 0) or 0) + delta

    def _refresh_source_adjustments(self, sources=None) -> None:
        """加载最近窗口内的信源调权结果。"""
        self._source_adjustments = self.source_quality_store.get_source_adjustments(sources=sources)

    def _get_source_dynamic_adjustment(self, source: str) -> int:
        """读取指定信源的动态调权分。"""
        return int(self._source_adjustments.get(source or "未知来源", 0) or 0)

    def _get_source_rank_bucket(self, source: str) -> int:
        """为 QA 排序提供稳定的信源桶位，优先直连实践源，其次中性源，最后版本发布。"""
        source_name = str(source or "")
        if "官方版本发布" in source_name:
            return 2

        source_config = self._get_source_config(source_name)
        source_type = str(source_config.get("type", "") or "").lower()
        if source_type in {
            "rss",
            "testerhome_api",
            "mot_news_html",
            "juejin_api",
            "zendesk_help_center_api",
            "testmu_blog_html",
            "saucelabs_next_data_json",
        }:
            return 0
        return 1

    def _persist_source_quality_metrics(self, date_label: Optional[str] = None) -> None:
        """持久化本轮运行产生的信源质量指标。"""
        if not self._current_run_source_metrics:
            return
        self.source_quality_store.record_run(self._current_run_source_metrics, date_label=date_label)

    def _get_reference_time(self, items: List) -> Optional[datetime.datetime]:
        """尽量从候选内容中提取统一的参考时间，用于跨天主题比较。"""
        parsed_times = []
        for item in items:
            published_at = getattr(item, "published_at", None)
            if published_at:
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=datetime.timezone.utc)
                else:
                    published_at = published_at.astimezone(datetime.timezone.utc)
                parsed_times.append(published_at)
                continue
            published_text = getattr(item, "published", "")
            if not published_text:
                continue
            try:
                parsed_time = datetime.datetime.fromisoformat(str(published_text).replace("Z", "+00:00"))
                if parsed_time.tzinfo is None:
                    parsed_time = parsed_time.replace(tzinfo=datetime.timezone.utc)
                else:
                    parsed_time = parsed_time.astimezone(datetime.timezone.utc)
                parsed_times.append(parsed_time)
                continue
            except ValueError:
                pass
            try:
                parsed_times.append(
                    datetime.datetime.strptime(str(published_text), "%Y-%m-%d").replace(
                        tzinfo=datetime.timezone.utc
                    )
                )
            except ValueError:
                continue
        if not parsed_times:
            return None
        return max(parsed_times)

    def _prioritize_candidates_for_summarization(self, news_items: List) -> List:
        """在进入 Dify 前先做质量优先排序，为后续强多样性预选提供基线顺序。"""
        release_noise_pattern = re.compile(r"\bnightly\b|\brc\d+\b|\b(?:alpha|beta|preview|pre-release|snapshot)\b", re.IGNORECASE)

        def sort_key(item: Any):
            source = getattr(item, "source", "") or ""
            title = getattr(item, "original_title", "") or getattr(item, "title", "") or ""
            title_lower = title.lower()
            published_at = getattr(item, "published_at", None)
            freshness = published_at.timestamp() if published_at else 0
            preferred_scenario_match_count = self._count_preferred_scenario_matches(item)
            scenario_match_count = len(getattr(item, "scenario_tags", []) or [])
            source_priority = int(getattr(item, "source_priority", 99) or 99)
            source_bucket = self._get_source_rank_bucket(source)
            title_noise_penalty = 1 if release_noise_pattern.search(title_lower) else 0

            return (
                title_noise_penalty,
                -preferred_scenario_match_count,
                source_bucket,
                source_priority,
                -scenario_match_count,
                -freshness,
                title,
            )

        return sorted(news_items, key=sort_key)

    def _select_dify_candidates_for_summarization(self, prioritized_news_items: List, limit: int) -> List:
        """按激进多样性策略挑选进入 Dify 的候选，确保新增源有更高出场率。"""
        if limit <= 0:
            return prioritized_news_items

        max_per_source = self._get_dify_candidate_max_per_source()
        exploration_slots = min(limit, max(0, self._get_dify_exploration_slots()))
        selected_items: List[Any] = []
        selected_keys = set()
        source_counts: Dict[str, int] = {}
        exploration_selected_count = 0

        def _item_identity(item: Any) -> tuple[str, str]:
            return (
                str(getattr(item, "link", "") or ""),
                str(getattr(item, "original_title", "") or getattr(item, "title", "") or ""),
            )

        def _try_select(item: Any, respect_source_limit: bool = True) -> bool:
            identity = _item_identity(item)
            if identity in selected_keys:
                return False

            source = str(getattr(item, "source", "") or "未知来源")
            if respect_source_limit and max_per_source > 0 and source_counts.get(source, 0) >= max_per_source:
                return False

            selected_items.append(item)
            selected_keys.add(identity)
            source_counts[source] = source_counts.get(source, 0) + 1
            return True

        exploration_candidates = [
            item
            for item in prioritized_news_items
            if self._is_dify_exploration_source(getattr(item, "source", ""))
        ]

        for item in exploration_candidates:
            if len(selected_items) >= limit or exploration_selected_count >= exploration_slots:
                break
            if _try_select(item, respect_source_limit=True):
                exploration_selected_count += 1

        for item in prioritized_news_items:
            if len(selected_items) >= limit:
                break
            _try_select(item, respect_source_limit=True)

        if len(selected_items) < limit:
            for item in prioritized_news_items:
                if len(selected_items) >= limit:
                    break
                _try_select(item, respect_source_limit=False)

        logger.info(
            "进入 Dify 前按强多样性策略预选候选："
            f"{len(prioritized_news_items)} -> {len(selected_items)} "
            f"(新增源保底={exploration_selected_count}, 单源上限={max_per_source if max_per_source > 0 else '不限'})"
        )
        return selected_items

    def _build_dify_source_content(self, item: Any) -> str:
        """为 Dify 组装带来源与场景标签的正文，减少语义判断缺上下文。"""
        source = getattr(item, "source", "") or "未知来源"
        scenario_tags = list(getattr(item, "scenario_tags", []) or [])
        source_content = getattr(item, "content_text", "") or item.summary

        content_parts = [f"来源: {source}"]
        if scenario_tags:
            content_parts.append(f"预识别测试场景标签: {'、'.join(scenario_tags)}")
        if source_content:
            content_parts.append(source_content)
        return "\n".join(content_parts)

    def _should_rescue_testing_strategy_item(
        self,
        item: Any,
        score: int,
        min_quality_score: int,
        score_breakdown: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """判断是否应对高置信测试策略条目做窄范围保底，避免被模型误杀。"""
        if score >= min_quality_score:
            return False

        source = getattr(item, "source", "") or ""
        source_lower = source.lower()
        scenario_tags = {str(tag) for tag in (getattr(item, "scenario_tags", []) or []) if tag}
        if "测试策略" not in scenario_tags:
            return False

        if "官方版本发布" in source:
            return False

        source_priority = int(getattr(item, "source_priority", 99) or 99)
        if source_priority > 2:
            return False

        strategy_keywords = self.fetcher.filter_config.get("scenario_keywords", {}).get("测试策略", []) or []
        text = " ".join(
            part
            for part in [
                source,
                getattr(item, "original_title", "") or getattr(item, "title", ""),
                getattr(item, "summary", ""),
                getattr(item, "content_text", ""),
            ]
            if part
        ).lower()
        strategy_hit_count = sum(1 for keyword in strategy_keywords if keyword and str(keyword).lower() in text)
        testing_anchor_keywords = ("test", "testing", "qa", "质量", "测试", "回归")
        has_testing_anchor = any(keyword in text for keyword in testing_anchor_keywords)
        has_testing_source = any(keyword in source_lower for keyword in ("testing", "qa", "质量", "测试"))
        score_breakdown = score_breakdown or {}
        practical_value = int(score_breakdown.get("practical_value", 0) or 0)
        source_authority = int(score_breakdown.get("source_authority", 0) or 0)

        return (
            strategy_hit_count >= 1
            and (has_testing_source or has_testing_anchor)
            and (practical_value >= 5 or source_authority >= 8)
        )

    def _apply_testing_strategy_score_rescue(
        self,
        item: Any,
        score: int,
        min_quality_score: int,
        category: str,
        score_breakdown: Optional[Dict[str, Any]] = None,
    ) -> tuple[int, str, Dict[str, Any], bool]:
        """对高置信测试策略条目做最小必要的评分保底。"""
        normalized_breakdown = dict(score_breakdown or {})
        if not self._should_rescue_testing_strategy_item(
            item,
            score=score,
            min_quality_score=min_quality_score,
            score_breakdown=normalized_breakdown,
        ):
            return score, category, normalized_breakdown, False

        rescued_score = max(score, min_quality_score)
        normalized_breakdown["testing_relevance"] = max(
            int(normalized_breakdown.get("testing_relevance", 0) or 0),
            min_quality_score,
        )
        normalized_category = category or "测试策略与质量工程"
        if normalized_category in {"工程方法", "工程实践", "其他"}:
            normalized_category = "测试策略与质量工程"
        logger.info(f"命中测试策略高置信兜底，评分提升 {score} -> {rescued_score}: {getattr(item, 'title', '')[:20]}...")
        return rescued_score, normalized_category, normalized_breakdown, True

    def _rank_news_items(
        self,
        news_items: List,
        low_quality_rejected_items: Optional[List[Dict[str, Any]]] = None,
        rate_limit_skipped_items: Optional[List[Dict[str, Any]]] = None,
    ) -> List:
        """按测试相关质量、新鲜度和信源优先级做排序"""
        self._refresh_source_adjustments(sources=sorted({item.source for item in news_items if getattr(item, "source", "")}))

        def sort_key(item: Any):
            published_at = getattr(item, "published_at", None)
            freshness = published_at.timestamp() if published_at else 0
            source_adjustment = self._get_source_dynamic_adjustment(getattr(item, "source", ""))
            item.source_dynamic_adjustment = source_adjustment
            effective_score = getattr(item, "score", 0) + source_adjustment
            preferred_scenario_match_count = self._count_preferred_scenario_matches(item)
            scenario_match_count = len(getattr(item, "scenario_tags", []) or [])
            source_rank_bucket = self._get_source_rank_bucket(getattr(item, "source", ""))
            return (
                -effective_score,
                -getattr(item, "score", 0),
                -self._get_breakdown_score(item, "testing_relevance"),
                -self._get_breakdown_score(item, "practical_value"),
                -preferred_scenario_match_count,
                -scenario_match_count,
                source_rank_bucket,
                -self._get_breakdown_score(item, "source_authority"),
                -self._get_breakdown_score(item, "timeliness"),
                -freshness,
                getattr(item, "source_priority", 99),
                item.title,
            )

        ranked_items = sorted(news_items, key=sort_key)
        merged_items, merged_out_items = merge_same_event_items(self.fetcher, ranked_items)
        for merged_item in merged_out_items:
            self._record_source_metric(getattr(merged_item, "source", ""), "same_event_merged_count")
        recent_topics = self.recent_topic_store.get_recent_topics(reference_time=self._get_reference_time(merged_items))
        fresh_items, recent_topic_rejected_items = filter_recent_topic_duplicates(self.fetcher, merged_items, recent_topics)
        for rejected_item in recent_topic_rejected_items:
            self._record_source_metric(getattr(rejected_item["item"], "source", ""), "recent_topic_duplicate_count")
        diversified_items, diversity_rejected_items = self._apply_diversity_constraints(fresh_items, return_rejected=True)
        selected_items = diversified_items[: self._get_publish_limit()]
        remaining_items = diversified_items[self._get_publish_limit():]
        for selected_item in selected_items:
            self._record_source_metric(getattr(selected_item, "source", ""), "selected_count")
        self.latest_review_report = build_review_report(
            self.fetcher,
            selected_items=selected_items,
            remaining_items=remaining_items,
            merged_out_items=merged_out_items,
            diversity_rejected_items=diversity_rejected_items,
            recent_topic_rejected_items=recent_topic_rejected_items,
            low_quality_rejected_items=low_quality_rejected_items or self._latest_low_quality_rejected_items,
            rate_limit_skipped_items=rate_limit_skipped_items or self._latest_rate_limit_skipped_items,
            source_observations=self.source_quality_store.get_source_observations(
                sources=sorted({item.source for item in news_items if getattr(item, "source", "")})
            ),
        )
        return selected_items

    def _apply_diversity_constraints(self, ranked_items: List, return_rejected: bool = False) -> List:
        """限制同一来源和同一类别的占比，提升 QA 日报多样性。"""
        max_per_source = int(self.fetcher.filter_config.get("max_per_source_final", 1))
        max_per_category = int(self.fetcher.filter_config.get("max_per_category_final", 2))
        selected_items, rejected_items = apply_diversity_constraints(ranked_items, max_per_source, max_per_category)
        if return_rejected:
            return selected_items, rejected_items
        return selected_items

    def _export_review_report(self, date_label: Optional[str] = None):
        """导出 QA 人工复核候选池，方便检查内容贴合度。"""
        if not self.latest_review_report:
            return None
        export_path = write_review_export(
            report=self.latest_review_report,
            export_dir=self.review_export_dir,
            bot_type="qa_news",
            report_title="QA 日报人工复核候选池",
            date_label=date_label,
        )
        logger.info(f"已导出 QA 日报人工复核候选池: {export_path}")
        return export_path

    def _serialize_news_items(self, news_items: List) -> List[dict]:
        """将资讯对象转换为可持久化结构。"""
        serialized_items = []
        for item in news_items:
            serialized_items.append(
                {
                    "title": item.title,
                    "original_title": item.original_title,
                    "link": item.link,
                    "source": item.source,
                    "summary": item.summary,
                    "published": item.published,
                    "score_breakdown": item.score_breakdown,
                    "related_sources": getattr(item, "related_sources", []),
                    "merged_count": getattr(item, "merged_count", 1),
                    "scenario_tags": getattr(item, "scenario_tags", []),
                }
            )
        return serialized_items

    def _build_news_items_from_record(self, record: dict) -> List[NewsItem]:
        """从持久化记录恢复企微通知所需的资讯对象。"""
        restored_items = []
        for item_data in record.get("news_items", []):
            restored_items.append(
                NewsItem(
                    title=item_data.get("title", ""),
                    link=item_data.get("link", ""),
                    published=item_data.get("published", ""),
                    source=item_data.get("source", ""),
                    summary=item_data.get("summary", ""),
                    original_title=item_data.get("original_title", item_data.get("title", "")),
                    score_breakdown=item_data.get("score_breakdown", {}),
                    related_sources=item_data.get("related_sources", []),
                    merged_count=item_data.get("merged_count", 1),
                    scenario_tags=item_data.get("scenario_tags", []),
                )
            )
        return restored_items

    def _retry_pending_wecom_notifications(self):
        """在新一轮发布前先补发未成功的 QA 企微通知。"""
        if not self._is_wecom_enabled():
            if self.skip_wecom_notifications:
                logger.info("当前运行已开启跳过 QA 企业微信通知，补发逻辑已跳过。")
            return

        pending_records = self.publish_state_store.get_retryable_records("wecom")
        if not pending_records:
            return

        logger.info(f"检测到 {len(pending_records)} 条待补发的 QA 企业微信通知，开始补发...")
        notifier = WeComBotNotifier(self.wecom_webhook_url)
        for record in pending_records:
            news_items = self._build_news_items_from_record(record)
            success = notifier.notify_feishu_doc(record.get("wecom_title", record.get("doc_title", "")), record.get("doc_url", ""), news_items)
            if success:
                self.publish_state_store.update_channel_status(
                    record["record_id"],
                    "wecom",
                    "success",
                    increment_retry=True,
                )
                logger.info(f"QA 企业微信补发成功: {record.get('doc_title', '')}")
            else:
                self.publish_state_store.update_channel_status(
                    record["record_id"],
                    "wecom",
                    "failed",
                    error="QA 企业微信补发失败",
                    increment_retry=True,
                )
                logger.warning(f"QA 企业微信补发失败，保留待重试状态: {record.get('doc_title', '')}")

    def _load_config(self):
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        load_dotenv(dotenv_path=env_path)
        self.feishu_app_id = os.getenv("FEISHU_APP_ID")
        self.feishu_app_secret = os.getenv("FEISHU_APP_SECRET")
        self.feishu_folder_token = os.getenv("FEISHU_FOLDER_TOKEN", "")
        self.feishu_owner_user_id = os.getenv("FEISHU_OWNER_USER_ID")
        
        self.dify_base = os.getenv("DIFY_API_BASE")
        self.dify_user = os.getenv("DIFY_USER_ID", "lifeng16527")
        
        # ⚠️ 隔离 1: Dify API KEY，优先使用专属于 QA 深度导读的 Key，如果没有则降级用通用的
        self.dify_key = os.getenv("DIFY_QA_API_KEY") or os.getenv("DIFY_API_KEY")
        
        # QA 线优先读取专属企微地址，未配置时再降级走通用地址
        self.wecom_webhook_url = (
            os.getenv("WECOM_QA_BOT_WEBHOOK_URL")
            or os.getenv("WECOM_BOT_WEBHOOK_URL")
            or os.getenv("WECOM_WEBHOOK_URL", "")
        )

        if not all([self.feishu_app_id, self.feishu_app_secret]):
            logger.warning("缺少飞书应用凭证。文档将无法创建。")

    async def run(self, date_label: Optional[str] = None):
        logger.info("--- 开始运行 QA/研发效能 测开资讯采集 ---")
        self._reset_run_metrics()

        self._retry_pending_wecom_notifications()
        
        # 1. 抓取新闻，使用配置文件中 filter.max_count 作为 limit 上限
        news_items = await self.fetcher.fetch_all_async()
        
        if not news_items:
            logger.info("【QA_BOT】今日未发现精选的产研高质量好文。")
            return

        logger.info(f"【QA_BOT】深度精选出 {len(news_items)} 篇干货文章！")

        logger.info("第一点五步：正在补抓正文内容以提升测试相关性判断...")
        news_items = await self.fetcher.enrich_items_with_full_content_async(news_items)
        news_items = self.fetcher._assign_scenario_tags(news_items)

        # 2. 生成摘要
        news_items = self._summarize_news(news_items)
        self._persist_source_quality_metrics(date_label=date_label)
        if not news_items:
            logger.info("【QA_BOT】质量筛选后没有可发布的测试资讯。")
            return

        self._export_review_report(date_label=date_label)

        # 3. 发布至飞书文档 (隔离版)
        self._publish_to_feishu(news_items, date_label=date_label)

    def _summarize_news(self, news_items: List) -> List:
        logger.info("第二步：正在通过 Dify 生成测试专家视角的深度导读...")
        dify_client: Optional[DifyClient] = None
        # 使用 cast 或显式检查来帮助 Pyre 确定类型
        if self.dify_base and self.dify_key:
            dify_client = DifyClient(self.dify_base, self.dify_key, self.dify_user)
        else:
            logger.warning("Dify 未配置，QA 质量闸门不可用，本次跳过测试资讯推送。")
            return []
        
        qa_prompt_template = """标题: {title}
内容: {content}

请根据该文章与【软件测试、QA自动化、测试平台建设、质量保障及测试研效】领域的关联度，为其打分 (1-10分)。
⚠️如果文章仅仅是泛泛地讨论前端开发、通用的 AI 工具（如 Cursor 融资、普通的AI编码教程等）、或是纯代码开发而未强调任何测试落地场景，请务必给出低于 3 分的打分！
如果文章是主流测试框架或工具链的官方版本更新，例如 Playwright、Cypress、Appium、pytest、Selenium、k6、Allure、Postman 等，并且包含会影响测试工作流的功能增强、兼容性修复、稳定性改进或使用方式变化，请将其视为高相关内容，不要因为“版本发布”表述而误判为泛技术新闻。
如果文章讨论测试驱动开发（TDD）、测试方法论、质量工程策略、功能开关默认值、灰度发布、回滚策略、发布安全、回归预防等主题，并且给出了可落地的测试/质量保障机制，也应视为与测试工程师工作高度相关，不要误判为“泛工程方法论”。
如果文章明确落在 AI 辅助测试的具体实践场景，例如 AI 生成测试用例、AI 生成测试脚本、AI 缺陷诊断、AI 回归优化、AI 测试数据生成、LLM 应用评测，请优先视为高相关内容；这类文章即使来自较新的测试厂商博客，只要有明确机制、工作流或失败经验，也不应被低估。
如果文章只是厂商营销、招聘、品牌宣传、泛趋势判断，没有明确机制、真实数据、失败模式分析或测试落地经验，即使来自测试厂商，也不要给高分。
如果文章只是闲聊、随笔、职业焦虑、泛讨论、工具盘点但没有明确测试落地经验，也不要给高分。

请严格遵守以下 JSON 格式返回，不要包含任何其他说明文字或 Markdown 标记：
{{
  "title": "(精炼后的中文标题，必须简洁专业且与标题主旨一致)",
  "summary": "(中文摘要，紧贴核心价值，不超过250字)",
  "highlights": "(提取3个核心看点。格式：'* [Emoji] **关键词**: 说明')",
  "score": (整数，1-10，与测试关联度越高分越高。泛型新闻小于3分),
  "category": "(文章所属类别)",
  "score_breakdown": {{
    "timeliness": (整数，1-10，时效性),
    "source_authority": (整数，1-10，信源可信度),
    "testing_relevance": (整数，1-10，与测试工程师工作的贴合度),
    "practical_value": (整数，1-10，可直接落地的实操价值)
  }}
}}"""

        summarized_items = []
        low_quality_rejected_items: List[Dict[str, Any]] = []
        rate_limit_skipped_items: List[Dict[str, Any]] = []
        min_quality_score = int(self.fetcher.filter_config.get("min_quality_score", 3))
        rate_limit_abort_threshold = int(self.fetcher.filter_config.get("dify_rate_limit_abort_threshold", 0) or 0)
        rate_limit_retry_rounds = self._get_dify_rate_limit_retry_rounds()
        rate_limit_cooldown_seconds = self._get_dify_rate_limit_cooldown_seconds()
        consecutive_rate_limit_count = 0
        prioritized_news_items = self._prioritize_candidates_for_summarization(news_items)
        dify_candidate_limit = int(self.fetcher.filter_config.get("dify_candidate_limit", 0) or 0)
        if dify_candidate_limit > 0:
            prioritized_news_items = self._select_dify_candidates_for_summarization(
                prioritized_news_items,
                dify_candidate_limit,
            )
        client = cast(Any, dify_client)

        def _handle_success(item: Any, data: Dict[str, Any]) -> None:
            nonlocal consecutive_rate_limit_count
            consecutive_rate_limit_count = 0
            item.title = self._resolve_generated_title(item, data.get("title", item.title))
            item.summary = data.get("summary", item.summary)
            item.highlights = data.get("highlights", "")

            score = int(data.get("score", 0))
            category = data.get("category", "其他")
            score_breakdown = data.get("score_breakdown", {}) or {}
            score, category, score_breakdown, _rescued = self._apply_testing_strategy_score_rescue(
                item,
                score=score,
                min_quality_score=min_quality_score,
                category=category,
                score_breakdown=score_breakdown,
            )
            if score < min_quality_score:
                self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                low_quality_rejected_items.append(
                    {
                        "item": item,
                        "reason": f"质量评分 {score} 低于阈值 {min_quality_score}",
                    }
                )
                logger.info(f"质量评分过低 ({score}) 丢弃: {item.title[:20]}...")
                return

            item.category = category
            item.score = score
            item.score_breakdown = score_breakdown
            if not item.summary.strip():
                self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                low_quality_rejected_items.append(
                    {
                        "item": item,
                        "reason": "摘要为空，未通过质量闸门",
                    }
                )
                logger.warning(f"摘要为空，跳过: {item.title[:20]}...")
                return
            summarized_items.append(item)

        def _summarize_single_item(item: Any) -> str:
            nonlocal consecutive_rate_limit_count
            try:
                source_content = self._build_dify_source_content(item)
                item.original_title = item.original_title or item.title
                res_text = client.summarize_content(item.title, source_content, prompt_template=qa_prompt_template)
                if not res_text:
                    consecutive_rate_limit_count = 0
                    if self._apply_local_fallback_summary(item, "Dify 返回空响应", min_quality_score):
                        summarized_items.append(item)
                        return "fallback"
                    logger.warning(f"Dify 返回空响应，跳过原文: {item.title[:20]}...")
                    return "empty"
                try:
                    data = json.loads(res_text)
                except json.JSONDecodeError:
                    consecutive_rate_limit_count = 0
                    if self._apply_local_fallback_summary(item, "Dify 解析 JSON 失败", min_quality_score):
                        summarized_items.append(item)
                        return "fallback"
                    self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                    logger.warning(f"Dify 解析 JSON 失败，跳过原文: {item.title[:20]}...")
                    return "invalid_json"
                _handle_success(item, data)
                return "ok"
            except DifyRateLimitError as e:
                consecutive_rate_limit_count += 1
                backoff_seconds = self._get_dify_throttle_backoff_seconds()
                logger.warning(f"Dify 触发吞吐限流，{backoff_seconds}s 后再处理下一条资讯: {item.title[:20]}...")
                time.sleep(backoff_seconds)
                logger.error(f"调用 Dify 异常，跳过该条资讯 (源: {item.title}): {e}")
                return "rate_limit"
            except DifyRequestError as e:
                consecutive_rate_limit_count = 0
                if self._apply_local_fallback_summary(item, f"Dify 基础设施异常: {e}", min_quality_score):
                    summarized_items.append(item)
                    return "fallback"
                logger.error(f"调用 Dify 基础设施异常，跳过该条资讯 (源: {item.title}): {e}")
                return "infra_error"
            except Exception as e:
                consecutive_rate_limit_count = 0
                if self._apply_local_fallback_summary(item, f"Dify 未知异常: {e}", min_quality_score):
                    summarized_items.append(item)
                    return "fallback"
                self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                logger.error(f"调用 Dify 异常，跳过该条资讯 (源: {item.title}): {e}")
                return "error"

        def _append_rate_limit_skipped(item: Any, reason: str) -> None:
            if self._apply_local_fallback_summary(item, reason, min_quality_score):
                summarized_items.append(item)
                return
            rate_limit_skipped_items.append({"item": item, "reason": reason})

        def _process_batch(batch_items: List[Any], is_retry_round: bool = False) -> List[Any]:
            deferred_items: List[Any] = []
            for index, item in enumerate(batch_items):
                if not is_retry_round:
                    self._record_source_metric(getattr(item, "source", ""), "candidate_count")
                result = _summarize_single_item(item)
                if result != "rate_limit":
                    continue

                if is_retry_round:
                    _append_rate_limit_skipped(item, "Dify 吞吐限流，冷却重试后仍失败")
                else:
                    deferred_items.append(item)

                if rate_limit_abort_threshold and consecutive_rate_limit_count >= rate_limit_abort_threshold:
                    remaining_items = batch_items[index + 1 :]
                    if remaining_items:
                        if is_retry_round:
                            for remaining_item in remaining_items:
                                _append_rate_limit_skipped(
                                    remaining_item,
                                    f"Dify 连续限流达到阈值 {rate_limit_abort_threshold}，冷却重试轮次提前结束",
                                )
                        else:
                            deferred_items.extend(remaining_items)
                    if is_retry_round:
                        logger.warning(
                            f"Dify 连续限流已达到阈值 {rate_limit_abort_threshold}，冷却重试轮次提前结束。"
                        )
                    else:
                        logger.warning(
                            f"Dify 连续限流已达到阈值 {rate_limit_abort_threshold}，本轮剩余候选转入冷却重试。"
                        )
                    break
            return deferred_items

        pending_retry_items = _process_batch(prioritized_news_items, is_retry_round=False)
        if pending_retry_items and rate_limit_retry_rounds > 0:
            for retry_round_index in range(rate_limit_retry_rounds):
                logger.info(
                    f"Dify 限流后进入冷却重试，第 {retry_round_index + 1}/{rate_limit_retry_rounds} 轮，{rate_limit_cooldown_seconds}s 后重试 {len(pending_retry_items)} 条候选。"
                )
                time.sleep(rate_limit_cooldown_seconds)
                consecutive_rate_limit_count = 0
                pending_retry_items = _process_batch(pending_retry_items, is_retry_round=True)
                if not pending_retry_items:
                    break
        elif pending_retry_items:
            for pending_item in pending_retry_items:
                _append_rate_limit_skipped(pending_item, "Dify 吞吐限流，未配置冷却重试")

        self._latest_low_quality_rejected_items = low_quality_rejected_items
        self._latest_rate_limit_skipped_items = rate_limit_skipped_items
        ranked_items = self._rank_news_items(
            summarized_items,
            low_quality_rejected_items=low_quality_rejected_items,
            rate_limit_skipped_items=rate_limit_skipped_items,
        )
        logger.info(f"【QA_BOT】质量筛选完成：保留 {len(ranked_items)} 条高质量测试资讯。")
        return ranked_items

    def _publish_to_feishu(self, news_items: List, date_label: Optional[str] = None):
        if not (self.feishu_app_id and self.feishu_app_secret):
             return

        logger.info("第三步：正在执行 QA 版每日读报的飞书发布流程...")
        try:
            publisher = FeishuPublisher(self.feishu_app_id, self.feishu_app_secret, self.feishu_folder_token)
            
            today_str = date_label if date_label else datetime.date.today().strftime("%Y-%m-%d")
            # ⚠️ 从配置读取文档名称前缀
            notif_config = self.fetcher.config.get("notification", {})
            title_prefix = notif_config.get("feishu_doc_title", "AI 前沿：智能测试与研发效能日报")
            doc_title = f"{title_prefix} ({today_str})"
            doc_info = publisher.create_document(doc_title)
            
            if not doc_info:
                logger.error("创建飞书文档失败。")
                return
                
            document_id = doc_info.get("document_id")
            is_wiki = doc_info.get("is_wiki", False)
            node_token = doc_info.get("node_token") if is_wiki else document_id

            blocks = []
            
            # 1️⃣ 顶部标题与副标题区
            main_heading = self.fetcher.config.get("notification", {}).get("feishu_main_heading", "大模型与智能测试 ✖️ 每天只推干货！")
            blocks.append(FeishuBlockBuilder.heading_elements([
                {"text_run": {"content": main_heading, "text_element_style": {"text_color": 3, "bold": True}}}
            ], level=1))
            
            blocks.append(FeishuBlockBuilder.heading_elements([
                {"text_run": {"content": f"发布时间：{today_str}", "text_element_style": {"text_color": 7}}}
            ], level=3))
            blocks.append(FeishuBlockBuilder.divider())

            # 2️⃣ 正文导读区
            for i, item in enumerate(news_items, 1):
                # 蓝色正文标题与来源
                title_prefix = f"【精选推荐0{i}】 " if len(news_items) < 10 else f"{i}. "
                blocks.append(FeishuBlockBuilder.heading_elements([
                    {"text_run": {"content": title_prefix, "text_element_style": {"text_color": 4, "bold": True}}},
                    {"text_run": {"content": item.title, "text_element_style": {"text_color": 1, "bold": True}}}
                ], level=2))
                
                blocks.append(FeishuBlockBuilder.heading_elements([
                    {"text_run": {"content": f"来源: ", "text_element_style": {"text_color": 3, "bold": True}}},
                    {"text_run": {"content": item.source, "text_element_style": {"text_color": 3}}}
                ], level=3))

                # 摘要块（引用样式）
                summary_lines = item.summary.split('\n')
                for line in summary_lines:
                    if line.strip():
                        blocks.append(FeishuBlockBuilder.paragraph(line.strip()))

                # 亮点块（如果有）
                if getattr(item, 'highlights', ''):
                    blocks.append(FeishuBlockBuilder.paragraph(""))
                    blocks.append(FeishuBlockBuilder.paragraph_rich([
                        {"text_run": {"content": "💡 专家辣评：", "text_element_style": {"bold": True, "text_color": 7}}}
                    ]))
                    for line in item.highlights.split('\n'):
                        if line.strip():
                            if line.strip().startswith("- "):
                                blocks.append(FeishuBlockBuilder.bullet_list_rich(line.strip()[2:]))
                            else:
                                blocks.append(FeishuBlockBuilder.bullet_list_rich(line))
                            
                # 原文直达链接
                blocks.append(FeishuBlockBuilder.paragraph(f"👉 传送门: {item.link}"))

                blocks.append(FeishuBlockBuilder.paragraph("")) # 空行
                if i < len(news_items):
                    blocks.append(FeishuBlockBuilder.divider())
            
            # 使用 block 批量追加
            success = publisher.write_blocks(document_id, blocks)
            
            if success:
                final_token = doc_info.get("node_token") if is_wiki else document_id
                doc_url = publisher.get_document_url(final_token, is_wiki=is_wiki)
                logger.info(f"【QA_BOT】成功将内容写入飞书研效文档: {doc_url}")

                # 先写正文，再开放权限，避免暴露空文档或半成品文档
                if self.feishu_owner_user_id:
                    publisher.add_collaborator(node_token, self.feishu_owner_user_id, is_wiki=is_wiki, role="full_access")
                    publisher.transfer_owner(node_token, self.feishu_owner_user_id, is_wiki=is_wiki)
                publisher.set_public_sharing(node_token, is_wiki=is_wiki)

                wecom_title = self.fetcher.config.get("notification", {}).get("wecom_msg_title", "📖 【QA每日干货推送】AI 前沿：智能测试与研发效能快报")
                wecom_status = "pending" if self._is_wecom_enabled() else "skipped"
                record_id = self.publish_state_store.create_record(
                    bot_type="qa_news",
                    doc_title=doc_title,
                    doc_url=doc_url,
                    news_items=self._serialize_news_items(news_items),
                    article_links=[item.link for item in news_items],
                    wecom_title=wecom_title,
                    channels={
                        "feishu": {"status": "success"},
                        "wecom": {"status": wecom_status, "retry_count": 0},
                    },
                )
                
                # 持久化去重
                self.fetcher.save_to_history(news_items)
                self.recent_topic_store.add_topics(news_items, date_label=today_str)
                
                if news_items and self._is_wecom_enabled():
                    logger.info("正在发送测试组专属企业微信通知...")
                    notifier = WeComBotNotifier(self.wecom_webhook_url)
                    wecom_success = notifier.notify_feishu_doc(wecom_title, doc_url, news_items)
                    if wecom_success:
                        self.publish_state_store.update_channel_status(
                            record_id,
                            "wecom",
                            "success",
                            increment_retry=True,
                        )
                    else:
                        self.publish_state_store.update_channel_status(
                            record_id,
                            "wecom",
                            "failed",
                            error="QA 企业微信通知发送失败",
                            increment_retry=True,
                        )
                elif self.skip_wecom_notifications:
                    logger.info("当前运行已开启跳过 QA 企业微信通知，仅保留飞书写入结果。")
            else:
                logger.error("无法向 QA 专属飞书文档写入内容。")
            
        except Exception as e:
            logger.error(f"QA 飞书发布流程发生异常: {e}")

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="抓取和总结，但不写飞书/推企微")
    parser.add_argument("--skip-wecom", action="store_true", help="写入飞书，但跳过企业微信推送")
    parser.add_argument("--storage-tag", help="为本次运行启用隔离状态文件标签，避免污染正式去重/主题/发布记录")
    args = parser.parse_args()
    
    bot = QABot()
    bot.skip_wecom_notifications = args.skip_wecom
    if args.storage_tag:
        bot._apply_runtime_storage_tag(args.storage_tag)
    if args.dry_run:
        logger.info("正在以试运行模式 (DRY-RUN) 执行 QA_BOT...")
        news_items = await bot.fetcher.fetch_all_async()
        if news_items:
            for item in news_items:
                print(f"\n[推文预演 | {item.source}]: {item.title}")
                print(f"[摘要]: {item.summary[:100]}...\n[链接] {item.link}")
        else:
            logger.info("未抓取到任何产研资讯。")
    else:
        await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
