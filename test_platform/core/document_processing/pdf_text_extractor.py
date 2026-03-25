import pdfplumber
import logging
import math
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from test_platform.core.document_processing.table_processor import TableData, extract_tables_from_page

logger = logging.getLogger(__name__)

class ExtractionMethod(Enum):
    TEXT = "text"              # 纯文本解析
    VISION = "vision"          # 视觉 AI 解析
    HYBRID = "hybrid"          # 混合模式（文本+视觉补齐）
    UNKNOWN = "unknown"

class PageStatus(Enum):
    SUCCESS = "success"
    PARTIAL_FAILED = "partial_failed"
    FAILED = "failed"
    SKIPPED = "skipped"

def calculate_readable_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    valid = sum(1 for c in text if c.isalnum() or '\u4e00' <= c <= '\u9fff' or c in "，。；：,.!?()[]【】+-_/ ")
    return valid / len(text)

@dataclass
class PageContent:
    """单页 PDF 内容及其元数据"""
    page_num: int
    text: str = ""
    has_images: bool = False
    image_count: int = 0
    status: PageStatus = PageStatus.SUCCESS
    method: ExtractionMethod = ExtractionMethod.TEXT
    
    # 评分维度
    visual_score: float = 0.0  # 视觉优先级分 (0-100)
    image_area_ratio: float = 0.0
    text_density: float = 0.0
    error_msg: str = ""
    
    tables: List[TableData] = field(default_factory=list) # 结构化表格
    
    has_vector_graphics: bool = False
    readable_char_ratio: float = 1.0
    risk_flags: List[str] = field(default_factory=list)
    business_tags: List[str] = field(default_factory=list)

    @property
    def text_length(self) -> int:
        return len(self.text.strip()) if self.text else 0

    @property
    def is_text_rich(self) -> bool:
        """根据评分判定是否属于纯文字导向页"""
        return self.visual_score < 40 and self.text_length > 100

    @property
    def needs_vision(self) -> bool:
        """核心路由逻辑：智能多维度判定是否需要 Vision 能力补偿"""
        # 1. 显性高分：视觉分超过阈值
        if self.visual_score >= 60:
            return True
            
        # 2. 隐性风险：无有效文本但有图或矢量图形
        if self.text_length < 30 and (self.has_images or self.has_vector_graphics):
            return True
            
        # 3. 业务规则匹配：识别出核心链路或模型等需要视觉增强的页
        if any(tag in self.business_tags for tag in ["FLOW_DIAGRAM", "UI_PROTOTYPE"]):
            return True
            
        # 4. 文本乱码现象：疑似扫描件导致的破碎字符
        if self.readable_char_ratio < 0.6 and self.text_length > 0:
            return True
            
        return False

def calculate_visual_priority_score(page, page_content: PageContent) -> Dict[str, float]:
    """
    基于多特征计算页面的视觉优先级分并真实统计字符包围盒面积。
    返回分数及各项因子。
    """
    width = float(page.width)
    height = float(page.height)
    page_area = width * height if width * height > 0 else 1.0
    
    # 1. 文字特征（真实占用面积）
    chars = page.chars if hasattr(page, "chars") else []
    text_area = 0.0
    for ch in chars:
        x0 = float(ch.get("x0", 0))
        x1 = float(ch.get("x1", 0))
        top = float(ch.get("top", 0))
        bottom = float(ch.get("bottom", 0))
        text_area += max(0.0, x1 - x0) * max(0.0, bottom - top)
        
    text_density = text_area / page_area
    
    # 2. 提取文本及可读性
    text = page.extract_text() or ""
    text_len = len(text.strip())
    page_content.readable_char_ratio = calculate_readable_char_ratio(text)
    
    if page_content.readable_char_ratio < 0.6:
        page_content.risk_flags.append("TEXT_GARBLED")
    
    # 3. 图片特征与矢量图检测
    images = page.images if hasattr(page, 'images') else []
    total_img_area = 0.0
    for img in images:
        img_x0 = float(img.get('x0', 0))
        img_x1 = float(img.get('x1', 0))
        img_top = float(img.get('top', 0))
        img_bot = float(img.get('bottom', 0))
        total_img_area += max(0.0, img_x1 - img_x0) * max(0.0, img_bot - img_top)
    
    img_ratio = total_img_area / page_area
    
    # 检测流程图、原型图相关对象
    rect_count = len(page.rects) if hasattr(page, "rects") else 0
    curve_count = len(page.curves) if hasattr(page, "curves") else 0
    line_count = len(page.lines) if hasattr(page, "lines") else 0
    
    if (rect_count + curve_count + line_count) > 20:
        page_content.has_vector_graphics = True
        page_content.risk_flags.append("VECTOR_HEAVY")
    
    # 4. 综合评分算法
    score = img_ratio * 100
    if text_len < 100:
        score += (100 - text_len) * 0.5
        page_content.risk_flags.append("LOW_TEXT")
    
    if text_len > 1000 and img_ratio < 0.05:
        score *= 0.3
        
    # 提取基础业务词根以推断页面类型
    keywords = ["流程", "原型", "架构", "交互", "示意图"]
    if any(k in text for k in keywords):
        page_content.business_tags.append("FLOW_DIAGRAM")
    
    return {
        "score": min(max(score, 0.0), 100.0),
        "img_ratio": img_ratio,
        "text_density": text_density
    }

