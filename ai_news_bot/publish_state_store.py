import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class PublishStateStore:
    """发布状态存储，记录文档发布结果与渠道补发状态。"""

    def __init__(self, file_path: str, max_records: int = 300):
        self.file_path = file_path
        self.max_records = max_records
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def load_records(self) -> List[Dict[str, Any]]:
        """加载所有发布记录。"""
        if not os.path.exists(self.file_path):
            return []
        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                data = json.load(file)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def save_records(self, records: List[Dict[str, Any]]) -> None:
        """保存发布记录，并做数量裁剪。"""
        trimmed_records = records[: self.max_records]
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(trimmed_records, file, ensure_ascii=False, indent=2)

    def create_record(
        self,
        bot_type: str,
        doc_title: str,
        doc_url: str,
        news_items: List[Dict[str, Any]],
        article_links: List[str],
        wecom_title: str,
        channels: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> str:
        """创建一条新的发布记录。"""
        records = self.load_records()
        record_id = uuid.uuid4().hex
        now = self._now_iso()
        channel_states = channels or {
            "feishu": {"status": "success", "updated_at": now},
            "wecom": {"status": "pending", "updated_at": now, "retry_count": 0},
        }

        if "feishu" in channel_states and "updated_at" not in channel_states["feishu"]:
            channel_states["feishu"]["updated_at"] = now
        if "wecom" in channel_states:
            channel_states["wecom"].setdefault("updated_at", now)
            channel_states["wecom"].setdefault("retry_count", 0)

        records.insert(
            0,
            {
                "record_id": record_id,
                "bot_type": bot_type,
                "doc_title": doc_title,
                "doc_url": doc_url,
                "wecom_title": wecom_title,
                "article_links": article_links,
                "news_items": news_items,
                "created_at": now,
                "channels": channel_states,
            },
        )
        self.save_records(records)
        return record_id

    def update_channel_status(
        self,
        record_id: str,
        channel: str,
        status: str,
        error: str = "",
        increment_retry: bool = False,
    ) -> bool:
        """更新指定渠道的发布状态。"""
        records = self.load_records()
        for record in records:
            if record.get("record_id") != record_id:
                continue
            channel_state = record.setdefault("channels", {}).setdefault(channel, {})
            channel_state["status"] = status
            channel_state["updated_at"] = self._now_iso()
            if error:
                channel_state["error"] = error
            else:
                channel_state.pop("error", None)
            if increment_retry:
                channel_state["retry_count"] = int(channel_state.get("retry_count", 0)) + 1
            self.save_records(records)
            return True
        return False

    def get_retryable_records(self, channel: str) -> List[Dict[str, Any]]:
        """获取需要重试的渠道记录。"""
        retryable_records: List[Dict[str, Any]] = []
        for record in self.load_records():
            channel_state = record.get("channels", {}).get(channel, {})
            if channel_state.get("status") in {"pending", "failed"}:
                retryable_records.append(record)
        return retryable_records

    def _now_iso(self) -> str:
        """生成统一的 UTC 时间戳。"""
        return datetime.now(timezone.utc).isoformat()
