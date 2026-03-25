import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple


def _get_value(item: Any, key: str, default: Any = "") -> Any:
    """兼容对象和字典两种读取方式。"""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _normalize_title(fetcher: Any, title: str) -> str:
    """复用抓取器的标题归一化逻辑，便于跨源比较。"""
    if hasattr(fetcher, "_normalize_title"):
        return fetcher._normalize_title(title)
    return (title or "").strip().lower()


def _extract_similarity_tokens(title: str) -> List[str]:
    """提取适合做事件比对的关键词，尽量保留模型名、厂商名和专有名词。"""
    generic_tokens = {
        "发布",
        "推出",
        "上线",
        "更新",
        "版本",
        "模型",
        "工具",
        "实践",
        "指南",
        "教程",
        "应用",
        "能力",
        "方案",
        "平台",
        "系统",
        "产品",
        "亮相",
        "正式",
        "文章",
        "资讯",
        "新闻",
        "快讯",
        "日报",
        "推荐",
        "干货",
    }
    lower_title = (title or "").lower()
    split_phrases = [
        "正式发布",
        "发布",
        "推出",
        "上线",
        "更新",
        "亮相",
        "实战",
        "教程",
        "指南",
        "实践",
        "方案",
        "能力",
    ]
    for phrase in split_phrases:
        lower_title = lower_title.replace(phrase, " ")
    lower_title = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", lower_title)
    raw_tokens = re.findall(r"[a-z]+(?:[0-9]+)?|[\u4e00-\u9fff]{2,12}", lower_title)

    tokens = []
    for token in raw_tokens:
        if token and token not in generic_tokens:
            tokens.append(token)
    return tokens


def is_same_event(fetcher: Any, left_item: Any, right_item: Any) -> bool:
    """根据标题相似度和类别判断两条资讯是否属于同一事件。"""
    left_category = (_get_value(left_item, "category", "") or "").strip()
    right_category = (_get_value(right_item, "category", "") or "").strip()
    if left_category and right_category and left_category != right_category:
        return False

    left_title = _normalize_title(fetcher, _get_value(left_item, "original_title", "") or _get_value(left_item, "title", ""))
    right_title = _normalize_title(fetcher, _get_value(right_item, "original_title", "") or _get_value(right_item, "title", ""))
    if not left_title or not right_title:
        return False
    if left_title == right_title:
        return True

    shorter_title, longer_title = sorted((left_title, right_title), key=len)
    if len(shorter_title) >= 8 and shorter_title in longer_title:
        return True

    threshold = float(getattr(fetcher, "filter_config", {}).get("same_event_similarity_threshold", 0.72))
    matcher = SequenceMatcher(None, left_title, right_title)
    overlap_tokens = set(_extract_similarity_tokens(left_title)) & set(_extract_similarity_tokens(right_title))
    if len(overlap_tokens) >= 2 and (
        matcher.ratio() >= 0.35
        or matcher.find_longest_match(0, len(left_title), 0, len(right_title)).size / max(1, len(shorter_title)) >= 0.45
    ):
        return True
    if len(shorter_title) >= 8 and matcher.ratio() >= threshold:
        return True

    longest_match = matcher.find_longest_match(0, len(left_title), 0, len(right_title)).size
    return len(shorter_title) >= 8 and (longest_match / max(1, len(shorter_title))) >= threshold


def merge_same_event_items(fetcher: Any, ranked_items: List[Any]) -> Tuple[List[Any], List[Any]]:
    """合并多来源的同一事件，只保留排序最高的主条目。"""
    selected_items: List[Any] = []
    merged_out_items: List[Any] = []

    for item in ranked_items:
        item.related_sources = list(_get_value(item, "related_sources", []) or [])
        item.merged_count = max(1, int(_get_value(item, "merged_count", 1) or 1))

        matched_item: Optional[Any] = None
        for existing_item in selected_items:
            if is_same_event(fetcher, existing_item, item):
                matched_item = existing_item
                break

        if matched_item is None:
            selected_items.append(item)
            continue

        matched_item.merged_count += 1
        if item.source and item.source != matched_item.source and item.source not in matched_item.related_sources:
            matched_item.related_sources.append(item.source)
        merged_out_items.append(item)

    return selected_items, merged_out_items


