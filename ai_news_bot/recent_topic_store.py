import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


class RecentTopicStore:
    """保存最近已推送主题，用于跨天新鲜度去重。"""

    def __init__(self, file_path: str, max_records: int = 500, window_days: int = 7):
        self.file_path = file_path
        self.max_records = max_records
        self.window_days = window_days

    def load_records(self) -> List[Dict[str, Any]]:
        """读取主题历史。"""
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
        """持久化主题历史，并裁剪数量。"""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(records[: self.max_records], file, ensure_ascii=False, indent=2)

    def add_topics(self, news_items: List[Any], date_label: Optional[str] = None) -> None:
        """写入本次已推送主题。"""
        records = self.load_records()
        created_at = self._resolve_time(date_label=date_label).isoformat()
        new_records = []
        for item in news_items:
            new_records.append(
                {
                    "title": getattr(item, "title", ""),
                    "original_title": getattr(item, "original_title", "") or getattr(item, "title", ""),
                    "link": getattr(item, "link", ""),
                    "source": getattr(item, "source", ""),
                    "category": getattr(item, "category", ""),
                    "score": int(getattr(item, "score", 0) or 0),
                    "source_priority": int(getattr(item, "source_priority", 99) or 99),
                    "published_at": self._resolve_item_time(item, date_label=date_label).isoformat(),
                    "created_at": created_at,
                }
            )
        merged_records = new_records + records
        self.save_records(self._prune_records(merged_records, reference_time=self._resolve_time(date_label=date_label)))

    def get_recent_topics(self, reference_time: Optional[datetime] = None, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """读取近 N 天内已推送的主题。"""
        normalized_reference = self._normalize_datetime(reference_time) or datetime.now(timezone.utc)
        recent_records = self._prune_records(self.load_records(), reference_time=normalized_reference, days=days)
        self.save_records(recent_records)
        return recent_records

    def _prune_records(
        self,
        records: List[Dict[str, Any]],
        reference_time: Optional[datetime] = None,
        days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """按时间窗口清理历史。"""
        normalized_reference = self._normalize_datetime(reference_time) or datetime.now(timezone.utc)
        keep_days = int(days or self.window_days)
        cutoff = normalized_reference - timedelta(days=keep_days)
        pruned_records = []
        for record in records:
            created_at = self._normalize_datetime(self._parse_iso_datetime(record.get("created_at")))
            if created_at and created_at >= cutoff:
                pruned_records.append(record)
        return pruned_records[: self.max_records]

    def _resolve_item_time(self, item: Any, date_label: Optional[str] = None) -> datetime:
        """获取条目的发布时间，用于后续跨天比较。"""
        published_at = self._normalize_datetime(getattr(item, "published_at", None))
        if published_at:
            return published_at
        published_text = getattr(item, "published", "")
        parsed_time = self._parse_iso_datetime(published_text)
        if parsed_time:
            return parsed_time
        return self._resolve_time(date_label=date_label)

    def _resolve_time(self, date_label: Optional[str] = None) -> datetime:
        """根据日期标签生成统一时间。"""
        if date_label:
            try:
                return datetime.strptime(date_label, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                parsed_time = self._parse_iso_datetime(date_label)
                if parsed_time:
                    return parsed_time
        return datetime.now(timezone.utc)

    def _parse_iso_datetime(self, value: Any) -> Optional[datetime]:
        """解析常见日期格式。"""
        if not value:
            return None
        if isinstance(value, datetime):
            return self._normalize_datetime(value)
        text = str(value).strip()
        try:
            return self._normalize_datetime(datetime.fromisoformat(text.replace("Z", "+00:00")))
        except ValueError:
            try:
                return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return None

    def _normalize_datetime(self, value: Optional[datetime]) -> Optional[datetime]:
        """统一时间为 UTC。"""
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
