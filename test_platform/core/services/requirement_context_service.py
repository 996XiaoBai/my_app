import copy
import hashlib
import os
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from test_platform.core.document_processing.document_reader import read_document


class RequirementContextService:
    """负责需求上下文构建与缓存复用。"""

    MIN_TEXT_FOR_MODULE_SPLIT = 80
    DEFAULT_CACHE_TTL_SECONDS = 30 * 60
    DEFAULT_MAX_ENTRIES = 64
    FILE_HASH_CHUNK_SIZE = 1024 * 1024

    def __init__(
        self,
        module_identifier: Callable[[str, str], Optional[List[Dict[str, Any]]]],
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        now_provider: Optional[Callable[[], float]] = None,
        pdf_context_builder: Optional[Callable[[str, int], Union[Tuple[str, Dict[int, str]], Dict[str, Any]]]] = None,
    ):
        self.module_identifier = module_identifier
        self.cache_ttl_seconds = max(0, int(cache_ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self.now_provider = now_provider or time.time
        self.pdf_context_builder = pdf_context_builder or self._extract_pdf_context
        self.contexts_by_id: Dict[str, Dict[str, Any]] = {}
        self.context_id_by_key: Dict[str, str] = {}
        self.context_meta_by_id: Dict[str, Dict[str, Any]] = {}

    def prepare_context(
        self,
        requirement: str = "",
        file_path: Optional[str] = None,
        max_pages: int = 0,
        skip_module_split: bool = False,
    ) -> Dict[str, Any]:
        self._prune_cache()
        cache_key = self._build_cache_key(
            requirement=requirement,
            file_path=file_path,
            max_pages=max_pages,
            skip_module_split=skip_module_split,
        )
        cached_context_id = self.context_id_by_key.get(cache_key)
        if cached_context_id:
            cached_payload = self.get_context(cached_context_id)
            if cached_payload:
                return cached_payload
            self.context_id_by_key.pop(cache_key, None)

        payload = self._build_context_payload(
            requirement=requirement,
            file_path=file_path,
            max_pages=max_pages,
            skip_module_split=skip_module_split,
        )
        self.contexts_by_id[payload["context_id"]] = copy.deepcopy(payload)
        self.context_id_by_key[cache_key] = payload["context_id"]
        now = self.now_provider()
        self.context_meta_by_id[payload["context_id"]] = {
            "cache_key": cache_key,
            "created_at": now,
            "last_accessed_at": now,
        }
        self._prune_cache()
        return copy.deepcopy(payload)

    def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        self._prune_cache()
        payload = self.contexts_by_id.get(context_id)
        if not payload:
            return None
        self._touch_context(context_id)
        result = copy.deepcopy(payload)
        result["cache_hit"] = True
        return result

    def _build_context_payload(
        self,
        requirement: str = "",
        file_path: Optional[str] = None,
        max_pages: int = 0,
        skip_module_split: bool = False,
    ) -> Dict[str, Any]:
        context = self._build_context(requirement=requirement, file_path=file_path, max_pages=max_pages)
        combined_text = str(context.get("combined_text") or "")
        file_basename = str(context.get("file_basename") or "Requirement")

        modules = None
        if not skip_module_split and len(combined_text) > self.MIN_TEXT_FOR_MODULE_SPLIT:
            modules = self.module_identifier(combined_text, file_basename)

        if not modules:
            page_texts = context.get("page_texts")
            total_pages = list(page_texts.keys()) if isinstance(page_texts, dict) and page_texts else [1]
            modules = [
                {
                    "name": "核心功能",
                    "description": "基于输入内容的全文解析",
                    "pages": total_pages
                }
            ]

        return {
            "context_id": str(uuid.uuid4()),
            "modules": modules,
            "context": context,
            "cache_hit": False
        }

    def _build_context(self, requirement: str = "", file_path: Optional[str] = None, max_pages: int = 0) -> Dict[str, Any]:
        context = {
            "combined_text": requirement or "",
            "vision_files_map": {},
            "pages": [],
            "page_texts": {1: requirement} if requirement else {},
            "file_basename": os.path.basename(file_path) if file_path else "Requirement",
            "requirement": requirement
        }

        if not file_path:
            return context

        if file_path.lower().endswith(".pdf"):
            try:
                pdf_context = self.pdf_context_builder(file_path, max_pages)
                if isinstance(pdf_context, dict):
                    context["combined_text"] = str(pdf_context.get("combined_text") or "")
                    context["vision_files_map"] = dict(pdf_context.get("vision_files_map") or {})
                    context["pages"] = list(pdf_context.get("pages") or [])
                    context["page_texts"] = dict(pdf_context.get("page_texts") or {})
                else:
                    combined_text, page_texts_map = pdf_context
                    context["combined_text"] = combined_text
                    context["page_texts"] = page_texts_map
                return context
            except Exception:
                return context

        text, _ = read_document(file_path)
        if text:
            context["combined_text"] = text
            context["page_texts"] = {1: text}
        return context

    def _build_cache_key(
        self,
        requirement: str = "",
        file_path: Optional[str] = None,
        max_pages: int = 0,
        skip_module_split: bool = False,
    ) -> str:
        digest = hashlib.md5()
        digest.update(str(max_pages).encode("utf-8"))
        digest.update(b"skip_module_split=" + str(bool(skip_module_split)).encode("utf-8"))
        digest.update((requirement or "").encode("utf-8"))
        if file_path and os.path.exists(file_path):
            self._update_digest_with_file(digest, file_path)
        return digest.hexdigest()

    def _extract_pdf_context(self, file_path: str, max_pages: int) -> Dict[str, Any]:
        from test_platform.core.services.document_service import DocumentService

        combined_text, vision_files_map, pages = DocumentService().process_file(file_path, max_pages=max_pages)
        page_texts_map = {
            page.page_num: page.text
            for page in pages
            if getattr(page, "text", "")
        }
        return {
            "combined_text": combined_text,
            "vision_files_map": vision_files_map,
            "pages": pages,
            "page_texts": page_texts_map,
        }

    def _update_digest_with_file(self, digest: Any, file_path: str) -> None:
        with open(file_path, "rb") as source:
            while True:
                chunk = source.read(self.FILE_HASH_CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)

    def _touch_context(self, context_id: str) -> None:
        meta = self.context_meta_by_id.get(context_id)
        if meta:
            meta["last_accessed_at"] = self.now_provider()

    def _prune_cache(self) -> None:
        if not self.context_meta_by_id:
            return

        now = self.now_provider()
        expired_ids = [
            context_id
            for context_id, meta in list(self.context_meta_by_id.items())
            if now - float(meta.get("last_accessed_at", 0.0)) > self.cache_ttl_seconds
        ]

        for context_id in expired_ids:
            self._evict_context(context_id)

        while len(self.context_meta_by_id) > self.max_entries:
            least_recently_used_id = min(
                self.context_meta_by_id.items(),
                key=lambda item: (
                    float(item[1].get("last_accessed_at", 0.0)),
                    float(item[1].get("created_at", 0.0)),
                ),
            )[0]
            self._evict_context(least_recently_used_id)

    def _evict_context(self, context_id: str) -> None:
        meta = self.context_meta_by_id.pop(context_id, None)
        self.contexts_by_id.pop(context_id, None)

        if not meta:
            return

        cache_key = meta.get("cache_key")
        if cache_key and self.context_id_by_key.get(cache_key) == context_id:
            self.context_id_by_key.pop(cache_key, None)
