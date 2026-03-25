import os
import sys
import asyncio
import logging
import json
import re
import time
from dotenv import load_dotenv

import datetime

try:
    from ai_news_fetcher import AINewsFetcher, NewsItem
    from editorial_review import (
        apply_diversity_constraints,
        build_review_report,
        filter_recent_topic_duplicates,
        merge_same_event_items,
        write_review_export,
    )
    from recent_topic_store import RecentTopicStore
    from source_quality_store import SourceQualityStore
    from services.common.dify_client import DifyClient, DifyRequestError, DifyRateLimitError
    from feishu_publisher import FeishuPublisher, FeishuBlockBuilder
    from wecom_bot_notifier import WeComBotNotifier
    from wechat_oa_publisher import WeChatOAPublisher
    from publish_state_store import PublishStateStore
except ImportError:
    from .ai_news_fetcher import AINewsFetcher, NewsItem
    from .editorial_review import (
        apply_diversity_constraints,
        build_review_report,
        filter_recent_topic_duplicates,
        merge_same_event_items,
        write_review_export,
    )
    from .recent_topic_store import RecentTopicStore
    from .source_quality_store import SourceQualityStore
    from .services.common.dify_client import DifyClient, DifyRequestError, DifyRateLimitError
    from .feishu_publisher import FeishuPublisher, FeishuBlockBuilder
    from .wecom_bot_notifier import WeComBotNotifier
    from .wechat_oa_publisher import WeChatOAPublisher
    from .publish_state_store import PublishStateStore

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("NewsBot")