def filter_recent_topic_duplicates(
    fetcher: Any,
    items: List[Any],
    recent_topics: List[Dict[str, Any]],
) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """过滤近几天已推送过的同主题内容，并允许更强候选覆盖旧主题。"""
    filter_config = getattr(fetcher, "filter_config", {}) or {}
    window_days = int(filter_config.get("recent_topic_window_days", 7))
    override_score_delta = int(filter_config.get("recent_topic_override_score_delta", 2))

    selected_items = []
    rejected_items = []

    for item in items:
        matched_topic = None
        for recent_topic in recent_topics:
            if is_same_event(fetcher, recent_topic, item):
                matched_topic = recent_topic
                break

        if matched_topic is None:
            selected_items.append(item)
            continue

        item_score = int(_get_value(item, "score", 0) or 0)
        recent_score = int(_get_value(matched_topic, "score", 0) or 0)
        item_priority = int(_get_value(item, "source_priority", 99) or 99)
        recent_priority = int(_get_value(matched_topic, "source_priority", 99) or 99)
        should_override = item_score >= recent_score + override_score_delta or (
            item_priority < recent_priority and item_score >= recent_score
        )

        if should_override:
            selected_items.append(item)
            continue

        rejected_items.append(
            {
                "item": item,
                "reason": f"近 {window_days} 天同主题已推送：{_get_value(matched_topic, 'title', '')}",
                "matched_topic": matched_topic,
            }
        )

    return selected_items, rejected_items


def apply_diversity_constraints(
    items: List[Any],
    max_per_source: int,
    max_per_category: int,
) -> Tuple[List[Any], List[Dict[str, Any]]]:
    """限制来源与类别集中度，并记录淘汰原因。"""
    source_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    selected_items: List[Any] = []
    rejected_items: List[Dict[str, Any]] = []

    for item in items:
        source_key = _get_value(item, "source", "") or "未知来源"
        category_key = _get_value(item, "category", "") or "其他"
        if max_per_source and source_counts.get(source_key, 0) >= max_per_source:
            rejected_items.append({"item": item, "reason": f"同来源达到上限：{source_key}"})
            continue
        if max_per_category and category_counts.get(category_key, 0) >= max_per_category:
            rejected_items.append({"item": item, "reason": f"同类别达到上限：{category_key}"})
            continue
        selected_items.append(item)
        source_counts[source_key] = source_counts.get(source_key, 0) + 1
        category_counts[category_key] = category_counts.get(category_key, 0) + 1

    return selected_items, rejected_items


