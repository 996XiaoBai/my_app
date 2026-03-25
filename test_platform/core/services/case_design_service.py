import json
from typing import Any, Dict, List

from test_platform.core.services.result_contracts import build_case_suite, normalize_case_items


class CaseDesignService:
    """负责测试用例结果的结构化与序列化。"""

    def normalize_module_cases(self, raw_items: Any, default_module: str = "") -> List[Dict[str, Any]]:
        return normalize_case_items(raw_items, default_module=default_module)

    def build_suite(self, raw_items: Any, summary: str, default_module: str = "") -> Dict[str, Any]:
        return build_case_suite(raw_items, summary=summary, default_module=default_module)

    def serialize_suite(self, raw_items: Any, summary: str, default_module: str = "") -> str:
        suite = self.build_suite(raw_items, summary=summary, default_module=default_module)
        return json.dumps(suite, ensure_ascii=False)
