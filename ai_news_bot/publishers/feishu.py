import logging
import requests
import time
import os
from typing import Dict, Any, List, Optional
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from publishers.base import PublisherBase
from dotenv import load_dotenv

load_dotenv()

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_FOLDER_TOKEN = os.getenv("FEISHU_FOLDER_TOKEN", "")

logger = logging.getLogger(__name__)

class FeishuPublisher(PublisherBase):
    """
    飞书文档发布渠道。
    继承自 PublisherBase，将抓取和生成后的结构化内容块（Blocks）写入飞书云文档/知识库。
    """
    def __init__(self, app_id: str = None, app_secret: str = None, folder_token: str = None):
        self.app_id = app_id or FEISHU_APP_ID
        self.app_secret = app_secret or FEISHU_APP_SECRET
        self.folder_token = folder_token or FEISHU_FOLDER_TOKEN
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
    def create_document(self, title: str) -> Optional[Dict[str, str]]:
        """创建一个新的 Docx 文档（带重试机制）"""
        token = self._get_tenant_access_token()
        if not token:
            return None

        # 尝试在知识库(Wiki)创建节点
        if self.folder_token and len(self.folder_token) > 20 and not self.folder_token.startswith("fld"):
            try:
                headers = {"Authorization": f"Bearer {token}"}
                url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token={self.folder_token}"
                
                space_id = ""
                resp = requests.get(url, headers=headers, timeout=10)
                res_data = resp.json()
                if res_data.get("code") == 0:
                    space_id = res_data.get("data", {}).get("node", {}).get("space_id", "")
                
                if space_id:
                    create_url = f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"
                    payload = {
                        "obj_type": "docx",
                        "parent_node_token": self.folder_token,
                        "node_type": "origin",
                        "origin_node_token": "",
                        "title": title
                    }
                    resp = requests.post(create_url, headers=headers, json=payload, timeout=15)
                    res_data = resp.json()
                    if res_data.get("code") == 0:
                        doc_data = res_data.get("data", {}).get("node", {})
                        return {
                            "document_id": doc_data.get("obj_token"),
                            "node_token": doc_data.get("node_token"),
                            "revision_id": "-1",
                            "is_wiki": True
                        }
                    else:
                        logger.warning(f"Wiki creation failed (Code {res_data.get('code')}), falling back to regular docs...")
                else:
                    logger.warning("Could not get space_id, falling back to regular docs...")
            except Exception as e:
                logger.error(f"Wiki logic error: {e}, falling back to regular docs...")

        # 兜底：普通云文档接口创建
        logger.info("Creating document in regular docs storage...")
        url = "https://open.feishu.cn/open-apis/docx/v1/documents"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"title": title}
        
        if self.folder_token and self.folder_token.startswith("fld"):
            payload["folder_token"] = self.folder_token

        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        res_data = resp.json()
        if res_data.get("code") == 0:
            doc_data = res_data.get("data", {}).get("document", {})
            return {
                "document_id": doc_data.get("document_id"),
                "revision_id": str(doc_data.get("revision_id")),
                "is_wiki": False # 标记以便拼接链接时区分
            }
        else:
            raise Exception(f"Feishu Doc Creation Error: {res_data}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def write_blocks(self, document_id: str, blocks: List[Dict[str, Any]], revision_id: str = "-1") -> bool:
        """向文档追加 Block 列表内容（带重试机制）"""
        token = self._get_tenant_access_token()
        if not token:
            return False

        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        headers = {"Authorization": f"Bearer {token}"}
        
        batch_size = 50
        for i in range(0, len(blocks), batch_size):
            batch_blocks = blocks[i:i + batch_size]
            payload = {
                "children": batch_blocks,
                "index": -1 # -1表示追加到最后
            }

            resp = requests.post(url, headers=headers, json=payload, params={"document_revision_id": revision_id}, timeout=30)
            res_data = resp.json()
            if res_data.get("code") == 0:
                revision_id = str(res_data.get("data", {}).get("document_revision_id", "-1"))
                time.sleep(0.5) 
            else:
                raise Exception(f"Feishu Block Writing Error (batch {i}): {res_data}")
                
        return True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def upload_image(self, image_url: str, document_id: str) -> Optional[str]:
        """下载公网图片并上传至飞书空间（带重试机制）"""
        token = self._get_tenant_access_token()
        if not token or not image_url:
            return None

        img_resp = requests.get(image_url, timeout=15)
        img_resp.raise_for_status()
        image_bytes = img_resp.content
        
        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        headers = {"Authorization": f"Bearer {token}"}
        
        content_type = img_resp.headers.get('Content-Type', 'image/jpeg')
        ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
        file_name_val = f"image.{ext}"
        
        data = {
            "file_name": file_name_val,
            "parent_type": "docx_image",
            "size": len(image_bytes),
            "parent_node": document_id
        }
        files = {
            "file": (file_name_val, image_bytes, content_type)
        }
        res = requests.post(url, headers=headers, data=data, files=files, timeout=20)
        res_data = res.json()
        if res_data.get("code") == 0:
            return res_data.get("data", {}).get("file_token")
        else:
            raise Exception(f"Feishu Image Upload Error: {res_data}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def set_public_readable(self, document_id: str, doc_type: str = "docx") -> bool:
        """设置文档权限为"互联网上获得链接的任何人可阅读"（带重试机制）"""
        token = self._get_tenant_access_token()
        if not token:
            return False

        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{document_id}/public"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"type": doc_type}
        payload = {
            "link_share_entity": "anyone_readable",
            "comment_entity": "anyone_can_view",
            "copy_entity": "anyone_can_view",
            "external_access": True,
        }

        resp = requests.patch(url, headers=headers, json=payload, params=params, timeout=10)
        res_data = resp.json()
        if res_data.get("code") == 0:
            logger.info(f"✅ 文档权限已设置为互联网公开可读: {document_id}")
            return True
        else:
            raise Exception(f"Feishu Permission Setting Error: {res_data}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def add_collaborator(self, document_id: str, user_id: str, perm: str = "full_access", doc_type: str = "docx") -> bool:
        """将指定用户添加为文档协作者（带重试机制）"""
        token = self._get_tenant_access_token()
        if not token:
            return False

        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{document_id}/members"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"type": doc_type}
        payload = {
            "member_type": "userid",
            "member_id": user_id,
            "perm": perm,
        }

        resp = requests.post(url, headers=headers, json=payload, params=params, timeout=10)
        res_data = resp.json()
        if res_data.get("code") == 0:
            logger.info(f"✅ 已将用户 {user_id} 添加为文档协作者 (权限: {perm})")
            return True
        else:
            raise Exception(f"Feishu Collaborator Adding Error: {res_data}")

    def get_document_url(self, document_id: str, is_wiki: bool = False) -> str:
        """根据 document_id 和类型返回用户可访问的在线链接形式"""
        if is_wiki:
            return f"https://feishu.cn/wiki/{document_id}"
        return f"https://feishu.cn/docx/{document_id}"

    def publish(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        核心发布流程。
        实现自 PublisherBase。Feishu 需要额外传入 `blocks` 来组装样式。
        在这里因为 `content` 参数必须存在以满足接口签名，我们实际上并不直接使用传进来的纯文本 content，
        而是依赖 kwargs 里的 `blocks`（由组装器生成）进行 API 写入。
        """
        blocks = kwargs.get('blocks')
        owner_user_id = kwargs.get('owner_user_id')
        
        if not blocks:
            logger.error("FeishuPublisher publish failed: Missing structurally required 'blocks'.")
            return {"success": False, "error": "Missing blocks data"}

        try:
            # 1. 创建文档
            doc_info = self.create_document(title=title)
            if not doc_info:
                return {"success": False, "error": "Document creation returned None"}
                
            doc_id = doc_info["document_id"]
            node_token = doc_info.get("node_token")
            rev_id = doc_info["revision_id"]
            is_wiki = doc_info.get("is_wiki", False)
            
            # 使用 wiki 创建时，ID 处理略有不同
            target_id = node_token if is_wiki else doc_id
            
            # 2. 写入内容块
            success = self.write_blocks(document_id=doc_id, blocks=blocks, revision_id=rev_id)
            if not success:
                return {"success": False, "error": "Failed to write blocks"}
                
            # 3. 设置权限
            try:
                self.set_public_readable(target_id)
            except Exception as e:
                logger.error(f"Failed to set public readable: {e}")
                
            try:
                if owner_user_id:
                    self.add_collaborator(target_id, owner_user_id, perm="full_access")
            except Exception as e:
                logger.error(f"Failed to add collaborator: {e}")
                
            doc_url = self.get_document_url(target_id, is_wiki=is_wiki)
            return {
                "success": True, 
                "url": doc_url,
                "doc_id": target_id
            }
        except Exception as e:
            logger.error(f"Feishu publish process failed: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

# ==========================================
# 辅助构建飞书 Block 的工具库 (直接继承原结构，无需变动)
# ==========================================
class FeishuBlockBuilder:
    @staticmethod
    def header(text: str, level: int = 1) -> Dict[str, Any]:
        block_type = max(1, min(9, level))
        return {"block_type": block_type + 2, f"heading{block_type}": {"elements": [{"text_run": {"content": text}}]}}

    @staticmethod
    def heading_elements(elements: List[Dict[str, Any]], level: int = 1) -> Dict[str, Any]:
        block_type = max(1, min(9, level))
        return {"block_type": block_type + 2, f"heading{block_type}": {"elements": elements}}

    @staticmethod
    def paragraph(text: str) -> Dict[str, Any]:
        if not text: text = " "
        return {"block_type": 2, "text": {"elements": [{"text_run": {"content": text}}]}}

    @staticmethod
    def paragraph_with_link(text: str, link_url: str) -> Dict[str, Any]:
        return {"block_type": 2, "text": {"elements": [{"text_run": {"content": text, "text_element_style": {"link": {"url": link_url}}}}]}}

    @staticmethod
    def ordered_list(text: str, link_url: str = None) -> Dict[str, Any]:
        element = {"text_run": {"content": text}}
        if link_url: element["text_run"]["text_element_style"] = {"link": {"url": link_url}}
        return {"block_type": 13, "ordered": {"elements": [element]}}

    @staticmethod
    def parse_markdown_bold(text: str) -> List[Dict[str, Any]]:
        import re
        parts = re.split(r'(\*\*.*?\*\*)', text)
        elements = []
        for part in parts:
            if not part: continue
            if part.startswith('**') and part.endswith('**'):
                elements.append({"text_run": {"content": part[2:-2], "text_element_style": {"bold": True}}})
            else:
                elements.append({"text_run": {"content": part}})
        return elements

    @staticmethod
    def bullet_list_rich(text: str) -> Dict[str, Any]:
        return {"block_type": 12, "bullet": {"elements": FeishuBlockBuilder.parse_markdown_bold(text)}}

    @staticmethod
    def bullet_list(items: List[str]) -> List[Dict[str, Any]]:
        return [FeishuBlockBuilder.bullet_list_rich(item) for item in items]

    @staticmethod
    def divider() -> Dict[str, Any]:
        return {"block_type": 22, "divider": {}}

    @staticmethod
    def image(image_token: str) -> Dict[str, Any]:
        return {"block_type": 27, "image": {"image_key": image_token}}
