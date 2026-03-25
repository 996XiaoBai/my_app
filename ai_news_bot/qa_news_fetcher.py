import os
import requests
import logging
import re
from html import unescape
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
import aiohttp
import asyncio

# 尝试复用原有系统底层的逻辑
try:
    from ai_news_fetcher import AINewsFetcher, NewsItem
except ImportError:
    from .ai_news_fetcher import AINewsFetcher, NewsItem

logger = logging.getLogger(__name__)

class QANewsFetcher(AINewsFetcher):
    """
    专门针对测试效能、QA自动化垂直领域的资讯抓取器
    """
    def __init__(self, config_path: str = "config/qa_tools_config.yaml"):
        current_bot_dir = os.path.dirname(os.path.abspath(__file__))
        resolved_config_path = config_path
        if not os.path.isabs(resolved_config_path) and not os.path.exists(resolved_config_path):
            candidate_path = os.path.join(current_bot_dir, resolved_config_path)
            if os.path.exists(candidate_path):
                resolved_config_path = candidate_path

        # 复用 AINewsFetcher 的初始化（指定不同的配置文件）
        super().__init__(config_path=resolved_config_path)
        
        # 为了隔离避免与 ai news 打架，使用专属的去重缓存文件
        self.history_file = os.path.join(current_bot_dir, "data", "qa_sent_articles.json")
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        self.sent_history = self._load_sent_history()

    def _extract_scenario_tags(self, text: str) -> List[str]:
        """根据场景关键词为 QA 资讯打标签。"""
        scenario_keywords = self.filter_config.get("scenario_keywords", {}) or {}
        if not text or not isinstance(scenario_keywords, dict):
            return []

        text_lower = text.lower()
        matched_tags = []
        for tag, keywords in scenario_keywords.items():
            if isinstance(keywords, str):
                keywords = [keywords]
            if not isinstance(keywords, list):
                continue
            if any(self._matches_scenario_keyword_rule(keyword, text_lower) for keyword in keywords):
                matched_tags.append(str(tag))
        return matched_tags

    def _matches_scenario_keyword_rule(self, keyword_rule: Any, text_lower: str) -> bool:
        """场景关键词支持单词命中，也支持组合词同时命中。"""
        if not keyword_rule:
            return False

        if isinstance(keyword_rule, str):
            return keyword_rule.lower() in text_lower

        if isinstance(keyword_rule, (list, tuple)):
            normalized_parts = [str(part).lower() for part in keyword_rule if part]
            return bool(normalized_parts) and all(part in text_lower for part in normalized_parts)

        return False

    def _assign_scenario_tags(self, items: List[NewsItem]) -> List[NewsItem]:
        """统一为 QA 条目补充场景标签，覆盖 RSS/API 等不同来源。"""
        for item in items:
            merged_text = " ".join(
                part
                for part in [
                    getattr(item, "source", ""),
                    getattr(item, "original_title", ""),
                    getattr(item, "title", ""),
                    getattr(item, "summary", ""),
                    getattr(item, "content_text", ""),
                ]
                if part
            )
            extracted_tags = self._extract_scenario_tags(merged_text)
            existing_tags = list(getattr(item, "scenario_tags", []) or [])
            item.scenario_tags = list(dict.fromkeys(existing_tags + extracted_tags))
        return items

    def _parse_month_day_publish_time(self, raw_value: str) -> Optional[datetime]:
        """解析 Ministry of Testing 这类仅提供“日 月”格式的发布时间。"""
        value = " ".join(str(raw_value or "").split())
        if not value:
            return None

        current_time = datetime.now(timezone.utc)
        for time_format in ("%d %b", "%d %B", "%b %d", "%B %d"):
            try:
                candidate = datetime.strptime(
                    f"{value} {current_time.year}",
                    f"{time_format} %Y",
                ).replace(tzinfo=timezone.utc)
                if candidate - current_time > timedelta(days=2):
                    candidate = candidate.replace(year=current_time.year - 1)
                return candidate
            except ValueError:
                continue
        return self._parse_datetime_value(value)

    def _parse_named_month_date_with_year(self, raw_value: str) -> Optional[datetime]:
        """解析包含年份的英文月份日期，如 `Mar 17, 2026`。"""
        value = " ".join(str(raw_value or "").split())
        if not value:
            return None

        parsed_time = self._parse_datetime_value(value)
        if parsed_time:
            return parsed_time

        for time_format in ("%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(value, time_format).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _extract_nested_text(self, value: Any) -> str:
        """从嵌套 JSON/富文本结构中提取可读文本。"""
        parts: List[str] = []

        def _walk(node: Any) -> None:
            if node is None:
                return
            if isinstance(node, str):
                if node.strip():
                    parts.append(node.strip())
                return
            if isinstance(node, list):
                for item in node:
                    _walk(item)
                return
            if isinstance(node, dict):
                if isinstance(node.get("value"), str) and node.get("value", "").strip():
                    parts.append(node["value"].strip())
                for child in node.values():
                    _walk(child)

        _walk(value)
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    def _iter_nested_mappings(self, value: Any):
        """递归遍历任意嵌套结构中的字典节点。"""
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from self._iter_nested_mappings(child)
        elif isinstance(value, list):
            for item in value:
                yield from self._iter_nested_mappings(item)
        
    async def _fetch_testerhome(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """抓取 TesterHome 精选帖子"""
        items = []
        # type=excellent 抓精选，或者按默认最新抓
        url = source.get("url", "https://testerhome.com/api/v3/topics.json?limit=15&type=excellent")
        source_time_window_hours = source.get("time_window_hours")
        try:
            logger.info(f"正在抓取 {source['name']} ({url})...")
            async with session.get(url, timeout=15, ssl=False) as response:
                if response.status != 200:
                    logger.warning(f"  抓取失败 {source['name']}: 状态码 {response.status}")
                    return []
                data = await response.json()
                
            topics = data.get('topics', [])
            valid_count = 0
            
            for topic in topics:
                self.stats["total_fetched"] += 1
                title = topic.get('title', '')
                topic_id = topic.get('id')
                link = f"https://testerhome.com/topics/{topic_id}"
                publish_time = self._extract_publish_time_from_mapping(
                    topic,
                    fields=("created_at", "updated_at", "replied_at", "published_at"),
                )

                if self._is_title_excluded_by_patterns(title, source=source):
                    self.stats["blacklist_filtered"] += 1
                    continue
                
                # 时间过滤与缓存去重
                if not self._is_publish_time_within_window(
                    publish_time,
                    time_window_hours=source_time_window_hours,
                ):
                    self.stats["time_filtered"] += 1
                    continue
                if self._is_in_sent_history(link, title):
                    self.stats["history_filtered"] += 1
                    continue
                
                # 关键词过滤逻辑
                summary = topic.get('body', '') or topic.get('excerpt', '') or title
                relevance_text = f"{title} {summary}"
                is_valid, reject_reason = self._is_relevant_with_reason(relevance_text, source=source)
                if not is_valid:
                    if reject_reason == "blacklist":
                        self.stats["blacklist_filtered"] += 1
                    elif reject_reason == "no_whitelist":
                        self.stats["miss_whitelist"] += 1
                    continue
                    
                self.stats["hit_whitelist"] += 1
                
                # TesterHome 能拿到正文片段时优先用片段，拿不到再退回标题
                item = NewsItem(
                    title=title,
                    link=link,
                    published=(publish_time.isoformat() if publish_time else datetime.now(timezone.utc).isoformat()),
                    source=source["name"],
                    summary=summary[:200],
                    cover_image_url="",
                    source_priority=source.get("priority", 99),
                    published_at=publish_time,
                    original_title=title,
                    scenario_tags=self._extract_scenario_tags(f"{title} {summary}"),
                )
                items.append(item)
                valid_count += 1
                
            logger.info(f"  -> 从 {source['name']} 中筛选出 {valid_count} 条相关资讯。")
            self._source_fail_counts[source['name']] = 0
            return items

        except Exception as e:
            logger.error(f"从 {source['name']} 抓取时出错: {e}")
            return []

    async def _fetch_juejin(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """抓取掘金站内热门实战文章"""
        items = []
        url = "https://api.juejin.cn/search_api/v1/search"
        source_time_window_hours = source.get("time_window_hours")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # 从 source 配置里读取专属参数，例如 {"keyword": "自动化测试"}
        keyword = source.get("keyword", "测试开发")
        payload = {
            "key_word": keyword,
            "id_type": 0,
            "cursor": "0",
            "limit": 20,
            "search_type": 0,
            "sort_type": 2 # 2=按最新, 3=按最热综合
        }
        
        try:
            logger.info(f"正在通过 API 抓取 {source['name']} (关键词: {keyword})...")
            async with session.post(url, headers=headers, json=payload, timeout=15, ssl=False) as response:
                if response.status != 200:
                    logger.warning(f"  抓取失败 {source['name']}: 状态码 {response.status}")
                    return []
                data = await response.json()
            
            results = data.get('data', [])
            valid_count = 0
            
            for index_item in results:
                self.stats["total_fetched"] += 1
                result_model = index_item.get('result_model', {})
                article = result_model.get('article_info', {})
                if not article:
                    continue
                    
                title = article.get('title', '')
                article_id = article.get('article_id', '')
                brief = article.get('brief_content', '')
                link = f"https://juejin.cn/post/{article_id}"
                cover_image_url = article.get('cover_image', '')
                publish_time = self._extract_publish_time_from_mapping(
                    article,
                    fields=("ctime", "mtime", "updated_at", "created_at", "published_at"),
                )
                
                # 时间与缓存过滤
                if not self._is_publish_time_within_window(
                    publish_time,
                    time_window_hours=source_time_window_hours,
                ):
                    self.stats["time_filtered"] += 1
                    continue
                if self._is_in_sent_history(link, title):
                    self.stats["history_filtered"] += 1
                    continue
                
                full_text = f"{title} {brief}"
                is_valid, reject_reason = self._is_relevant_with_reason(full_text, source=source)
                if not is_valid:
                    continue
                    
                self.stats["hit_whitelist"] += 1
                
                # 构造标准模型
                item = NewsItem(
                    title=title,
                    link=link,
                    published=(publish_time.isoformat() if publish_time else datetime.now(timezone.utc).isoformat()),
                    source=f"掘金 ({keyword})",
                    summary=brief[:200],
                    cover_image_url=cover_image_url,
                    source_priority=source.get("priority", 99),
                    published_at=publish_time,
                    original_title=title,
                    scenario_tags=self._extract_scenario_tags(full_text),
                )
                items.append(item)
                valid_count += 1
                
            logger.info(f"  -> 从 {source['name']} 中筛选出 {valid_count} 条相关资讯。")
            self._source_fail_counts[source['name']] = 0
            return items

        except Exception as e:
            logger.error(f"从 {source['name']} 抓取时出错: {e}")
            return []

    async def _fetch_testmu_blog_html(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """抓取 TestMu AI（原 LambdaTest）博客首页的卡片内容。"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        items = []
        source_time_window_hours = source.get("time_window_hours")
        try:
            logger.info(f"正在抓取 {source['name']} ({source['url']})...")
            async with session.get(source["url"], headers=headers, timeout=15, ssl=False) as response:
                if response.status != 200:
                    logger.warning(f"  抓取失败 {source['name']}: 状态码 {response.status}")
                    return []
                html = await response.text()

            card_pattern = re.compile(
                r"(?P<categories>(?:<a href=\"https://www\.testmuai\.com/blog/category/[^\"#?]+/?\"[^>]*>.*?</a>\s*(?:<span[^>]*>.*?</span>\s*)*)*)"
                r"<a href=\"(?P<link>(?:https://www\.testmuai\.com)?/blog/[^\"#?]+/? )\"[^>]*class=\"[^\"]*(?:text-size-24|text-size-20|text-size-18)[^\"]*\"[^>]*>(?P<title>.*?)</a>"
                r"\s*<p class=\"[^\"]*\">(?P<summary>.*?)</p>"
                r"(?P<metadata>.*?)"
                r"<p class=\"[^\"]*\">(?P<published>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4})</p>",
                re.IGNORECASE | re.DOTALL,
            )
            # 修正正则中的可选空格，避免误把链接尾部空格吃进来
            card_pattern = re.compile(card_pattern.pattern.replace("/? )", "/?)"), re.IGNORECASE | re.DOTALL)

            seen_links = set()
            valid_count = 0
            for match in card_pattern.finditer(html):
                raw_link = unescape(match.group("link")).strip()
                link = raw_link if raw_link.startswith("http") else f"https://www.testmuai.com{raw_link}"
                if link in seen_links:
                    continue
                seen_links.add(link)

                self.stats["total_fetched"] += 1

                title = re.sub(
                    r"\s+",
                    " ",
                    self._extract_readable_text_from_html(match.group("title")) or unescape(match.group("title")),
                ).strip()
                summary = re.sub(
                    r"\s+",
                    " ",
                    self._extract_readable_text_from_html(match.group("summary")) or unescape(match.group("summary")),
                ).strip()
                categories = re.sub(
                    r"\s+",
                    " ",
                    self._extract_readable_text_from_html(match.group("categories")),
                ).strip()
                published_text = re.sub(r"\s+", " ", match.group("published")).strip()
                publish_time = self._parse_named_month_date_with_year(published_text)

                if not title or self._is_title_excluded_by_patterns(title, source=source):
                    self.stats["blacklist_filtered"] += 1
                    continue
                if not self._is_publish_time_within_window(
                    publish_time,
                    time_window_hours=source_time_window_hours,
                ):
                    self.stats["time_filtered"] += 1
                    continue
                if self._is_in_sent_history(link, title):
                    self.stats["history_filtered"] += 1
                    continue

                full_text = " ".join(
                    part
                    for part in [
                        source.get("name", ""),
                        categories,
                        title,
                        summary,
                    ]
                    if part
                )
                is_valid, reject_reason = self._is_relevant_with_reason(full_text, source=source)
                if not is_valid:
                    if reject_reason == "blacklist":
                        self.stats["blacklist_filtered"] += 1
                    elif reject_reason == "no_whitelist":
                        self.stats["miss_whitelist"] += 1
                    continue

                self.stats["hit_whitelist"] += 1
                item = NewsItem(
                    title=title,
                    link=link,
                    published=(publish_time.isoformat() if publish_time else published_text or datetime.now(timezone.utc).isoformat()),
                    source=source["name"],
                    summary=summary[:200],
                    cover_image_url="",
                    source_priority=source.get("priority", 99),
                    published_at=publish_time,
                    original_title=title,
                    scenario_tags=self._extract_scenario_tags(f"{categories} {title} {summary}"),
                )
                items.append(item)
                valid_count += 1

            logger.info(f"  -> 从 {source['name']} 中筛选出 {valid_count} 条相关资讯。")
            self._source_fail_counts[source['name']] = 0
            return items
        except Exception as e:
            logger.error(f"从 {source['name']} 抓取时出错: {e}")
            return []

    async def _fetch_saucelabs_next_data_json(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """抓取 Sauce Labs Next.js 数据接口中的博客条目。"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        items = []
        source_time_window_hours = source.get("time_window_hours")
        link_prefix = source.get("link_prefix", "https://saucelabs.com/resources/blog/")
        try:
            logger.info(f"正在抓取 {source['name']} ({source['url']})...")
            async with session.get(source["url"], headers=headers, timeout=15, ssl=False) as response:
                if response.status != 200:
                    logger.warning(f"  抓取失败 {source['name']}: 状态码 {response.status}")
                    return []
                data = await response.json()

            seen_slugs = set()
            valid_count = 0
            for mapping in self._iter_nested_mappings(data):
                fields = mapping.get("fields")
                if not isinstance(fields, dict):
                    continue
                if str(fields.get("feedType", "")).lower() != "blog":
                    continue

                title = str(fields.get("title", "") or "").strip()
                slug = str(fields.get("slug", "") or "").strip().strip("/")
                if not title or not slug or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)

                self.stats["total_fetched"] += 1

                link = f"{link_prefix.rstrip('/')}/{slug}"
                publish_time = self._extract_publish_time_from_mapping(
                    mapping.get("sys", {}) if isinstance(mapping.get("sys"), dict) else {},
                    fields=("updatedAt", "createdAt"),
                )
                if not publish_time:
                    publish_time = self._extract_publish_time_from_mapping(
                        fields,
                        fields=("publishedAt", "publicationDate", "publishDate", "updatedAt", "createdAt"),
                    )

                if self._is_title_excluded_by_patterns(title, source=source):
                    self.stats["blacklist_filtered"] += 1
                    continue
                if not self._is_publish_time_within_window(
                    publish_time,
                    time_window_hours=source_time_window_hours,
                ):
                    self.stats["time_filtered"] += 1
                    continue
                if self._is_in_sent_history(link, title):
                    self.stats["history_filtered"] += 1
                    continue

                summary = (
                    str(fields.get("excerpt", "") or "").strip()
                    or self._extract_nested_text(fields.get("description"))
                    or title
                )
                full_text = " ".join(
                    part
                    for part in [
                        source.get("name", ""),
                        title,
                        summary,
                    ]
                    if part
                )
                is_valid, reject_reason = self._is_relevant_with_reason(full_text, source=source)
                if not is_valid:
                    if reject_reason == "blacklist":
                        self.stats["blacklist_filtered"] += 1
                    elif reject_reason == "no_whitelist":
                        self.stats["miss_whitelist"] += 1
                    continue

                self.stats["hit_whitelist"] += 1
                item = NewsItem(
                    title=title,
                    link=link,
                    published=(publish_time.isoformat() if publish_time else datetime.now(timezone.utc).isoformat()),
                    source=source["name"],
                    summary=summary[:200],
                    cover_image_url="",
                    source_priority=source.get("priority", 99),
                    published_at=publish_time,
                    original_title=title,
                    scenario_tags=self._extract_scenario_tags(f"{title} {summary}"),
                )
                items.append(item)
                valid_count += 1

            logger.info(f"  -> 从 {source['name']} 中筛选出 {valid_count} 条相关资讯。")
            self._source_fail_counts[source['name']] = 0
            return items
        except Exception as e:
            logger.error(f"从 {source['name']} 抓取时出错: {e}")
            return []

    async def _fetch_mot_news_html(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """抓取 Ministry of Testing 的测试自动化聚合页。"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        items = []
        source_time_window_hours = source.get("time_window_hours")
        try:
            logger.info(f"正在抓取 {source['name']} ({source['url']})...")
            async with session.get(source["url"], headers=headers, timeout=15, ssl=False) as response:
                if response.status != 200:
                    logger.warning(f"  抓取失败 {source['name']}: 状态码 {response.status}")
                    return []
                html = await response.text()

            card_pattern = re.compile(
                r"<div class='card shadow summary-card'>(?P<card>.*?)"
                r'<a target="_blank" class="stretched-link text-black" href="(?P<link>[^"]+)">(?P<title>.*?)</a>'
                r"(?P<after_title>.*?)<div class='summary'>\s*Source:\s*(?P<source_label>.*?)\s*</div>"
                r"(?P<footer>.*?)<div class='published fs-6'>\s*(?P<published>.*?)\s*</div>",
                re.IGNORECASE | re.DOTALL,
            )

            valid_count = 0
            for match in card_pattern.finditer(html):
                self.stats["total_fetched"] += 1

                title = self._extract_readable_text_from_html(match.group("title"))
                if not title:
                    title = unescape(match.group("title")).strip()
                title = re.sub(r"\s+", " ", title).strip()
                link = unescape(match.group("link")).strip()
                source_label = re.sub(
                    r"\s+",
                    " ",
                    self._extract_readable_text_from_html(match.group("source_label")),
                ).strip()
                published_text = re.sub(
                    r"\s+",
                    " ",
                    self._extract_readable_text_from_html(match.group("published")),
                ).strip()
                publish_time = self._parse_month_day_publish_time(published_text)

                if not self._is_publish_time_within_window(
                    publish_time,
                    time_window_hours=source_time_window_hours,
                ):
                    self.stats["time_filtered"] += 1
                    continue
                if self._is_in_sent_history(link, title):
                    self.stats["history_filtered"] += 1
                    continue

                summary = f"来源: {source_label}" if source_label else ""
                full_text = " ".join(
                    part
                    for part in [
                        source.get("name", ""),
                        title,
                        summary,
                    ]
                    if part
                )
                is_valid, reject_reason = self._is_relevant_with_reason(full_text, source=source)
                if not is_valid:
                    if reject_reason == "blacklist":
                        self.stats["blacklist_filtered"] += 1
                    elif reject_reason == "no_whitelist":
                        self.stats["miss_whitelist"] += 1
                    continue

                self.stats["hit_whitelist"] += 1
                item = NewsItem(
                    title=title,
                    link=link,
                    published=(publish_time.isoformat() if publish_time else published_text or datetime.now(timezone.utc).isoformat()),
                    source=source["name"],
                    summary=summary[:200],
                    cover_image_url="",
                    source_priority=source.get("priority", 99),
                    published_at=publish_time,
                    original_title=title,
                    scenario_tags=self._extract_scenario_tags(f"{title} {summary}"),
                )
                items.append(item)
                valid_count += 1

            logger.info(f"  -> 从 {source['name']} 中筛选出 {valid_count} 条相关资讯。")
            self._source_fail_counts[source['name']] = 0
            return items
        except Exception as e:
            logger.error(f"从 {source['name']} 抓取时出错: {e}")
            return []

    async def _fetch_zendesk_help_center_api(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """抓取 Zendesk Help Center API，筛选高价值的测试工具更新。"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        items = []
        source_time_window_hours = source.get("time_window_hours")
        try:
            logger.info(f"正在抓取 {source['name']} ({source['url']})...")
            async with session.get(source["url"], headers=headers, timeout=15, ssl=False) as response:
                if response.status != 200:
                    logger.warning(f"  抓取失败 {source['name']}: 状态码 {response.status}")
                    return []
                data = await response.json()

            articles = data.get("articles", [])
            valid_count = 0
            for article in articles[:30]:
                title = article.get("title") or article.get("name") or ""
                link = article.get("html_url") or article.get("url") or ""
                if not title or not link:
                    continue

                self.stats["total_fetched"] += 1
                publish_time = self._extract_publish_time_from_mapping(
                    article,
                    fields=("updated_at", "edited_at", "created_at"),
                )
                if not self._is_publish_time_within_window(
                    publish_time,
                    time_window_hours=source_time_window_hours,
                ):
                    self.stats["time_filtered"] += 1
                    continue
                if self._is_in_sent_history(link, title):
                    self.stats["history_filtered"] += 1
                    continue

                labels = " ".join(str(label) for label in article.get("label_names", []) if label)
                body_text = self._extract_readable_text_from_html(article.get("body", ""))
                full_text = " ".join(
                    part
                    for part in [
                        source.get("name", ""),
                        title,
                        labels,
                        body_text,
                    ]
                    if part
                )
                is_valid, reject_reason = self._is_relevant_with_reason(full_text, source=source)
                if not is_valid:
                    if reject_reason == "blacklist":
                        self.stats["blacklist_filtered"] += 1
                    elif reject_reason == "no_whitelist":
                        self.stats["miss_whitelist"] += 1
                    continue

                self.stats["hit_whitelist"] += 1
                summary_parts = []
                if labels:
                    summary_parts.append(f"标签: {labels}")
                if body_text:
                    summary_parts.append(body_text[:160])
                summary = " | ".join(summary_parts)
                item = NewsItem(
                    title=title,
                    link=link,
                    published=(publish_time.isoformat() if publish_time else datetime.now(timezone.utc).isoformat()),
                    source=source["name"],
                    summary=summary[:200],
                    cover_image_url="",
                    source_priority=source.get("priority", 99),
                    published_at=publish_time,
                    original_title=title,
                    scenario_tags=self._extract_scenario_tags(f"{title} {labels} {body_text}"),
                )
                items.append(item)
                valid_count += 1

            logger.info(f"  -> 从 {source['name']} 中筛选出 {valid_count} 条相关资讯。")
            self._source_fail_counts[source['name']] = 0
            return items
        except Exception as e:
            logger.error(f"从 {source['name']} 抓取时出错: {e}")
            return []

    async def _fetch_source(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """重写底层分发逻辑，支持自定义的 API Type"""
        source_type = source.get("type", "rss")
        
        # 处理非标数据源
        if source_type == "testerhome_api":
            items = await self._fetch_testerhome(session, source)
            return self._assign_scenario_tags(items)
        elif source_type == "juejin_api":
            items = await self._fetch_juejin(session, source)
            return self._assign_scenario_tags(items)
        elif source_type == "mot_news_html":
            items = await self._fetch_mot_news_html(session, source)
            return self._assign_scenario_tags(items)
        elif source_type == "zendesk_help_center_api":
            items = await self._fetch_zendesk_help_center_api(session, source)
            return self._assign_scenario_tags(items)
        elif source_type == "testmu_blog_html":
            items = await self._fetch_testmu_blog_html(session, source)
            return self._assign_scenario_tags(items)
        elif source_type == "saucelabs_next_data_json":
            items = await self._fetch_saucelabs_next_data_json(session, source)
            return self._assign_scenario_tags(items)
        
        # 如果是 RSS 源（如微信公众号的 RSSHub），走父类的原逻辑即可
        items = await super()._fetch_source(session, source)
        return self._assign_scenario_tags(items)
