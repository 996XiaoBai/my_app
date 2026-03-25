import feedparser
import time
import ssl
import yaml
import os
import requests
import asyncio
import aiohttp
import logging
import json
import hashlib
import re
from html import unescape
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# 修复 SSL 证书验证失败的问题
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

logger = logging.getLogger(__name__)

@dataclass
class NewsItem:
    title: str
    link: str
    published: str
    source: str
    summary: str = ""
    highlights: str = ""
    cover_image_url: str = ""
    category: str = ""
    score: int = 0
    source_priority: int = 99
    published_at: Optional[datetime] = None
    original_title: str = ""
    score_breakdown: Dict[str, int] = field(default_factory=dict)
    content_text: str = ""
    related_sources: List[str] = field(default_factory=list)
    merged_count: int = 1
    scenario_tags: List[str] = field(default_factory=list)

class AINewsFetcher:
    def __init__(self, config_path: str = "services/ai_news_bot/config/news_config.yaml"):
        self.config = self._load_config(config_path)
        self.sources = self.config.get("news_sources", [])
        self.filter_config = self.config.get("filter", {})
        # 追踪每个信源的连续失败次数，用于健康监控
        self._source_fail_counts: Dict[str, int] = {}
        
        # 统计指标埋点
        self.stats = {
            "total_fetched": 0,
            "time_filtered": 0,
            "blacklist_filtered": 0,
            "miss_whitelist": 0,
            "hit_whitelist": 0,
            "history_filtered": 0  # 新增：持久化历史过滤统计
        }
        
        # 持久化去重数据初始化
        current_bot_dir = os.path.dirname(os.path.abspath(__file__))
        self.history_file = os.path.join(current_bot_dir, "data", "sent_articles.json")
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        self.sent_history = self._load_sent_history()
        
        # 默认回退源
        if not self.sources:
            self.sources = [
                {"name": "Hacker News (AI)", "url": "https://hnrss.org/newest?q=AI+OR+Artificial+Intelligence&points=10", "type": "rss"}
            ]

    def _load_config(self, path: str) -> Dict[str, Any]:
        """加载配置文件，支持绝对路径或相对路径"""
        if not os.path.exists(path):
            current_dir = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(current_dir, "config", "news_config.yaml")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"从 {path} 加载配置出错: {e}")
            return {}

    def _normalize_link(self, link: str) -> str:
        """对链接做轻量归一化，去掉常见追踪参数。"""
        if not link:
            return ""

        parts = urlsplit(link.strip())
        scheme = (parts.scheme or "https").lower()
        netloc = parts.netloc.lower()
        path = parts.path.rstrip("/") or parts.path or "/"

        tracking_params = {
            "fbclid",
            "gclid",
            "igshid",
            "mc_cid",
            "mc_eid",
            "spm",
        }
        query_items = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            lowered_key = key.lower()
            if lowered_key.startswith("utm_") or lowered_key in tracking_params:
                continue
            query_items.append((key, value))
        normalized_query = urlencode(sorted(query_items))
        return urlunsplit((scheme, netloc, path, normalized_query, ""))

    def _normalize_title(self, title: str) -> str:
        """将标题规整为适合做指纹的形式。"""
        if not title:
            return ""
        lowered_title = title.strip().lower()
        compact_title = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", lowered_title)
        return compact_title

    def _build_title_fingerprint(self, title: str) -> str:
        """为标题生成稳定指纹，用于跨链接去重。"""
        normalized_title = self._normalize_title(title)
        if not normalized_title:
            return ""
        digest = hashlib.sha1(normalized_title.encode("utf-8")).hexdigest()
        return digest[:16]

    def _build_identity_keys(self, link: str = "", title: str = "") -> List[str]:
        """为一条资讯生成用于去重的多个标识。"""
        identity_keys: List[str] = []
        normalized_link = self._normalize_link(link)
        if normalized_link:
            identity_keys.append(f"url:{normalized_link}")
        title_fingerprint = self._build_title_fingerprint(title)
        if title_fingerprint:
            identity_keys.append(f"title:{title_fingerprint}")
        return identity_keys

    def _history_entry_to_keys(self, entry: Any) -> List[str]:
        """兼容旧历史格式与新历史标识。"""
        if isinstance(entry, str):
            if entry.startswith("url:") or entry.startswith("title:"):
                return [entry]
            return self._build_identity_keys(link=entry)
        if isinstance(entry, dict):
            return self._build_identity_keys(link=entry.get("link", ""), title=entry.get("title", ""))
        return []

    def _load_sent_history(self) -> List[str]:
        """加载已发送文章的历史记录"""
        if not os.path.exists(self.history_file):
            return []
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []

                normalized_history: List[str] = []
                seen_keys = set()
                for entry in data:
                    for key in self._history_entry_to_keys(entry):
                        if key and key not in seen_keys:
                            seen_keys.add(key)
                            normalized_history.append(key)
                return normalized_history
        except Exception as e:
            logger.error(f"加载历史去重文件失败: {e}")
            return []

    def _is_in_sent_history(self, link: str, title: str = "") -> bool:
        """检查文章是否已在历史记录中出现。"""
        if not self.sent_history:
            return False
        history_set = set(self.sent_history)
        for key in self._build_identity_keys(link=link, title=title):
            if key in history_set:
                return True
        return False

    def save_to_history(self, items_or_links: List[Any]):
        """保存新发布内容到历史记录，并保持文件瘦身。"""
        current_history = self._load_sent_history()
        new_history_keys: List[str] = []
        for item in items_or_links:
            if isinstance(item, NewsItem):
                source_title = item.original_title or item.title
                new_history_keys.extend(self._build_identity_keys(link=item.link, title=source_title))
            elif isinstance(item, str):
                new_history_keys.extend(self._build_identity_keys(link=item))

        # 将新标识合并（去重），新发布的排在前面
        updated_history = list(dict.fromkeys(new_history_keys + current_history))
        
        # 自动瘦身：仅保留最近 1500 条记录（约覆盖一个月的推送量）
        max_history = 1500
        if len(updated_history) > max_history:
            updated_history = updated_history[:max_history]
            
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(updated_history, f, ensure_ascii=False, indent=2)
            self.sent_history = updated_history
            logger.info(f"成功更新去重历史记录，当前记录总数: {len(updated_history)}")
        except Exception as e:
            logger.error(f"保存历史去重文件失败: {e}")

    def _is_relevant_with_reason(self, text: str, source: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
        """根据关键词过滤内容，并返回 (是否通过, 拒绝原因)。"""
        if not text:
            return False, "empty_text"
            
        text_lower = text.lower()
        
        # 1. 检查排除词 (黑名单)
        exclude_keywords = list(self.filter_config.get("exclude_keywords", []) or [])
        if source:
            exclude_keywords.extend(source.get("exclude_keywords", []) or [])
        for kw in exclude_keywords:
            if kw.lower() in text_lower:
                return False, "blacklist"

        # 2. 检查信源级强约束词，适合对厂商博客做进一步收口
        required_keywords = []
        if source:
            required_keywords = list(source.get("require_keywords", []) or [])
        has_required_keyword = False
        if required_keywords:
            has_required_keyword = any(
                self._matches_keyword_rule(keyword, text_lower)
                for keyword in required_keywords
            )
            if not has_required_keyword:
                return False, "missing_required_keywords"
                
        # 3. 检查包含词 (白名单，只要命中一个即可)
        include_keywords = list(self.filter_config.get("keywords", []) or [])
        if source:
            include_keywords.extend(source.get("include_keywords", []) or [])
        if not include_keywords:
            return True, "no_whitelist_config" # 如果没有配置关键词，默认不过滤
            
        for kw in include_keywords:
            if kw.lower() in text_lower:
                return True, "whitelist_hit"

        if has_required_keyword:
            return True, "whitelist_hit"
                
        return False, "no_whitelist"

    def _matches_keyword_rule(self, keyword_rule: Any, text_lower: str) -> bool:
        """关键词规则支持单词命中，也支持组合词同时命中。"""
        if not keyword_rule:
            return False

        if isinstance(keyword_rule, str):
            return keyword_rule.lower() in text_lower

        if isinstance(keyword_rule, (list, tuple)):
            normalized_parts = [str(part).lower() for part in keyword_rule if part]
            return bool(normalized_parts) and all(part in text_lower for part in normalized_parts)

        return False

    def _is_relevant(self, text: str, source: Optional[Dict[str, Any]] = None) -> bool:
        """根据关键词过滤内容（兼容原方法签名）"""
        is_valid, _ = self._is_relevant_with_reason(text, source=source)
        return is_valid

    def _is_title_excluded_by_patterns(self, title: str, source: Optional[Dict[str, Any]] = None) -> bool:
        """按信源配置的标题正则排除低价值噪音条目。"""
        if not title or not source:
            return False

        patterns = list(source.get("exclude_title_patterns", []) or [])
        if not patterns:
            return False

        for pattern in patterns:
            normalized_pattern = str(pattern).lower()
            if self.filter_config.get("allow_prerelease_titles", False) and any(
                marker in normalized_pattern
                for marker in ("nightly", "rc", "alpha", "beta", "preview", "pre-release", "snapshot")
            ):
                continue
            try:
                if re.search(str(pattern), title, flags=re.IGNORECASE):
                    return True
            except re.error as exc:
                logger.warning(f"信源 {source.get('name', '未知来源')} 的标题排除正则无效: {pattern} ({exc})")
        return False

    def _parse_publish_time(self, entry) -> Optional[datetime]:
        """从 feed entry 中解析发布时间，返回 UTC 时间（无时区信息则假定为 UTC）"""
        for field in ("published", "updated", "created"):
            raw = entry.get(field, "")
            if not raw:
                continue
            publish_time = self._parse_datetime_value(raw)
            if publish_time:
                return publish_time
        return None

    def _parse_datetime_value(self, raw: Any) -> Optional[datetime]:
        """解析多种外部时间格式，统一返回 UTC 时间"""
        if raw in (None, ""):
            return None

        dt: Optional[datetime] = None
        if isinstance(raw, datetime):
            dt = raw
        elif isinstance(raw, (int, float)):
            timestamp = float(raw)
            if timestamp > 10**12:
                timestamp /= 1000
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        elif isinstance(raw, str):
            value = raw.strip()
            if not value:
                return None

            if value.isdigit():
                return self._parse_datetime_value(int(value))

            try:
                dt = parsedate_to_datetime(value)
            except Exception:
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except Exception:
                    return None
        else:
            return None

        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _extract_publish_time_from_mapping(
        self,
        entry: Dict[str, Any],
        fields: Tuple[str, ...] = (
            "published",
            "updated",
            "created",
            "publish_time",
            "published_at",
            "created_at",
            "pub_time",
            "ctime",
            "mtime",
            "timestamp",
            "date",
        ),
    ) -> Optional[datetime]:
        """从常见 API 字段中抽取发布时间"""
        for field in fields:
            if field not in entry:
                continue
            publish_time = self._parse_datetime_value(entry.get(field))
            if publish_time:
                return publish_time
        return None

    def _is_publish_time_within_window(
        self,
        publish_time: Optional[datetime],
        time_window_hours: Optional[int] = None,
    ) -> bool:
        """基于解析后的时间判断是否在窗口内，允许单源覆盖默认时间窗口。"""
        effective_time_window_hours = (
            self.filter_config.get("time_window_hours", 0)
            if time_window_hours is None
            else time_window_hours
        )
        if not effective_time_window_hours or not publish_time:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(hours=int(effective_time_window_hours))
        return publish_time >= cutoff

    def _get_candidate_pool_limit(self, publish_limit: int) -> int:
        """为后续质量排序保留更大的候选池"""
        configured_limit = self.filter_config.get("candidate_pool_limit")
        if configured_limit:
            return max(publish_limit, int(configured_limit))

        multiplier = int(self.filter_config.get("candidate_pool_multiplier", 1))
        return max(publish_limit, publish_limit * max(1, multiplier))

    def _extract_readable_text_from_html(self, html: str) -> str:
        """从 HTML 中提取相对可读的正文文本。"""
        if not html:
            return ""

        cleaned_html = re.sub(r"(?is)<(script|style|noscript|svg|canvas).*?>.*?</\1>", " ", html)
        cleaned_html = re.sub(r"(?is)<(nav|footer|header|aside|form).*?>.*?</\1>", " ", cleaned_html)

        main_match = re.search(r"(?is)<(article|main)[^>]*>(.*?)</\1>", cleaned_html)
        if main_match:
            cleaned_html = main_match.group(2)
        else:
            body_match = re.search(r"(?is)<body[^>]*>(.*?)</body>", cleaned_html)
            if body_match:
                cleaned_html = body_match.group(1)

        text = re.sub(r"(?is)<br\s*/?>", "\n", cleaned_html)
        text = re.sub(r"(?is)</p>|</div>|</li>|</section>|</h[1-6]>", "\n", text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        text = unescape(text)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n", text)

        filtered_lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if len(line) <= 2:
                continue
            if any(noise in line for noise in ("登录", "注册", "版权", "上一篇", "下一篇")):
                continue
            filtered_lines.append(line)
        return "\n".join(filtered_lines).strip()

    async def _fetch_full_content_for_item(
        self,
        session: aiohttp.ClientSession,
        item: NewsItem,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """抓取单篇文章正文，失败时静默回退。"""
        if not item.link or getattr(item, "content_text", ""):
            return

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        async with semaphore:
            try:
                async with session.get(item.link, headers=headers, timeout=15, ssl=False) as response:
                    if response.status != 200:
                        return
                    content_type = response.headers.get("Content-Type", "")
                    if "html" not in content_type and content_type:
                        return
                    html = await response.text()
            except Exception:
                return

        extracted_text = self._extract_readable_text_from_html(html)
        if extracted_text:
            max_chars = int(self.filter_config.get("full_content_max_chars", 4000))
            item.content_text = extracted_text[:max_chars]

    async def enrich_items_with_full_content_async(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """为候选资讯补抓正文，提升后续质量判断准确性。"""
        if not news_items:
            return news_items

        fetch_limit = int(self.filter_config.get("content_fetch_limit", len(news_items)))
        target_items = news_items[: max(0, fetch_limit)]
        if not target_items:
            return news_items

        concurrency = max(1, int(self.filter_config.get("content_fetch_concurrency", 4)))
        semaphore = asyncio.Semaphore(concurrency)
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_full_content_for_item(session, item, semaphore) for item in target_items]
            await asyncio.gather(*tasks)
        return news_items

    def _is_within_time_window(self, entry, time_window_hours: Optional[int] = None) -> bool:
        """检查文章是否在时间窗口内，允许单源覆盖默认时间窗口。"""
        publish_time = self._parse_publish_time(entry)
        return self._is_publish_time_within_window(
            publish_time,
            time_window_hours=time_window_hours,
        )

    async def _fetch_source(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """异步获取单个源的新闻，支持 RSS、HTML 和 API 类型"""
        source_type = source.get("type", "rss")
        if source_type == "rss":
            return await self._fetch_rss_source(session, source)
        elif source_type == "html":
            return await self._fetch_html_source(session, source)
        elif source_type == "api":
            return await self._fetch_api_source(session, source)
        else:
            logger.warning(f"不支持的信源类型: {source_type} ({source['name']})")
            return []

    async def _fetch_rss_source(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """原有的 RSS 抓取逻辑"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        items = []
        try:
            logger.info(f"正在抓取 RSS: {source['name']} ({source['url']})...")
            try:
                async with session.get(source["url"], headers=headers, timeout=15, ssl=False) as response:
                    if response.status != 200:
                        logger.warning(f"  抓取失败 {source['name']}: 状态码 {response.status}")
                        return []
                    content = await response.text()
            except Exception as req_err:
                logger.warning(f"  网络错误 {source['name']}: {req_err}")
                return []

            # 解析 Feed
            feed = feedparser.parse(content)
            
            if not feed.entries:
                logger.warning(f"  未在 {source['name']} 中发现任何文章")
                return []

            # 预筛选
            entries_to_check = feed.entries[:30] # 每次最多检查 30 条来找符合条件的
            
            valid_count = 0
            time_filtered = 0
            blacklist_filtered = 0
            source_time_window_hours = source.get("time_window_hours")
            
            for entry in entries_to_check:
                self.stats["total_fetched"] += 1
                title = entry.title
                summary = entry.get("summary", "")

                if self._is_title_excluded_by_patterns(title, source=source):
                    blacklist_filtered += 1
                    self.stats["blacklist_filtered"] += 1
                    continue
                
                # 时间窗口过滤
                if not self._is_within_time_window(entry, time_window_hours=source_time_window_hours):
                    time_filtered += 1
                    self.stats["time_filtered"] += 1
                    continue
                
                # 持久化历史过滤 (跨次去重核心拦截)
                if self._is_in_sent_history(entry.link, title):
                    self.stats["history_filtered"] += 1
                    continue
                
                full_text = f"{source.get('name', '')} {title} {summary}"
                
                # 关键词与黑名单过滤，增加原因记录
                is_valid, reject_reason = self._is_relevant_with_reason(full_text, source=source)
                if not is_valid:
                    if reject_reason == "blacklist":
                        blacklist_filtered += 1
                        self.stats["blacklist_filtered"] += 1
                    elif reject_reason == "no_whitelist":
                        self.stats["miss_whitelist"] += 1
                    continue
                    
                self.stats["hit_whitelist"] += 1
                    
                # 尝试提取文章的首图链接
                cover_image_url = ""
                # 1. 尝试从 media_content 找
                if "media_content" in entry and isinstance(entry.media_content, list) and len(entry.media_content) > 0:
                    cover_image_url = entry.media_content[0].get("url", "")
                
                # 2. 如果没有，则尝试从 summary 或 content 中提取 <img src="...">
                if not cover_image_url:
                    import re
                    content_html = summary
                    if "content" in entry and isinstance(entry.content, list) and len(entry.content) > 0:
                        content_html += " " + entry.content[0].get("value", "")
                    img_matches = re.findall(r'<img.*?src="(https?://[^"]+)"', content_html)
                    if img_matches:
                        cover_image_url = img_matches[0]
                
                item = NewsItem(
                    title=title,
                    link=entry.link,
                    published=entry.get("published", entry.get("updated", datetime.now().strftime("%Y-%m-%d"))),
                    source=source["name"],
                    summary=summary[:200],
                    cover_image_url=cover_image_url,
                    source_priority=source.get("priority", 99),
                    published_at=self._parse_publish_time(entry),
                    original_title=title,
                )
                items.append(item)
                valid_count += 1
            
            if time_filtered:
                logger.info(f"  -> {time_filtered} 条资讯因超出时间窗口被过滤。")
            if blacklist_filtered:
                logger.info(f"  -> {blacklist_filtered} 条资讯因命中黑名单被过滤。")
            logger.info(f"  -> 从 {source['name']} 中筛选出 {valid_count} 条相关资讯。")
            
            # 成功则重置失败计数
            self._source_fail_counts[source['name']] = 0
            return items

        except Exception as e:
            fail_count = self._source_fail_counts.get(source['name'], 0) + 1
            self._source_fail_counts[source['name']] = fail_count
            threshold = self.filter_config.get("source_fail_threshold", 3)
            if fail_count >= threshold:
                logger.error(f"[健康告警] 信源 '{source['name']}' 已连续失败 {fail_count} 次，请检查 URL 是否有效: {source['url']}")
            else:
                logger.error(f"从 {source['name']} 抓取时出错: {e}")
            return []

    async def _fetch_api_source(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """通过 API 形式抓取（目前专门针对 AIBase）"""
        # headers = { # Original headers, to be replaced
        #     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
        #     "Referer": "https://www.aibase.cn/"
        # }
        items = []
        # 模拟浏览器访问，尝试解决 401 问题
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.aibase.cn",
            "Referer": "https://www.aibase.cn/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site"
        }
        try:
            # If still 401, plan to fall back to HTML mode or use read_url_content.
            url = source['url'] # Define url variable for consistency with instruction's logger.info and session.get
            logger.info(f"正在抓取 API: {source['name']} ({url})...")
            async with session.get(url, headers=headers, timeout=15, ssl=False) as response:
                if response.status != 200:
                    logger.warning(f"  抓取失败 {source['name']}: 状态码 {response.status}")
                    return []
                data = await response.json()
            
            # AIBase API 结构: {"code":200, "data": {"list": [...]}}
            news_list = data.get("data", {}).get("list", [])
            valid_count = 0
            time_filtered = 0
            
            for entry in news_list:
                title = entry.get("title", "")
                # 构造链接，API 通常只给 ID
                news_id = entry.get("id")
                if not news_id or not title:
                    continue
                
                link = f"https://news.aibase.cn/news/{news_id}"
                self.stats["total_fetched"] += 1

                publish_time = self._extract_publish_time_from_mapping(entry)
                if not self._is_publish_time_within_window(publish_time):
                    time_filtered += 1
                    self.stats["time_filtered"] += 1
                    continue
                
                if self._is_in_sent_history(link, title):
                    self.stats["history_filtered"] += 1
                    continue
                
                # 关键词过滤
                is_valid, _ = self._is_relevant_with_reason(title, source=source)
                if not is_valid:
                    self.stats["miss_whitelist"] += 1
                    continue

                self.stats["hit_whitelist"] += 1
                
                item = NewsItem(
                    title=title,
                    link=link,
                    published=datetime.now().strftime("%Y-%m-%d"),
                    source=source["name"],
                    summary=entry.get("summary", ""),
                    cover_image_url=entry.get("cover_image", ""),
                    source_priority=source.get("priority", 99),
                    published_at=publish_time,
                    original_title=title,
                )
                items.append(item)
                valid_count += 1
                
            if time_filtered:
                logger.info(f"  -> {time_filtered} 条资讯因超出时间窗口被过滤。")
            logger.info(f"  -> 从 {source['name']} API 中筛选出 {valid_count} 条相关资讯。")
            self._source_fail_counts[source['name']] = 0
            return items
            
        except Exception as e:
            logger.error(f"从 {source['name']} (API) 抓取时出错: {e}")
            return []

    async def _fetch_html_source(self, session: aiohttp.ClientSession, source: Dict[str, str]) -> List[NewsItem]:
        """通用的 HTML 抓取（作为回退或备选）"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        items = []
        # 此处保留一个基础的 HTML 解析逻辑，以便后续其他源使用
        logger.warning(f"HTML 模式抓取已针对 AIBase 弃用，请使用 API 模式。")
        return []

    async def fetch_all_async(self, limit: int = None) -> List[NewsItem]:
        """异步并发获取所有源的新闻，按 priority 优先级排序，每源受独立配额制约"""
        if limit is None:
            limit = self.filter_config.get("max_count", 15)
        global_max_per_source = int(self.filter_config.get("max_per_source", 0) or 0)
        
        # 按 priority 升序排列信源（数字越小优先级越高）
        sorted_sources = sorted(self.sources, key=lambda s: s.get("priority", 99))
            
        async with aiohttp.ClientSession() as session:
            tasks = [self._fetch_source(session, source) for source in sorted_sources]
            results = await asyncio.gather(*tasks)
            
        # 合并所有结果（source 顺序即优先级顺序）
        all_news = []
        for source, res in zip(sorted_sources, results):
            # 全局设为 0 时，候选阶段不再限制单源条数，直接交给后续质量排序决定
            if global_max_per_source <= 0:
                source_limit = 0
            else:
                source_limit = int(source.get("max_per_source", global_max_per_source) or 0)
            if source_limit and source_limit > 0:
                all_news.extend(res[:source_limit])
            else:
                all_news.extend(res)
            
        # 全局去重（优先按归一化 URL，其次按标题指纹）
        seen_identity_keys = set()
        unique_news = []
        for item in all_news:
            identity_keys = self._build_identity_keys(link=item.link, title=item.original_title or item.title)
            if any(key in seen_identity_keys for key in identity_keys):
                continue
            seen_identity_keys.update(identity_keys)
            unique_news.append(item)
            
        candidate_pool_limit = self._get_candidate_pool_limit(limit)
        final_list = unique_news[:candidate_pool_limit]
        
        logger.info(
            f"抓取总结：共筛选出 {len(final_list)} 条候选资讯 "
            f"(发布上限={limit}, 候选池上限={candidate_pool_limit}, 单源上限={global_max_per_source or '不限'})"
        )
        return final_list

    def fetch_latest_news(self, limit: int = None) -> List[NewsItem]:
        """同步包装器，保持向后兼容"""
        # 注意：在某些环境中 asyncio.run 可能会冲突
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 这种情况下无法使用 run
                import nest_asyncio
                nest_asyncio.apply()
            return asyncio.run(self.fetch_all_async(limit))
        except Exception:
            # Fallback
            return asyncio.run(self.fetch_all_async(limit))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fetcher = AINewsFetcher()
    news = fetcher.fetch_latest_news()
    print(f"\nFound {len(news)} articles:")
    for n in news:
        print(f"- [{n.source}] {n.title}")
        print(f"  {n.link}\n")
