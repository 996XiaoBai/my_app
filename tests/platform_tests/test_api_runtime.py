from test_platform.api.runtime import resolve_prepared_context


class DummyReviewService:
    def __init__(self):
        self.prepare_calls = []

    def prepare_context(self, **kwargs):
        self.prepare_calls.append(kwargs)
        return {
            "context_id": "ctx-1",
            "context": {"combined_text": "建表语句"},
            "modules": [{"name": "核心功能", "pages": [1], "description": "全文解析"}],
            "cache_hit": False,
        }

    def get_context(self, context_id):
        return None


def test_resolve_prepared_context_skips_module_split_for_test_data():
    review_service = DummyReviewService()

    prepared_context, context_id, cache_hit = resolve_prepared_context(
        review_service=review_service,
        mode="test_data",
        requirement="",
        file_path="sample.doc",
        context_id=None,
        historical_findings="已有风险项",
    )

    assert prepared_context is not None
    assert context_id == "ctx-1"
    assert cache_hit is False
    assert review_service.prepare_calls[0]["skip_module_split"] is True
    assert prepared_context["historical_findings"] == "已有风险项"


def test_resolve_prepared_context_keeps_module_split_for_review():
    review_service = DummyReviewService()

    resolve_prepared_context(
        review_service=review_service,
        mode="review",
        requirement="登录需求",
        file_path=None,
        context_id=None,
        historical_findings=None,
    )

    assert review_service.prepare_calls[0]["skip_module_split"] is False
