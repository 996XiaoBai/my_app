import logging
import requests
import time
import os
from typing import Dict, Any, List, Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)

class FeishuClient:
    """
    飞书文档客户端，用于创建和写入周报。
    封装了常用的飞书云文档 API。
    """
    def __init__(self, app_id: str, app_secret: str, folder_token: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        self.folder_token = folder_token
        self.tenant_access_token = None
        self.token_expire_time = 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10), retry=retry_if_exception_type(Exception))
    def _get_tenant_access_token(self) -> str:
        """获取并缓存 tenant_access_token（带重试机制）"""
        if self.tenant_access_token and time.time() < self.token_expire_time:
            return self.tenant_access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        resp = requests.post(url, json=payload, timeout=10)
        res_data = resp.json()
        if res_data.get("code") == 0:
            self.tenant_access_token = res_data.get("tenant_access_token")
            # 预留 60 秒的安全 buffer
            expire = int(res_data.get("expire", 7200))
            self.token_expire_time = time.time() + expire - 60
            return self.tenant_access_token
        else:
            logger.error(f"Failed to get tenant_access_token: {res_data}")
            raise Exception(f"Feishu API Auth Error: {res_data}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def create_document(self, title: str) -> Optional[Dict[str, Any]]:
        """创建一个新的 Docx 文档。
        
        根据 folder_token 的类型自动判断：
        - 以 'fld' 开头：在普通云盘文件夹下创建
        - 其他长 token：尝试在知识库（Wiki）节点下创建子文档
        """
        token = self._get_tenant_access_token()
        if not token:
            return None

        headers = {"Authorization": f"Bearer {token}"}

        # 尝试在知识库(Wiki)创建子节点
        if self.folder_token and len(self.folder_token) > 20 and not self.folder_token.startswith("fld"):
            try:
                # 先查询 Wiki 节点获取 space_id
                url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={self.folder_token}"
                resp = requests.get(url, headers=headers, timeout=10)
                res_data = resp.json()
                space_id = ""
                if res_data.get("code") == 0:
                    space_id = res_data.get("data", {}).get("node", {}).get("space_id", "")
                
                if space_id:
                    # 在该 space 下创建子节点
                    create_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
                    payload = {
                        "obj_type": "docx",
                        "parent_node_token": self.folder_token,
                        "node_type": "origin",
                        "title": title
                    }
                    resp = requests.post(create_url, headers=headers, json=payload, timeout=15)
                    res_data = resp.json()
                    if res_data.get("code") == 0:
                        doc_data = res_data.get("data", {}).get("node", {})
                        logger.info(f"✅ 成功在知识库下创建文档: {title}")
                        return {
                            "document_id": doc_data.get("obj_token"),
                            "node_token": doc_data.get("node_token"),
                            "revision_id": "-1",
                            "is_wiki": True
                        }
                    else:
                        logger.warning(f"Wiki 创建失败 (Code {res_data.get('code')}): {res_data.get('msg')}，降级到普通文档...")
                else:
                    logger.warning("无法获取 space_id，降级到普通文档...")
            except Exception as e:
                logger.error(f"Wiki 创建异常: {e}，降级到普通文档...")

        # 兜底：普通云文档接口创建
        logger.info(f"在普通云盘创建文档: {title}")
        url = "https://open.feishu.cn/open-apis/docx/v1/documents"
        payload = {"title": title}
        
        # 只要配置了 folder_token，就尝试带上（不再强制要求以 fld 开头）
        if self.folder_token:
            payload["folder_token"] = self.folder_token

        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        res_data = resp.json()
        if res_data.get("code") == 0:
            doc_data = res_data.get("data", {}).get("document", {})
            return {
                "document_id": doc_data.get("document_id"),
                "revision_id": str(doc_data.get("revision_id")),
                "is_wiki": False
            }
        else:
            # 如果带 folder_token 报错，尝试不带 folder_token 创建（保底操作）
            if self.folder_token:
                logger.warning(f"带 folder_token 创建失败 ({res_data.get('code')})，尝试在根目录创建...")
                payload.pop("folder_token")
                resp = requests.post(url, headers=headers, json=payload, timeout=15)
                res_data = resp.json()
                if res_data.get("code") == 0:
                    doc_data = res_data.get("data", {}).get("document", {})
                    return {
                        "document_id": doc_data.get("document_id"),
                        "revision_id": str(doc_data.get("revision_id")),
                        "is_wiki": False
                    }
            
            raise Exception(f"Feishu Doc Creation Error: {res_data}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def write_blocks(self, document_id: str, blocks: List[Dict[str, Any]], revision_id: str = "-1") -> str:
        """向文档追加内容块，返回最新的 revision_id"""
        token = self._get_tenant_access_token()
        if not token:
            return revision_id

        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        headers = {"Authorization": f"Bearer {token}"}
        
        batch_size = 50
        current_rev = revision_id
        for i in range(0, len(blocks), batch_size):
            batch_blocks = blocks[i:i + batch_size]
            payload = {
                "children": batch_blocks,
                "index": -1 
            }

            resp = requests.post(url, headers=headers, json=payload, params={"document_revision_id": current_rev}, timeout=30)
            res_data = resp.json()
            if res_data.get("code") == 0:
                current_rev = str(res_data.get("data", {}).get("document_revision_id", "-1"))
                time.sleep(0.5) 
            else:
                raise Exception(f"Feishu Block Writing Error (batch {i}): {res_data}")
                
        return current_rev

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def set_public_readable(self, document_id: str) -> bool:
        """设置文档为链接分享所有人可阅读"""
        token = self._get_tenant_access_token()
        if not token:
            return False

        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{document_id}/public"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"type": "docx"}
        payload = {
            "link_share_entity": "anyone_readable",
            "external_access": True,
        }

        resp = requests.patch(url, headers=headers, json=payload, params=params, timeout=10)
        res_data = resp.json()
        if res_data.get("code") == 0:
            return True
        else:
            raise Exception(f"Feishu Permission Setting Error: {res_data}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def add_collaborator(self, document_id: str, user_id: str, perm: str = "full_access") -> bool:
        """为文档添加协作者"""
        token = self._get_tenant_access_token()
        if not token:
            return False

        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{document_id}/members"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"type": "docx"}
        payload = {
            "member_type": "userid",
            "member_id": user_id,
            "perm": perm,
        }

        resp = requests.post(url, headers=headers, json=payload, params=params, timeout=10)
        res_data = resp.json()
        if res_data.get("code") == 0:
            return True
        else:
            raise Exception(f"Feishu Collaborator Adding Error: {res_data}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def update_text_block(self, document_id: str, block_id: str, text: str) -> bool:
        """更新一个文本块的内容 (docx.block.patch)"""
        token = self._get_tenant_access_token()
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{block_id}"
        headers = {"Authorization": f"Bearer {token}"}
        
        payload = {
            "replace_text": {
                "elements": FeishuBlockBuilder._build_text_elements(text)
            }
        }
        resp = requests.patch(url, headers=headers, json=payload, timeout=10)
        return resp.json().get("code") == 0

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def create_table_with_data(self, document_id: str, table_data: List[List[str]], revision_id: str = "-1") -> str:
        """
        在文档末尾创建一个原生表格。返回最新的 revision_id。
        """
        token = self._get_tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        row_size = len(table_data)
        col_size = len(table_data[0]) if row_size > 0 else 0
        
        # 1. 创建空结构的 Table Block
        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        payload = {
            "children": [{
                "block_type": 31, # table
                "table": {
                    "property": {
                        "row_size": row_size,
                        "column_size": col_size
                    }
                }
            }],
            "index": -1
        }
        
        resp = requests.post(url, headers=headers, json=payload, params={"document_revision_id": revision_id}, timeout=30)
        res_data = resp.json()
        if res_data.get("code") != 0:
            raise Exception(f"Feishu Table Init Error: {res_data}")
            
        new_table_block = res_data.get("data", {}).get("children", [])[0]
        cell_ids = new_table_block.get("table", {}).get("cells", [])
        
        # 2. 依次填充 Cell 内容
        for i in range(row_size):
            for j in range(col_size):
                idx = i * col_size + j
                if idx >= len(cell_ids): break
                
                cell_id = cell_ids[idx]
                content = table_data[i][j] if j < len(table_data[i]) else ""
                
                try:
                    # 使用 batch_create 在 cell 下创建段落
                    # 飞书 table cell 默认生成一个空段落，我们目前采取追加方案
                    # 如果后续需要更精准的首行替换，可以在此处先 get children 再 patch (修复后)
                    child_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{cell_id}/children"
                    payload = {
                        "children": [FeishuBlockBuilder.paragraph(content)],
                        "index": -1
                    }
                    requests.post(child_url, headers=headers, json=payload, timeout=10)
                except Exception as e:
                    logger.warning(f"Failed to fill cell {cell_id}: {e}")
                
        return str(res_data.get("data", {}).get("document_revision_id", "-1"))

    def get_document_url(self, document_id: str, is_wiki: bool = False) -> str:
        """根据文档类型返回正确的访问链接"""
        if is_wiki:
            return f"https://feishu.cn/wiki/{document_id}"
        return f"https://feishu.cn/docx/{document_id}"

class FeishuBlockBuilder:
    """构建飞书 Block 的工具类"""
    
    @staticmethod
    def _build_text_elements(text: str) -> List[Dict[str, Any]]:
        """解析文本中的 Markdown 语法（目前支持 **加粗**），并确保格式符合 API 要求"""
        import re
        if not text:
            return [{"text_run": {"content": " ", "text_element_style": {}}}]
        
        # 移除末尾换行符，防止 API 报错
        text = text.rstrip('\n')
        
        # 解析加粗 **text**
        parts = re.split(r'(\*\*.*?\*\*)', text)
        elements = []
        for part in parts:
            if not part: continue
            if part.startswith('**') and part.endswith('**'):
                elements.append({
                    "text_run": {
                        "content": part[2:-2],
                        "text_element_style": {"bold": True}
                    }
                })
            else:
                elements.append({
                    "text_run": {
                        "content": part,
                        "text_element_style": {}
                    }
                })
        
        if not elements:
            return [{"text_run": {"content": " ", "text_element_style": {}}}]
        return elements

    @staticmethod
    def header(text: str, level: int = 1) -> Dict[str, Any]:
        block_type = max(1, min(9, level))
        return {
            "block_type": block_type + 2, 
            f"heading{block_type}": {
                "elements": FeishuBlockBuilder._build_text_elements(text)
            }
        }

    @staticmethod
    def paragraph(text: str) -> Dict[str, Any]:
        return {
            "block_type": 2, 
            "text": {
                "elements": FeishuBlockBuilder._build_text_elements(text)
            }
        }

    @staticmethod
    def bullet_list(text: str) -> Dict[str, Any]:
        return {
            "block_type": 12, 
            "bullet": {
                "elements": FeishuBlockBuilder._build_text_elements(text)
            }
        }

    @staticmethod
    def quote(text: str) -> Dict[str, Any]:
        """引用块 (block_type 14)"""
        return {
            "block_type": 14,
            "quote": {
                "elements": FeishuBlockBuilder._build_text_elements(text)
            }
        }

    @staticmethod
    def table(data: List[List[str]]) -> Dict[str, Any]:
        """
        构建飞书表格 Block (嵌套结构)。
        每个单元格内默认为一个段落。
        """
        if not data:
            return FeishuBlockBuilder.paragraph("[Empty Table]")
            
        row_size = len(data)
        col_size = len(data[0]) if row_size > 0 else 0
        
        rows = []
        for i in range(row_size):
            cells = []
            for j in range(col_size):
                cell_text = data[i][j] if j < len(data[i]) else ""
                cells.append({
                    "block_type": 33, # table_cell
                    "table_cell": {},
                    "children": [FeishuBlockBuilder.paragraph(cell_text)]
                })
            rows.append({
                "block_type": 32, # table_row
                "table_row": {},
                "children": cells
            })
            
        return {
            "block_type": 31, # table
            "table": {
                "property": {
                    "row_size": row_size,
                    "column_size": col_size
                }
            },
            "children": rows
        }

    @staticmethod
    def divider() -> Dict[str, Any]:
        return {"block_type": 22, "divider": {}}
