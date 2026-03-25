"""
封装文档解析和处理逻辑。
"""
from typing import Tuple, Dict, List, Optional
import os
import logging
import base64
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from test_platform.core.document_processing.pdf_processor import convert_pdf_to_base64_images
from test_platform.core.document_processing.pdf_text_extractor import (
    extract_pdf_content, get_combined_text, get_vision_page_numbers, 
    PageContent, PageStatus, ExtractionMethod
)
from test_platform.core.document_processing.document_reader import read_document, is_supported
from test_platform.core.document_processing.vision_analyzer import VisionAnalyzer, MockVisionAnalyzer

logger = logging.getLogger(__name__)

class DocumentService:
    """提供底层的文档阅读与接口编排。"""
    MAX_UPLOAD_WORKERS = 5
    
    def __init__(self, vision_analyzer: Optional[VisionAnalyzer] = None):
        # 如果未注入，则默认使用 Mock 降级（或根据配置初始化默认适配器）
        self.vision_analyzer = vision_analyzer or MockVisionAnalyzer()

    def process_file(self, file_path: str, max_pages: int = 0) -> Tuple[str, Dict[int, Dict], List[PageContent]]:
        """
        混合识别处理 PDF。面向 VisionAnalyzer 接口进行解耦。
        Returns: (combined_text, vision_files_map, page_contents)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not is_supported(file_path):
            raise ValueError(f"Unsupported file format: {file_path}")

        text, is_pdf = read_document(file_path)
        if not is_pdf:
            dummy_page = PageContent(page_num=1, text=text, status=PageStatus.SUCCESS)
            return text, {}, [dummy_page]

        logger.info(f"📄 Processing PDF: {file_path} (Using Analyzer: {self.vision_analyzer.__class__.__name__})")
        
        # 1. 执行路由评分
        pages = extract_pdf_content(file_path, max_pages=max_pages)
        if not pages:
            return "", {}, []

        combined_text = get_combined_text(pages)
        vision_page_nums = get_vision_page_numbers(pages)
        
        vision_files_map = {}
        if vision_page_nums:
            logger.info(f"🖼️ 并发处理 {len(vision_page_nums)} 页视觉识别链路...")
            vision_files_map = self._upload_vision_pages(file_path, vision_page_nums, max_pages, pages)
            
            # 更新页面元数据
            for p in pages:
                if p.page_num in vision_files_map:
                    p.method = ExtractionMethod.HYBRID
                elif p.page_num in vision_page_nums:
                    p.status = PageStatus.PARTIAL_FAILED
                    p.error_msg = "视觉分析链路处理失败，已降级"
        
        return combined_text, vision_files_map, pages

    def _upload_vision_pages(self, pdf_path: str, vision_page_nums: List[int], max_pages: int, 
                             pages_meta: List[PageContent]) -> Dict[int, Dict]:
        """协调并发处理并将任务下沉至适配器"""
        all_images = convert_pdf_to_base64_images(pdf_path, max_pages=max_pages)
        files_map = {}
        
        def process_page(page_num, b64_data):
            try:
                # 准备临时物理文件（隔离适配器对内存对象的直接操作需求）
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(base64.b64decode(b64_data))
                    tmp_path = tmp.name
                
                try:
                    # 关键解耦调用：下沉至适配器层执行上传、重试、错误分类
                    media_ref = self.vision_analyzer.prepare_page_media(tmp_path)
                    
                    if media_ref.success:
                        return page_num, {
                            "type": "image",
                            "transfer_method": "local_file",
                            "upload_file_id": media_ref.media_id,
                            "url": media_ref.media_url,
                            "latency_ms": media_ref.latency_ms
                        }
                    else:
                        logger.error(f"Page {page_num} vision prep failed: {media_ref.error_message}")
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
            except Exception as e:
                logger.error(f"Error preparing page {page_num}: {e}")
            return page_num, None

        with ThreadPoolExecutor(max_workers=self.MAX_UPLOAD_WORKERS) as executor:
            futures = []
            for page_num in vision_page_nums:
                idx = page_num - 1
                if idx < len(all_images):
                    futures.append(executor.submit(process_page, page_num, all_images[idx]))
            
            for future in as_completed(futures):
                page_num, file_data = future.result()
                if file_data:
                    files_map[page_num] = file_data
                    for p in pages_meta:
                        if p.page_num == page_num:
                            p.status = PageStatus.SUCCESS
                            p.method = ExtractionMethod.HYBRID
                
        return files_map
