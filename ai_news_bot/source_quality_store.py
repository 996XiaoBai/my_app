import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple


class SourceQualityStore:
    """保存各信源近几天的质量表现，用于动态调权。"""

    def __init__(self, file_path: str, window_days: int = 7, max_records: int = 90):
        self.file_path = file_path
        self.window_days = window_days
        self.max_records = max_records

    def load_records(self) -> List[Dict[str, Any]]:
        """读取历史运行质量记录。"""
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
        """持久化历史运行质量记录。"""
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(records[: self.max_records], file, ensure_ascii=False, indent=2)

    def record_run(self, metrics_by_source: Dict[str, Dict[str, int]], date_label: Optional[str] = None) -> None:
        """记录一次运行中的信源质量指标。"""
        if not metrics_by_source:
            return
        records = self.load_records()
        record_time = self._resolve_time(date_label)
        records.insert(
            0,
            {
                "created_at": record_time.isoformat(),
                "sources": metrics_by_source,
            },
        )
        self.save_records(self._prune_records(records, reference_time=record_time))

    def get_source_adjustments(self, sources: Optional[List[str]] = None) -> Dict[str, int]:
        """获取最近窗口内的动态调权结果。"""
        aggregated_stats = self.get_aggregated_stats(sources=sources)
        return {source: self._calculate_adjustment(stats)[0] for source, stats in aggregated_stats.items()}

    def get_source_observations(self, sources: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """输出便于人工复核的信源健康度观察结果。"""
        observations = []
        aggregated_stats = self.get_aggregated_stats(sources=sources)
        for source, stats in aggregated_stats.items():
            adjustment, reasons = self._calculate_adjustment(stats)
            if adjustment == 0:
                continue
            observations.append(
                {
                    "source": source,
                    "adjustment": adjustment,
                    "reasons": reasons,
                    "stats": stats,
                }
            )
        observations.sort(key=lambda item: (item["adjustment"], -item["stats"].get("candidate_count", 0), item["source"]))
        return observations

    def get_aggregated_stats(self, sources: Optional[List[str]] = None) -> Dict[str, Dict[str, int]]:
        """聚合最近窗口内各信源的质量数据。"""
        filtered_sources = set(sources or [])
        aggregated_stats: Dict[str, Dict[str, int]] = {}
        records = self._prune_records(self.load_records())
        self.save_records(records)

        for record in records:
            for source, metrics in record.get("sources", {}).items():
                if filtered_sources and source not in filtered_sources:
                    continue
                source_stats = aggregated_stats.setdefault(
                    source,
                    {
                        "candidate_count": 0,
                        "low_quality_count": 0,
                        "same_event_merged_count": 0,
                        "recent_topic_duplicate_count": 0,
                        "selected_count": 0,
                    },
                )
                for key in source_stats:
                    source_stats[key] += int(metrics.get(key, 0) or 0)
        return aggregated_stats

    def _calculate_adjustment(self, stats: Dict[str, int]) -> Tuple[int, List[str]]:
        """根据质量表现计算调权分。"""
        candidates = int(stats.get("candidate_count", 0) or 0)
        if candidates < 3:
            return 0, []

        low_quality_rate = int(stats.get("low_quality_count", 0) or 0) / max(1, candidates)
        duplicate_rate = (
            int(stats.get("same_event_merged_count", 0) or 0)
            + int(stats.get("recent_topic_duplicate_count", 0) or 0)
        ) / max(1, candidates)
        selected_rate = int(stats.get("selected_count", 0) or 0) / max(1, candidates)

        adjustment = 0
        reasons: List[str] = []

        if low_quality_rate >= 0.5:
            adjustment -= 1
            reasons.append(f"低质量率偏高（{low_quality_rate:.0%}）")
        if duplicate_rate >= 0.3:
            adjustment -= 1
            reasons.append(f"重复率偏高（{duplicate_rate:.0%}）")
        if selected_rate >= 0.6 and low_quality_rate <= 0.2 and duplicate_rate <= 0.2:
            adjustment += 1
            reasons.append(f"稳定入选率较高（{selected_rate:.0%}）")

        return adjustment, reasons

    def _prune_records(
        self,
        records: List[Dict[str, Any]],
        reference_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """按时间窗口裁剪历史记录。"""
        normalized_reference = reference_time or self._get_latest_record_time(records) or datetime.now(timezone.utc)
        cutoff = normalized_reference - timedelta(days=self.window_days)
        pruned_records = []
        for record in records:
            created_at = self._parse_datetime(record.get("created_at"))
            if created_at and created_at >= cutoff:
                pruned_records.append(record)
        return pruned_records[: self.max_records]

    def _get_latest_record_time(self, records: List[Dict[str, Any]]) -> Optional[datetime]:
        """获取记录中的最新时间，避免测试依赖真实系统日期。"""
        parsed_times = [self._parse_datetime(record.get("created_at")) for record in records]
        normalized_times = [parsed_time for parsed_time in parsed_times if parsed_time is not None]
        if not normalized_times:
            return None
        return max(normalized_times)

    def _resolve_time(self, date_label: Optional[str]) -> datetime:
        """根据日期标签或当前时间生成统一时间。"""
        if date_label:
            try:
                return datetime.strptime(date_label, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                parsed_time = self._parse_datetime(date_label)
                if parsed_time:
                    return parsed_time
        return datetime.now(timezone.utc)

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """解析 ISO 时间。"""
        if not value:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        try:
            parsed_time = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed_time.tzinfo is None:
            return parsed_time.replace(tzinfo=timezone.utc)
        return parsed_time.astimezone(timezone.utc)
