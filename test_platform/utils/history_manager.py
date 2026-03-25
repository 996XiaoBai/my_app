import os
import glob
import json
import uuid
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Optional

# 配置日志
logger = logging.getLogger(__name__)

# 历史记录存储路径固定在项目根目录下，避免因启动目录不同而写到不同位置
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HISTORY_DIR = str(PROJECT_ROOT / "history")

class HistoryManager:
    """
    负责评审记录的本地持久化和读取。
    文件命名格式：YYYYMMDD_HHMMSS_{filename}_{type}.json
    """
    
    def __init__(self, base_dir: str = HISTORY_DIR):
        self.base_dir = str(Path(base_dir))
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
            logger.info(f"📁 创建历史记录目录：{self.base_dir}")

    def save_report(self, content: str, filename: str, report_type: str, meta: Dict = None) -> str:
        """
        保存报告到本地 JSON 文件。
        
        Args:
            content (str): 报告内容（Markdown 文本）
            filename (str): 原始文件名
            report_type (str): 报告类型（review | test_case）
            meta (Dict): 元数据（生成耗时、模型配置等）
            
        Returns:
            str: 保存的文件路径
        """
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
        
        # 清洗文件名，防止非法字符
        safe_filename = "".join([c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
        if not safe_filename:
            safe_filename = "unnamed"
            
        file_id = f"{timestamp}_{safe_filename}_{report_type}_{uuid.uuid4().hex[:8]}"
        file_path = os.path.join(self.base_dir, f"{file_id}.json")
        
        data = {
            "id": file_id,
            "timestamp": now.isoformat(),
            "filename": filename,
            "type": report_type,
            "content": content,
            "meta": meta or {}
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 历史记录已保存：{file_path}")
            return file_path
        except Exception as e:
            logger.error(f"❌ 保存历史记录失败：{e}")
            return ""

    def list_reports(self, limit: int = 20) -> List[Dict]:
        """
        列出最近的报告记录（仅元数据，不含全文）。
        """
        files = glob.glob(os.path.join(self.base_dir, "*.json"))
        # 按修改时间倒序
        files.sort(key=os.path.getmtime, reverse=True)
        
        reports = []
        for f in files[:limit]:
            try:
                # 只读取前 500 字节以获取元数据，避免读取大文件全文
                with open(f, 'r', encoding='utf-8') as file_obj:
                    # 简单解析：由于是 JSON，为了安全还是得 load，但对于大文件可能慢
                    # 优化：文件名其实包含了大部分信息，这里为了准确性还是 load
                    data = json.load(file_obj)
                    reports.append({
                        "id": data.get("id"),
                        "timestamp": data.get("timestamp"),
                        "filename": data.get("filename"),
                        "type": data.get("type"),
                        "meta": data.get("meta") or {},
                        "file_path": f
                    })
            except Exception as e:
                logger.warning(f"⚠️ 无法读取历史文件 {f}: {e}")
                
        return reports

    def load_report(self, file_path: str) -> Optional[Dict]:
        """读取完整报告内容。"""
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ 读取历史记录失败：{e}")
            return None
