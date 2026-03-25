import logging
import os
import datetime
from typing import List, Optional, Any
from test_platform.infrastructure.feishu_client import FeishuClient, FeishuBlockBuilder

logger = logging.getLogger(__name__)

class WeeklyReportService:
    """
    周报生成服务。
    负责将企业微信讨论内容和 TAPD 截图通过 Dify LLM 清洗总结，
    再导出到飞书文档形成结构化周报。
    """
    def __init__(self, dify_client: Any, feishu_client: FeishuClient, config: Any):
        self.dify_client = dify_client
        self.feishu_client = feishu_client
        self.config = config

    def summarize_report(self, wecom_text: str, image_paths: List[str]) -> Optional[str]:
        """
        通过 Dify API 总结周报内容。
        """
        # 1. 上传图片（如果有）
        files = []
        for img_path in image_paths:
            if os.path.exists(img_path):
                file_id = self.dify_client.upload_file(img_path, self.dify_client.user_id)
                if file_id:
                    files.append({
                        "type": "image",
                        "transfer_method": "local_file",
                        "upload_file_id": file_id
                    })

        # 2. 构造 Prompt (严格遵循 PDF 模板)
        prompt = f"""
你是一位资深的测试专家，请根据以下提供的本周企业微信关键讨论片段和 TAPD 任务截图（由 Vision 模型辅助识别），进行清洗、去噪和深度总结，生成一份结构化的周报。

### 输入内容：
- **企业微信讨论**：
{wecom_text}

- **TAPD 任务截图**：(已在附件中提供，请结合图片内容进行分析总结)

### 生成要求（请严格遵守展示样式）：
1. **不要输出文档标题**：系统会自动设置文档标题。
2. **输出结构必须包含以下部分**：
    - **📋 工作概览**：用一段话简要概括本周核心进展（放在最顶部）。
    - **一、 [核心项目/工作项名称]**：
        - 使用“项目名称”作为二级标题。
        - 内部使用无序列表，每项格式为：**关键动作**：具体描述（参考 PDF 样式）。
    - **二、 [核心项目/工作项名称]**：(以此类推，根据实际内容拆分 2-4 个项目块)
    - **📊 本周任务明细**：
        - 总结 TAPD 截图中的具体任务。
        - **格式要求**：必须使用标准的 Markdown 表格。
        - 表格列名：需求 | 标题 | 任务类别 | 预计开始 | 预计结束。
3. **样式细节**：
    - 每个大板块之间使用 `---` 分割线。
    - 使用 **加粗** 强调每条内容的关键字。
    - 输出语言：中文。
    - 格式：标准 Markdown。

请确保内容干练、专业，排版呼吸感强，完全对齐用户提供的图片参考。
"""
        return self.dify_client.generate_completion(prompt, files=files)

    def export_to_feishu(self, title: str, summary_md: str) -> Optional[str]:
        """
        将生成的 Markdown 导出到飞书文档。
        """
        try:
            # 1. 创建文档
            doc_info = self.feishu_client.create_document(title)
            if not doc_info:
                return None
            
            doc_id = doc_info["document_id"]
            rev_id = doc_info["revision_id"]
            is_wiki = doc_info.get("is_wiki", False)
            node_token = doc_info.get("node_token")
            perm_target = node_token if is_wiki else doc_id

            # 2. 解析 Markdown 并构造 Blocks
            blocks = []
            lines = summary_md.split('\n')
            
            top_header_skipped = False
            table_lines = []
            in_table = False

            def flush_table():
                nonlocal in_table, table_lines
                if not table_lines:
                    return
                # 解析表格内容
                table_data = []
                for t_line in table_lines:
                    # 过滤分割线行 |---|---|
                    if t_line.strip().replace('|', '').replace('-', '').replace(' ', '') == "":
                        continue
                    # 拆分列
                    cols = [c.strip() for c in t_line.split('|') if c.strip() or t_line.strip().startswith('|')]
                    # 去掉开头和结尾的空项（如果有的化）
                    if t_line.strip().startswith('|'):
                        cols = [c.strip() for c in t_line.strip('|').split('|')]
                    if cols:
                        table_data.append(cols)
                
                if table_data:
                    blocks.append({"_type": "table", "data": table_data})
                table_lines = []
                in_table = False

            for line in lines:
                original_line = line
                line = line.strip()
                
                # 表格检测
                if line.startswith('|') and '|' in line[1:]:
                    in_table = True
                    table_lines.append(line)
                    continue
                elif in_table:
                    flush_table()

                if not line:
                    if blocks and isinstance(blocks[-1], dict) and blocks[-1].get("block_type") != 2:
                        blocks.append(FeishuBlockBuilder.paragraph(" "))
                    continue
                
                # 增强跳过逻辑
                if line.startswith('# ') and not top_header_skipped:
                    h_text = line[2:].strip()
                    if "周报" in h_text or (len(title) > 4 and title[:4] in h_text):
                        top_header_skipped = True
                        continue
                
                if not top_header_skipped and not line.startswith('#'):
                    top_header_skipped = True

                # 开始转换 Block
                if line.startswith('# '):
                    blocks.append(FeishuBlockBuilder.header(line[2:], level=1))
                elif line.startswith('## '):
                    blocks.append(FeishuBlockBuilder.header(line[3:], level=2))
                elif line.startswith('### '):
                    blocks.append(FeishuBlockBuilder.header(line[4:], level=3))
                elif line.startswith('#### '):
                    blocks.append(FeishuBlockBuilder.header(line[5:], level=4))
                elif line.startswith('> '):
                    blocks.append(FeishuBlockBuilder.quote(line[2:]))
                elif line.startswith('- ') or line.startswith('* '):
                    blocks.append(FeishuBlockBuilder.bullet_list(line[2:]))
                elif line.startswith('---'):
                    blocks.append(FeishuBlockBuilder.divider())
                else:
                    # 优先匹配数字标题
                    if any(line.startswith(prefix) for prefix in ["一、", "二、", "三、", "四、", "五、"]) or "任务明细" in line:
                        blocks.append(FeishuBlockBuilder.header(line, level=2))
                    else:
                        blocks.append(FeishuBlockBuilder.paragraph(line))
            
            # 最后检查
            flush_table()

            # 3. 写入内容
            current_rev = rev_id
            batch = []
            
            for b_item in blocks:
                if isinstance(b_item, dict) and b_item.get("_type") == "table":
                    # 先刷入之前的普通 batch
                    if batch:
                        self.feishu_client.write_blocks(doc_id, batch, revision_id=current_rev)
                        batch = []
                    
                    # 写入表格
                    current_rev = self.feishu_client.create_table_with_data(doc_id, b_item["data"], revision_id="-1")
                else:
                    batch.append(b_item)
            
            if batch:
                self.feishu_client.write_blocks(doc_id, batch, revision_id="-1")

            # 4. 设置权限
            try:
                self.feishu_client.set_public_readable(perm_target)
            except: pass
            
            owner_id = getattr(self.config, 'FEISHU_OWNER_USER_ID', None)
            if owner_id:
                try:
                    self.feishu_client.add_collaborator(perm_target, owner_id)
                except: pass
            
            return self.feishu_client.get_document_url(perm_target, is_wiki=is_wiki)
                
            return None
        except Exception as e:
            logger.error(f"Failed to export to Feishu: {e}")
            return None
