import json
from typing import Any, Dict, List

from test_platform.core.services.result_contracts import (
    build_flowchart_pack,
    normalize_flowchart_item,
)


class FlowchartService:
    """负责业务流程图结果的结构化与序列化。"""

    def normalize_module_flowchart(self, raw_item: Any, default_module: str = "") -> Dict[str, Any]:
        return normalize_flowchart_item(raw_item, default_module=default_module)

    def build_pack(self, raw_items: Any, summary: str, default_module: str = "") -> Dict[str, Any]:
        return build_flowchart_pack(raw_items, summary=summary, default_module=default_module)

    def serialize_pack(self, raw_items: List[Dict[str, Any]], summary: str, default_module: str = "") -> str:
        pack = self.build_pack(raw_items, summary=summary, default_module=default_module)
        return json.dumps(pack, ensure_ascii=False)
