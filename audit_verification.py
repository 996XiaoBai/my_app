import os
import sys
import logging
import asyncio

# 添加项目根目录到 PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from test_platform.core.document_processing.pdf_text_extractor import extract_pdf_content, get_combined_text
from test_platform.core.services.document_service import DocumentService
from test_platform.core.document_processing.vision_analyzer import MockVisionAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuditVerify")

async def verify_pipeline():
    test_pdf = os.path.join(ROOT_DIR, "test_platform/tools/test.pdf")
    if not os.path.exists(test_pdf):
        logger.error(f"❌ 测试文件不存在: {test_pdf}")
        return False

    logger.info(f"🚀 开始审计验证：{test_pdf}")

    try:
        # 1. 测试 PDF 提取逻辑 (含 Layout-Aware)
        logger.info("--- 步骤 1: PDF 文字与布局提取审计 ---")
        pages = extract_pdf_content(test_pdf, max_pages=2)
        if not pages:
            logger.error("❌ PDF 提取结果为空")
            return False
        
        for p in pages:
            logger.info(f"Page {p.page_num}: Text Length={p.text_length}, Visual Score={p.visual_score:.2f}, Tables={len(p.tables)}")
            if p.tables:
                for idx, t in enumerate(p.tables):
                    logger.info(f"  Table {idx} md preview: {t.markdown[:50]}...")

        # 2. 测试文本合并与语义衔接 (Overlapping)
        combined_text = get_combined_text(pages, overlap_chars=50)
        logger.info(f"Combined Text Length: {len(combined_text)}")
        if "(...前页内容衔接:" in combined_text:
            logger.info("✅ 语义衔接（Overlapping）机制生效")
        else:
            logger.info("⚠️ 未检测到语义衔接标记 (可能因文档太短或只有一页)")

        # 3. 测试 Service 层解耦注入与运行
        logger.info("--- 步骤 2: DocumentService 解耦运行审计 ---")
        mock_analyzer = MockVisionAnalyzer()
        service = DocumentService(vision_analyzer=mock_analyzer)
        
        # 运行处理逻辑 (同步调用)
        combined_text, vision_files_map, pages = service.process_file(test_pdf, max_pages=2)
        
        if combined_text is not None:
             logger.info(f"✅ DocumentService 运行成功, 总长度: {len(combined_text)}")
             logger.info(f"视觉识别任务数: {len(vision_files_map)}")
             logger.info(f"解析页面对象数: {len(pages)}")
        else:
             logger.error("❌ DocumentService 返回内容为空")
             return False

        logger.info("🏆 所有审计验证项通过！系统处于可运行状态。")
        return True

    except Exception as e:
        logger.error(f"❌ 运行中发生异常: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(verify_pipeline())
    sys.exit(0 if success else 1)