class NewsBot:
    def __init__(self):
        self.skip_wecom_notifications = False
        self._load_config()
        self.fetcher = AINewsFetcher()
        current_bot_dir = os.path.dirname(os.path.abspath(__file__))
        state_file = os.path.join(current_bot_dir, "data", "publish_records.json")
        self.publish_state_store = PublishStateStore(state_file)
        self.recent_topic_store = RecentTopicStore(os.path.join(current_bot_dir, "data", "ai_recent_topics.json"))
        self.source_quality_store = SourceQualityStore(os.path.join(current_bot_dir, "data", "ai_source_quality.json"))
        self.review_export_dir = os.path.join(current_bot_dir, "data", "review_exports")
        self.latest_review_report = {}
        self._current_run_source_metrics = {}
        self._source_adjustments = {}

    def _is_wecom_enabled(self) -> bool:
        """判断当前运行是否允许发送企业微信通知。"""
        return bool(self.wecom_webhook_url) and not self.skip_wecom_notifications

    def _get_publish_limit(self) -> int:
        """读取最终发布条数上限"""
        return int(self.fetcher.filter_config.get("max_count", 15))

    def _get_breakdown_score(self, item, key: str) -> int:
        """获取指定维度的子评分。"""
        score_breakdown = getattr(item, "score_breakdown", {}) or {}
        try:
            return int(score_breakdown.get(key, 0))
        except Exception:
            return 0

    def _get_dify_throttle_backoff_seconds(self) -> int:
        """获取 Dify 限流后的额外退避时间。"""
        return int(self.fetcher.filter_config.get("dify_throttle_backoff_seconds", 6))

    def _resolve_generated_title(self, item, generated_title: str) -> str:
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

    def _reset_run_metrics(self) -> None:
        """清空本轮运行中的信源质量统计。"""
        self._current_run_source_metrics = {}

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

    def _persist_source_quality_metrics(self, date_label: str = None) -> None:
        """持久化本轮运行产生的信源质量指标。"""
        if not self._current_run_source_metrics:
            return
        self.source_quality_store.record_run(self._current_run_source_metrics, date_label=date_label)

    def _get_reference_time(self, items):
        """尽量从候选内容中提取统一的参考时间，用于跨天主题比较。"""
        parsed_times = []
        for item in items:
            published_at = getattr(item, "published_at", None)
            if published_at:
                parsed_times.append(published_at)
                continue
            published_text = getattr(item, "published", "")
            if not published_text:
                continue
            try:
                parsed_times.append(datetime.datetime.fromisoformat(str(published_text).replace("Z", "+00:00")))
                continue
            except ValueError:
                pass
            try:
                parsed_times.append(datetime.datetime.strptime(str(published_text), "%Y-%m-%d"))
            except ValueError:
                continue
        if not parsed_times:
            return None
        return max(parsed_times)

    def _rank_news_items(self, news_items):
        """按质量、时效和信源优先级做最终排序"""
        self._refresh_source_adjustments(sources=sorted({item.source for item in news_items if getattr(item, "source", "")}))

        def sort_key(item):
            published_at = getattr(item, "published_at", None)
            freshness = published_at.timestamp() if published_at else 0
            source_adjustment = self._get_source_dynamic_adjustment(getattr(item, "source", ""))
            item.source_dynamic_adjustment = source_adjustment
            effective_score = getattr(item, "score", 0) + source_adjustment
            return (
                -effective_score,
                -getattr(item, "score", 0),
                -self._get_breakdown_score(item, "technical_depth"),
                -self._get_breakdown_score(item, "practical_value"),
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
            source_observations=self.source_quality_store.get_source_observations(
                sources=sorted({item.source for item in news_items if getattr(item, "source", "")})
            ),
        )
        return selected_items

    def _apply_diversity_constraints(self, ranked_items, return_rejected: bool = False):
        """限制同一来源和同一类别的占比，提升日报多样性。"""
        max_per_source = int(self.fetcher.filter_config.get("max_per_source_final", 2))
        max_per_category = int(self.fetcher.filter_config.get("max_per_category_final", 2))
        selected_items, rejected_items = apply_diversity_constraints(ranked_items, max_per_source, max_per_category)
        if return_rejected:
            return selected_items, rejected_items
        return selected_items

    def _export_review_report(self, date_label: str = None):
        """导出每日人工复核候选池，方便抽检质量和淘汰原因。"""
        if not self.latest_review_report:
            return None
        export_path = write_review_export(
            report=self.latest_review_report,
            export_dir=self.review_export_dir,
            bot_type="ai_news",
            report_title="AI 日报人工复核候选池",
            date_label=date_label,
        )
        logger.info(f"已导出 AI 日报人工复核候选池: {export_path}")
        return export_path

    def _serialize_news_items(self, news_items):
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
                }
            )
        return serialized_items

    def _build_news_items_from_record(self, record):
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
                )
            )
        return restored_items

    def _retry_pending_wecom_notifications(self):
        """在新一轮发布前先补发未成功的企微通知。"""
        if not self._is_wecom_enabled():
            if self.skip_wecom_notifications:
                logger.info("当前运行已开启跳过企业微信通知，补发逻辑已跳过。")
            return

        pending_records = self.publish_state_store.get_retryable_records("wecom")
        if not pending_records:
            return

        logger.info(f"检测到 {len(pending_records)} 条待补发的企业微信通知，开始补发...")
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
                logger.info(f"企业微信补发成功: {record.get('doc_title', '')}")
            else:
                self.publish_state_store.update_channel_status(
                    record["record_id"],
                    "wecom",
                    "failed",
                    error="企微补发失败",
                    increment_retry=True,
                )
                logger.warning(f"企业微信补发失败，保留待重试状态: {record.get('doc_title', '')}")

    def _load_config(self):
        load_dotenv()
        self.feishu_app_id = os.getenv("FEISHU_APP_ID")
        self.feishu_app_secret = os.getenv("FEISHU_APP_SECRET")
        self.feishu_folder_token = os.getenv("FEISHU_FOLDER_TOKEN", "")
        self.dify_base = os.getenv("DIFY_API_BASE")
        self.dify_key = os.getenv("DIFY_API_KEY")
        self.dify_user = os.getenv("DIFY_USER_ID", "lifeng16527")
        self.wecom_webhook_url = os.getenv("WECOM_BOT_WEBHOOK_URL") or os.getenv("WECOM_WEBHOOK_URL")
        self.feishu_owner_user_id = os.getenv("FEISHU_OWNER_USER_ID")
        
        self.wechat_app_id = os.getenv("WECHAT_APP_ID")
        self.wechat_app_secret = os.getenv("WECHAT_APP_SECRET")

        if not all([self.feishu_app_id, self.feishu_app_secret]):
            logger.warning("缺少飞书应用凭证。文档将无法创建。")

    async def run(self, date_label: str = None):
        logger.info("--- 开始运行 AI 资讯机器人 ---")
        self._reset_run_metrics()

        self._retry_pending_wecom_notifications()
        
        # 1. 抓取新闻 (异步)
        logger.info("第一步：正在从各源抓取 AI 资讯...")
        news_items = await self.fetcher.fetch_all_async()
        
        if not news_items:
            logger.info("未发现新资讯。")
            return

        logger.info(f"成功抓取 {len(news_items)} 条资讯。")

        logger.info("第一点五步：正在补抓正文内容以提升质量判断...")
        news_items = await self.fetcher.enrich_items_with_full_content_async(news_items)

        # 2. 生成摘要 (目前为同步调用)
        news_items = self._summarize_news(news_items)
        self._persist_source_quality_metrics(date_label=date_label)
        if not news_items:
            logger.info("质量筛选后没有可发布的 AI 资讯。")
            return

        self._export_review_report(date_label=date_label)

        # 3. 发布至飞书文档
        self._publish_to_feishu(news_items, date_label=date_label)

        logger.info("--- 任务运行结束 ---")

    def _summarize_news(self, news_items):
        logger.info("第二步：正在通过 Dify 生成新闻摘要...")
        dify_client = None
        if self.dify_base and self.dify_key:
            dify_client = DifyClient(self.dify_base, self.dify_key, self.dify_user)
        else:
            logger.warning("Dify 未配置，质量闸门不可用，本次跳过 AI 日报推送。")
            return []
        
        ai_prompt_template = """标题: {title}
内容: {content}

请根据该文章针对【AI大模型发展、前沿科技动态、产品创新及研发技术】等维度的价值，为其打分 (1-10分)。
请尽量客观，对于标题党或内容极其空泛的凑数文章，请打低分(低于3分)。

请严格遵守以下 JSON 格式返回，不要包含任何其他说明文字或 Markdown 标记：
{{
  "title": "(精炼后的中文标题，必须简洁专业且与标题主旨一致)",
  "summary": "(中文摘要，紧贴核心价值，不超过250字)",
  "highlights": "(提取3个核心看点。格式：'* [Emoji] **关键词**: 说明')",
  "score": (整数，1-10，高价值高分，水文低分),
  "category": "(文章所属类别)",
  "score_breakdown": {{
    "timeliness": (整数，1-10，时效性),
    "source_authority": (整数，1-10，信源权威性),
    "technical_depth": (整数，1-10，技术深度),
    "practical_value": (整数，1-10，工程落地价值)
  }}
}}"""

        summarized_items = []
        min_quality_score = int(self.fetcher.filter_config.get("min_quality_score", 3))
        for item in news_items:
            self._record_source_metric(getattr(item, "source", ""), "candidate_count")
            if dify_client:
                try:
                    source_content = getattr(item, "content_text", "") or item.summary
                    item.original_title = item.original_title or item.title
                    res_text = dify_client.summarize_content(item.title, source_content, prompt_template=ai_prompt_template)
                    if res_text:
                        try:
                            data = json.loads(res_text)
                            new_title = data.get("title", item.title)
                            new_summary = data.get("summary", item.summary)
                            new_highlights = data.get("highlights", "")
                            score = int(data.get("score", 0))
                            
                            if score < min_quality_score:
                                self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                                logger.info(f"跳过（评分较低 {score}）: {item.title[:20]}...")
                                continue

                            item.category = data.get("category", "其他")
                            item.title = self._resolve_generated_title(item, new_title)
                            item.summary = new_summary
                            item.highlights = new_highlights
                            item.score = score
                            item.score_breakdown = data.get("score_breakdown", {}) or {}
                            logger.info(f"已生成中文摘要: {item.title[:20]}...")

                            if not item.summary.strip():
                                self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                                logger.warning(f"摘要为空，跳过: {item.title[:20]}...")
                                continue
                            summarized_items.append(item)
                        except json.JSONDecodeError:
                            self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                            logger.warning(f"Dify 返回非标准 JSON，跳过该条资讯: {item.title[:20]}...")
                    else:
                        self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                        logger.warning(f"Dify 响应为空，跳过: {item.title[:20]}...")
                except DifyRateLimitError as e:
                     backoff_seconds = self._get_dify_throttle_backoff_seconds()
                     logger.warning(f"Dify 触发吞吐限流，{backoff_seconds}s 后再处理下一条资讯: {item.title[:20]}...")
                     time.sleep(backoff_seconds)
                     logger.error(f"调用 Dify 异常，跳过该条资讯 (源: {item.title}): {e}")
                except DifyRequestError as e:
                     logger.error(f"调用 Dify 基础设施异常，跳过该条资讯 (源: {item.title}): {e}")
                except Exception as e:
                     self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                     import traceback
                     logger.error(f"调用 Dify 异常，跳过该条资讯 (源: {item.title}): {e}\n{traceback.format_exc()}")
                except BaseException as be:
                     self._record_source_metric(getattr(item, "source", ""), "low_quality_count")
                     logger.error(f"捕获到严重系统打断 (BaseException) 源: {item.title}: {be}")

        ranked_items = self._rank_news_items(summarized_items)
        logger.info(f"质量筛选完成：保留 {len(ranked_items)} 条高质量 AI 资讯。")
        return ranked_items

    def _publish_to_feishu(self, news_items, date_label: str = None):
        if not (self.feishu_app_id and self.feishu_app_secret):
             logger.info("Skipping Feishu Doc (No credentials)")
             return

        logger.info("第三步：正在执行飞书发布流程...")
        try:
            publisher = FeishuPublisher(self.feishu_app_id, self.feishu_app_secret, self.feishu_folder_token)
            
            # 若外部传入 date_label 则使用指定日期，否则使用今日日期
            today_str = date_label if date_label else datetime.date.today().strftime("%Y-%m-%d")
            doc_title = f"AI 每日新闻速递 ({today_str})"
            doc_info = publisher.create_document(doc_title)
            
            if not doc_info:
                logger.error("创建飞书文档失败。")
                return
                
            document_id = doc_info.get("document_id")
            is_wiki = doc_info.get("is_wiki", False)
            node_token = doc_info.get("node_token") if is_wiki else document_id
            logger.info(f"文档创建成功！ID: {document_id}, 是否知识库: {is_wiki}")

            blocks = []
            
            # 1️⃣ 顶部标题与副标题区 (匹配大绿字与小日期排版)
            blocks.append(FeishuBlockBuilder.heading_elements([
                {"text_run": {"content": "AI 日报", "text_element_style": {"text_color": 4, "bold": True}}}
            ], level=1))
            
            blocks.append(FeishuBlockBuilder.heading_elements([
                {"text_run": {"content": f"{today_str} • Albase 日报组整理", "text_element_style": {"text_color": 7}}}
            ], level=3))

            # 2️⃣ 目录聚合区
            # 为了实现图1的聚合目录效果，使用分割线 + 连续的有序列表
            blocks.append(FeishuBlockBuilder.divider())
            for i, item in enumerate(news_items, 1):
                blocks.append(FeishuBlockBuilder.ordered_list(item.title, link_url=item.link))
            blocks.append(FeishuBlockBuilder.divider())

            # 3️⃣ 正文新闻项
            for i, item in enumerate(news_items, 1):
                # 绿色数字与标题
                blocks.append(FeishuBlockBuilder.heading_elements([
                    {"text_run": {"content": f"{i}. ", "text_element_style": {"text_color": 7, "bold": True}}},
                    {"text_run": {"content": item.title, "text_element_style": {"text_color": 7, "bold": True, "link": {"url": item.link}}}}
                ], level=2))
                
                # 摘要段落 (恢复纯黑正文)
                blocks.append(FeishuBlockBuilder.paragraph(item.summary))
                
                img_url = getattr(item, 'image_url', getattr(item, 'cover_image_url', None))
                # 亮点提要标题 (恢复三级标题样式)
                if item.highlights:
                    blocks.append(FeishuBlockBuilder.heading_elements([
                        {"text_run": {"content": "亮点提要：", "text_element_style": {"bold": True}}}
                    ], level=3))
                    
                    # 亮点列表处理
                    for line in item.highlights.split('\n'):
                        line = line.strip()
                        if line:
                            if line.startswith('* '):
                                line = line[2:]
                            elif line.startswith('- '):
                                line = line[2:]
                            
                            # 传入富文本解析支持**加粗**结构
                            blocks.append(FeishuBlockBuilder.bullet_list_rich(line))
                            
                blocks.append(FeishuBlockBuilder.paragraph("")) # 空行
                if i < len(news_items):
                    blocks.append(FeishuBlockBuilder.divider())
            
            # 使用 block 批量追加接口
            # 注意需要正确的 URL 和 payload 格式，为了简便，我们需要单独封装 FeishuPublisher 的内容
            # 调用封装好的 write_blocks
            success = publisher.write_blocks(document_id, blocks)
            
            if success:
                # 如果是 Wiki 模式，则使用 node_token 来拼接外部访问链接，否则使用 obj_token(document_id)
                final_token = doc_info.get("node_token") if is_wiki else document_id
                doc_url = publisher.get_document_url(final_token, is_wiki=is_wiki)
                logger.info(f"成功将内容写入飞书文档: {doc_url}")

                # 先写正文，再开放权限，避免暴露空文档或半成品文档
                if self.feishu_owner_user_id:
                    publisher.add_collaborator(node_token, self.feishu_owner_user_id, is_wiki=is_wiki, role="full_access")
                publisher.set_public_sharing(node_token, is_wiki=is_wiki)
                if self.feishu_owner_user_id:
                    publisher.transfer_owner(node_token, self.feishu_owner_user_id, is_wiki=is_wiki)

                wecom_status = "pending" if self._is_wecom_enabled() else "skipped"
                record_id = self.publish_state_store.create_record(
                    bot_type="ai_news",
                    doc_title=doc_title,
                    doc_url=doc_url,
                    news_items=self._serialize_news_items(news_items),
                    article_links=[item.link for item in news_items],
                    wecom_title=doc_title,
                    channels={
                        "feishu": {"status": "success"},
                        "wecom": {"status": wecom_status, "retry_count": 0},
                    },
                )
                
                # --- 持久化去重：发布成功后回填历史记录 ---
                self.fetcher.save_to_history(news_items)
                self.recent_topic_store.add_topics(news_items, date_label=today_str)
                
                # 4. 企业微信转发
                if self._is_wecom_enabled():
                    logger.info("正在发送企业微信通知...")
                    notifier = WeComBotNotifier(self.wecom_webhook_url)
                    wecom_success = notifier.notify_feishu_doc(doc_title, doc_url, news_items)
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
                            error="企业微信通知发送失败",
                            increment_retry=True,
                        )
                elif self.skip_wecom_notifications:
                    logger.info("当前运行已开启跳过企业微信通知，仅保留飞书写入结果。")
                    
                # 5. 微信公众号同步 (仅在配置存在时运行) - 目前根据用户排期取消调用
                # if self.wechat_app_id and self.wechat_app_secret:
                #    logger.info("正在同步至微信公众号草稿箱...")
                #    wechat_pub = WeChatOAPublisher(self.wechat_app_id, self.wechat_app_secret)
                #    wechat_pub.push_to_draft(doc_title, doc_url, news_items)
                    
            else:
                logger.error("无法向飞书文档写入 Block 内容。")
            
        except Exception as e:
            logger.error(f"飞书发布流程发生异常: {e}")

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Fetch and summarize but don't publish")
    parser.add_argument("--skip-wecom", action="store_true", help="写入飞书，但跳过企业微信推送")
    parser.add_argument("--date", type=str, help="Specific date for the document title (e.g. 2026-02-24)")
    args = parser.parse_args()
    
    bot = NewsBot()
    bot.skip_wecom_notifications = args.skip_wecom
    if args.dry_run:
        logger.info("正在以试运行模式 (DRY-RUN) 执行...")
        news_items = await bot.fetcher.fetch_all_async()
        if news_items:
            # 去除之前写死的 2 条切片，测试完整列表过滤效果
            summarized = bot._summarize_news(news_items)
            for item in summarized:
                print(f"\n[标题]: {item.title}")
                print(f"[摘要]: {item.summary[:100]}...")
        else:
            logger.info("未抓取到任何资讯。")
    else:
        await bot.run(date_label=args.date)

if __name__ == "__main__":
    asyncio.run(main())
