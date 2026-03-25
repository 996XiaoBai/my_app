import json
from typing import Any, Dict, List

from test_platform.core.services.result_contracts import (
    build_requirement_analysis_pack,
    normalize_requirement_analysis_item,
)


class RequirementAnalysisService:
    """负责需求分析结果的结构化与序列化。"""

    def normalize_module_analysis(self, raw_item: Any, default_module: str = "") -> Dict[str, Any]:
        return normalize_requirement_analysis_item(raw_item, default_module=default_module)

    def build_pack(self, raw_items: Any, summary: str, default_module: str = "") -> Dict[str, Any]:
        return build_requirement_analysis_pack(raw_items, summary=summary, default_module=default_module)

    def serialize_pack(self, raw_items: List[Dict[str, Any]], summary: str, default_module: str = "") -> str:
        pack = self.build_pack(raw_items, summary=summary, default_module=default_module)
        return json.dumps(pack, ensure_ascii=False)