def sort_words_by_layout(words: List[Dict], page_width: float, detect_columns: bool = True) -> str:
    """
    基于坐标对单词进行聚合，支持基础双栏布局分段。
    """
    if not words:
        return ""
        
    if not detect_columns or page_width <= 0:
        words.sort(key=lambda w: (w['top'], w['x0']))
        lines = []
        current_line = [words[0]]
        for i in range(1, len(words)):
            if abs(words[i]['top'] - current_line[-1]['top']) <= 3:
                current_line.append(words[i])
            else:
                current_line.sort(key=lambda w: w['x0'])
                lines.append(" ".join([w['text'] for w in current_line]))
                current_line = [words[i]]
        current_line.sort(key=lambda w: w['x0'])
        lines.append(" ".join([w['text'] for w in current_line]))
        return "\n".join(lines)
        
    # 双栏检测逻辑：以页面一半进行粗略切割
    mid_x = page_width / 2.0
    left_words = []
    right_words = []
    
    for w in words:
        if w['x1'] <= mid_x + 10:  # 稍微放宽容差
            left_words.append(w)
        elif w['x0'] >= mid_x - 10:
            right_words.append(w)
        else: # 跨越中线，算作左半边（或者全屏首行）
            left_words.append(w)
            
    # 分别排版后再上下相接
    def process_block(block_words):
        if not block_words: return ""
        block_words.sort(key=lambda w: (w['top'], w['x0']))
        lines = []
        current = [block_words[0]]
        for i in range(1, len(block_words)):
            if abs(block_words[i]['top'] - current[-1]['top']) <= 3:
                current.append(block_words[i])
            else:
                current.sort(key=lambda w: w['x0'])
                lines.append(" ".join([w['text'] for w in current]))
                current = [block_words[i]]
        current.sort(key=lambda w: w['x0'])
        lines.append(" ".join([w['text'] for w in current]))
        return "\n".join(lines)
        
    out_text = process_block(left_words)
    if right_words:
        out_text += "\n\n" + process_block(right_words)
        
    return out_text

def render_tables_as_markdown(tables: List[TableData]) -> str:
    """直接拾取自带通道提取的 Tables Markdown"""
    md_out = [tb.markdown for tb in tables if tb.markdown]
    return "\n\n".join(md_out)