def build_review_report(
    fetcher: Any,
    selected_items: List[Any],
    remaining_items: List[Any],
    merged_out_items: List[Any],
    diversity_rejected_items: List[Dict[str, Any]],
    recent_topic_rejected_items: Optional[List[Dict[str, Any]]] = None,
    low_quality_rejected_items: Optional[List[Dict[str, Any]]] = None,
    rate_limit_skipped_items: Optional[List[Dict[str, Any]]] = None,
    source_observations: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """整理人工复核需要关注的候选池分区。"""
    filter_config = getattr(fetcher, "filter_config", {}) or {}
    min_quality_score = int(filter_config.get("min_quality_score", 3))
    high_score_threshold = int(filter_config.get("review_high_score_threshold", max(7, min_quality_score + 4)))
    borderline_threshold = int(filter_config.get("review_borderline_threshold", min_quality_score + 1))

    high_score_unselected = [_item for _item in remaining_items if int(_get_value(_item, "score", 0) or 0) >= high_score_threshold]
    borderline_items = [
        _item
        for _item in remaining_items
        if min_quality_score <= int(_get_value(_item, "score", 0) or 0) <= borderline_threshold
    ]

    return {
        "selected_items": selected_items,
        "remaining_items": remaining_items,
        "merged_out_items": merged_out_items,
        "diversity_rejected_items": diversity_rejected_items,
        "recent_topic_rejected_items": recent_topic_rejected_items or [],
        "low_quality_rejected_items": low_quality_rejected_items or [],
        "rate_limit_skipped_items": rate_limit_skipped_items or [],
        "high_score_unselected": high_score_unselected,
        "borderline_items": borderline_items,
        "source_observations": source_observations or [],
    }


def write_review_export(
    report: Dict[str, Any],
    export_dir: str,
    bot_type: str,
    report_title: str,
    date_label: Optional[str] = None,
) -> str:
    """输出人工复核 Markdown，方便每日抽查与回看。"""
    os.makedirs(export_dir, exist_ok=True)
    safe_date = date_label or datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(export_dir, f"{bot_type}_review_{safe_date}.md")

    content_lines = [
        f"# {report_title} ({safe_date})",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"候选总数：{_count_candidates(report)}",
        "",
    ]
    content_lines.extend(_render_section("已入选", report.get("selected_items", [])))
    content_lines.extend(_render_section("高分未入选", report.get("high_score_unselected", [])))
    content_lines.extend(_render_section("被多样性约束淘汰", report.get("diversity_rejected_items", []), with_reason=True))
    content_lines.extend(_render_section("被同事件合并淘汰", report.get("merged_out_items", [])))
    content_lines.extend(_render_section("被近 7 天主题去重淘汰", report.get("recent_topic_rejected_items", []), with_reason=True))
    content_lines.extend(_render_section("被质量闸门丢弃", report.get("low_quality_rejected_items", []), with_reason=True))
    content_lines.extend(_render_section("被 Dify 限流跳过", report.get("rate_limit_skipped_items", []), with_reason=True))
    content_lines.extend(_render_source_observation_section(report.get("source_observations", [])))
    content_lines.extend(_render_section("临界分内容", report.get("borderline_items", [])))

    with open(file_path, "w", encoding="utf-8") as file:
        file.write("\n".join(content_lines).strip() + "\n")
    return file_path


def _count_candidates(report: Dict[str, Any]) -> int:
    """统计复核池中的总候选数。"""
    return (
        len(report.get("selected_items", []))
        + len(report.get("remaining_items", []))
        + len(report.get("merged_out_items", []))
        + len(report.get("diversity_rejected_items", []))
        + len(report.get("recent_topic_rejected_items", []))
        + len(report.get("low_quality_rejected_items", []))
        + len(report.get("rate_limit_skipped_items", []))
    )


def _render_section(title: str, entries: List[Any], with_reason: bool = False) -> List[str]:
    """渲染一个复核分区。"""
    lines = [f"## {title}", ""]
    if not entries:
        lines.extend(["- 无", ""])
        return lines

    for index, entry in enumerate(entries, 1):
        item = entry.get("item") if with_reason else entry
        reason = entry.get("reason", "") if with_reason else ""
        lines.extend(_format_item_block(index, item, reason))
    lines.append("")
    return lines


def _format_item_block(index: int, item: Any, reason: str = "") -> List[str]:
    """格式化单条资讯，保留复核时最关键的信息。"""
    related_sources = "、".join(_get_value(item, "related_sources", []) or [])
    merged_count = int(_get_value(item, "merged_count", 1) or 1)
    summary = (_get_value(item, "summary", "") or "").replace("\n", " ").strip()
    if len(summary) > 120:
        summary = summary[:120] + "..."

    lines = [
        f"{index}. {_get_value(item, 'title', '')}",
        f"   来源：{_get_value(item, 'source', '') or '未知来源'} | 分类：{_get_value(item, 'category', '') or '其他'} | 评分：{_get_value(item, 'score', 0)}",
        f"   链接：{_get_value(item, 'link', '')}",
    ]
    if merged_count > 1:
        lines.append(f"   同事件合并：{merged_count} 篇 | 关联来源：{related_sources or '无'}")
    if reason:
        lines.append(f"   淘汰原因：{reason}")
    if summary:
        lines.append(f"   摘要：{summary}")
    return lines


def _render_source_observation_section(observations: List[Dict[str, Any]]) -> List[str]:
    """渲染信源降权观察区。"""
    lines = ["## 信源降权观察项", ""]
    if not observations:
        lines.extend(["- 无", ""])
        return lines

    for index, observation in enumerate(observations, 1):
        stats = observation.get("stats", {})
        reasons = "；".join(observation.get("reasons", []) or ["无"])
        adjustment = int(observation.get("adjustment", 0) or 0)
        lines.append(
            f"{index}. {observation.get('source', '')} | 动态调权：{adjustment:+d} | 候选：{stats.get('candidate_count', 0)} | 入选：{stats.get('selected_count', 0)}"
        )
        lines.append(
            f"   低质：{stats.get('low_quality_count', 0)} | 同事件合并：{stats.get('same_event_merged_count', 0)} | 近 7 天重复：{stats.get('recent_topic_duplicate_count', 0)}"
        )
        lines.append(f"   观察原因：{reasons}")
    lines.append("")
    return lines
