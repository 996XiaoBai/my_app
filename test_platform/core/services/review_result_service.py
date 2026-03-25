import json
from typing import Any, Dict, List

from test_platform.core.services.result_contracts import (
    build_review_markdown,
    normalize_review_findings,
    sanitize_review_reports,
)


class ReviewResultService:
    """负责需求评审结构化结果的组装。"""

    def serialize(self, reports: Dict[str, Any], findings: List[Dict[str, Any]]) -> str:
        normalized_reports = sanitize_review_reports(reports)
        normalized_findings = normalize_review_findings(findings)
        payload = {
            "reports": normalized_reports,
            "findings": normalized_findings,
            "markdown": build_review_markdown(normalized_reports, normalized_findings),
        }
        return json.dumps(payload, ensure_ascii=False)