def extract_pdf_content(pdf_path: str, max_pages: int = 0) -> List[PageContent]:
    """具备单页容错、布局解析与风险探测的高阶文本提取引擎。"""
    pages = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            pages_to_process = min(total_pages, max_pages) if max_pages > 0 else total_pages
            logger.info(f"PDF 提取启动：总 {total_pages} 页，处理 {pages_to_process} 页")
            
            for i in range(pages_to_process):
                page_content = PageContent(page_num=i + 1)
                page_status = PageStatus.SUCCESS
                
                try:
                    page = pdf.pages[i]
                except Exception as e:
                    logger.error(f"第 {i+1} 页加载失败: {e}")
                    page_content.status = PageStatus.FAILED
                    page_content.error_msg = f"加载失败: {e}"
                    pages.append(page_content)
                    continue
                
                # 特征与分数计算
                try:
                    metrics = calculate_visual_priority_score(page, page_content)
                    page_content.visual_score = metrics["score"]
                    page_content.image_area_ratio = metrics["img_ratio"]
                    page_content.text_density = metrics["text_density"]
                    images = page.images if hasattr(page, 'images') else []
                    page_content.has_images = len(images) > 0
                    page_content.image_count = len(images)
                except Exception as e:
                    logger.warning(f"第 {i+1} 页特征计算发生异常: {e}")
                    page_status = PageStatus.PARTIAL_FAILED
                
                # 文本结构与段落排序
                try:
                    words = page.extract_words() or []
                    page_width = float(page.width) if hasattr(page, 'width') else 0.0
                    if words:
                        text = sort_words_by_layout(words, page_width, detect_columns=True)
                    else:
                        text = page.extract_text() or ""
                    page_content.text = text.strip()
                except Exception as e:
                    logger.warning(f"第 {i+1} 页文本抽取失败: {e}")
                    page_content.risk_flags.append("TEXT_EXTRACTION_FAILED")
                    page_status = PageStatus.PARTIAL_FAILED
                
                # 结构化表格抽取与混合渲染
                try:
                    page_tables = extract_tables_from_page(page)
                    page_content.tables = page_tables
                    if page_tables:
                        page_content.risk_flags.append("TABLE_DETECTED")
                        md_tables = render_tables_as_markdown(page_tables)
                        if md_tables:
                            page_content.text += "\n\n[结构化表格内容提取]\n" + md_tables
                except Exception as e:
                    logger.warning(f"第 {i+1} 页表格提取异常: {e}")
                    page_content.risk_flags.append("TABLE_EXTRACTION_FAILED")
                    page_status = PageStatus.PARTIAL_FAILED
                
                page_content.status = page_status
                page_content.method = ExtractionMethod.VISION if page_content.needs_vision else ExtractionMethod.TEXT
                pages.append(page_content)
                
        vision_count = sum(1 for p in pages if p.method == ExtractionMethod.VISION)
        logger.info(f"PDF 评估完成：{len(pages)} 页中，{vision_count} 页被智能路由为 Vison 处理，保证不漏测")
        
    except Exception as e:
        logger.error(f"PDF 读取全量崩溃: {e}")
        
    return pages

def get_combined_text(pages: List[PageContent], overlap_chars: int = 200) -> str:
    """
    合并文本内容，支持跨页语义重叠 (Overlapping)。
    overlap_chars: 每一页末尾保留多少字符作为下一页的开头上下文。
    """
    parts = []
    prev_context = ""
    
    for page in pages:
        if page.text_length > 0:
            current_text = page.text
            
            # 构造分块，带上前一页的末尾作为上下文
            chunk = f"--- [Page {page.page_num} Start] ---\n"
            if prev_context:
                chunk += f"(...前页内容衔接: {prev_context})\n"
            
            chunk += current_text
            chunk += f"\n--- [Page {page.page_num} End] ---"
            
            parts.append(chunk)
            
            # 更新上下文 (保留末尾 N 个字符)
            if overlap_chars > 0 and len(current_text) > 0:
                start_idx = max(0, len(current_text) - overlap_chars)
                # 使用显式切片避免 Pyre 对负索引的潜在误判
                prev_context = current_text[start_idx:].strip().replace('\n', ' ')
            else:
                prev_context = ""
            
    return "\n\n".join(parts)

def get_vision_page_numbers(pages: List[PageContent]) -> List[int]:
    """获取标记为视觉处理的页码"""
    return [p.page_num for p in pages if p.method == ExtractionMethod.VISION]


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = extract_pdf_content(sys.argv[1])
        print(f"\n{'页码':<5} | {'评分':<5} | {'建议方法':<10} | {'文字字数':<8} | {'图片占比':<8}")
        print("-" * 50)
        for p in result:
            method_icon = "🖼️" if p.method == ExtractionMethod.VISION else "📝"
            print(f"P{p.page_num:<4} | {p.visual_score:>5.1f} | {method_icon} {p.method.value:<8} | {p.text_length:>8} | {p.image_area_ratio:>8.2%}")
