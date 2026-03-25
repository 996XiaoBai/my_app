from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional

@dataclass
class TableData:
    """结构化表格数据契约"""
    table_index: int
    rows: List[List[str]]          # 原始二维数组 (JSON Channel)
    markdown: str                  # Markdown 格式 (Semantic Channel)
    bbox: List[float]              # 坐标范围 [x0, top, x1, bottom]
    metadata: Dict[str, Any] = field(default_factory=dict)

def table_to_markdown(rows: List[List[Optional[str]]]) -> str:
    """将二维数组转换为 Markdown 表格字符串"""
    if not rows or not rows[0]:
        return ""
    
    # 清洗空值
    clean_rows: List[List[str]] = []
    for row in rows:
        clean_row = [str(cell).strip() if cell is not None else "" for cell in row]
        clean_rows.append(clean_row)
    
    # 生成 Markdown
    md_parts = []
    if not clean_rows:
        return ""
        
    # 表头
    header = clean_rows[0]
    md_parts.append("| " + " | ".join(header) + " |")
    # 分隔符
    md_parts.append("| " + " | ".join(["---"] * len(header)) + " |")
    
    # 逐行处理内容 (跳过表头)
    for i in range(1, len(clean_rows)):
        row = clean_rows[i]
        md_parts.append("| " + " | ".join(row) + " |")
        
    return "\n".join(md_parts)

def extract_tables_from_page(page) -> List[TableData]:
    """提取页面中的所有表格，输出双通道数据结构"""
    tables = []
    try:
        raw_tables = page.find_tables()
        for idx, table in enumerate(raw_tables):
            grid = table.extract()
            if not grid:
                continue
                
            md = table_to_markdown(grid)
            tables.append(TableData(
                table_index=idx,
                rows=grid,
                markdown=md,
                bbox=list(table.bbox)
            ))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Table extraction failed: {e}")
        
    return tables
