import os
import requests
import logging
from typing import List, Dict, Any, Optional
import time

logger = logging.getLogger(__name__)

class FeishuPublisher:
    def __init__(self, app_id: str, app_secret: str, folder_token: str = ""):
        self.app_id = app_id
        self.app_secret = app_secret
        self.folder_token = folder_token
        self.tenant_access_token = None
        self.token_expire_time = 0

    def _get_tenant_access_token(self) -> str:
        """获取并缓存 tenant_access_token"""
        if self.tenant_access_token and time.time() < self.token_expire_time:
            return self.tenant_access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        try:
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
                return ""
        except Exception as e:
            logger.error(f"Error fetching tenant_access_token: {e}")
            return ""

    def create_document(self, title: str) -> Optional[Dict[str, str]]:
        """创建一个新的 Docx 文档"""
        token = self._get_tenant_access_token()
        if not token:
            return None

        # 尝试在知识库(Wiki)创建节点
        if self.folder_token and len(self.folder_token) > 20 and not self.folder_token.startswith("fld"):
            try:
                # 使用创建知识库节点接口
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

        # 兜底：在该文件夹下创建文档
        # 注意：只有在用户拥有的共享文件夹下创建，由该文件夹继承来的删除权限才真正对用户生效
        logger.info(f"正在文件夹 {self.folder_token} 下创建文档...")
        url = "https://open.feishu.cn/open-apis/docx/v1/documents"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"title": title}
        
        # 必须带上 folder_token，这样文档才不属于机器人的私有根目录
        if self.folder_token and self.folder_token.startswith("fld"):
            payload["folder_token"] = self.folder_token
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            res_data = resp.json()
            if res_data.get("code") == 0:
                doc_data = res_data.get("data", {}).get("document", {})
                document_id = doc_data.get("document_id")
                return {
                    "document_id": document_id,
                    "revision_id": str(doc_data.get("revision_id")),
                    "is_wiki": False 
                }
            else:
                logger.error(f"创建文档失败: {res_data}")
                # 如果文件夹创建也失败，则尝试在根目录创建（虽然这会导致删除受限，但至少能生成文档）
                if res_data.get("code") != 0:
                     logger.warning("文件夹创建失败，尝试在根目录创建...")
                     del payload["folder_token"]
                     resp = requests.post(url, headers=headers, json=payload, timeout=15)
                     res_data = resp.json()
                     if res_data.get("code") == 0:
                         doc_data = res_data.get("data", {}).get("document", {})
                         return {"document_id": doc_data.get("document_id"), "revision_id": str(doc_data.get("revision_id")), "is_wiki": False}
                return None
        except Exception as e:
            logger.error(f"创建文档发生异常: {e}")
            return None

    def write_blocks(self, document_id: str, blocks: List[Dict[str, Any]], revision_id: str = "-1") -> bool:
        """向文档追加 Block 列表内容
        
        blocks 是飞书 Docx API 要求的 Block 结构数组。
        API Reference: https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/create
        """
        token = self._get_tenant_access_token()
        if not token:
            return False

        url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children"
        headers = {"Authorization": f"Bearer {token}"}
        
        # 飞书 API 限制单次 children 最大长度为 50
        batch_size = 50
        for i in range(0, len(blocks), batch_size):
            batch_blocks = blocks[i:i + batch_size]
            payload = {
                "children": batch_blocks,
                "index": -1 # -1表示追加到最后
            }

            try:
                resp = requests.post(url, headers=headers, json=payload, params={"document_revision_id": revision_id}, timeout=30)
                res_data = resp.json()
                if res_data.get("code") == 0:
                    # 获取下一次需要的 revision_id 以防报错
                    revision_id = str(res_data.get("data", {}).get("document_revision_id", "-1"))
                    time.sleep(0.5) # 稍微节流一下
                else:
                    import json
                    logger.error(f"Failed to write blocks (batch {i}): {res_data}")
                    logger.error(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
                    return False
            except Exception as e:
                logger.error(f"Error writing blocks to document {document_id}: {e}")
                return False
                
        return True

    def upload_image(self, image_url: str, document_id: str) -> Optional[str]:
        """下载公网图片并长传至飞书空间，返回 image_token"""
        token = self._get_tenant_access_token()
        if not token or not image_url:
            return None

        try:
            # 下载图片流，对 5xx 错误最多重试 2 次
            img_resp = None
            for attempt in range(3):
                try:
                    r = requests.get(image_url, timeout=10)
                    if r.status_code == 200:
                        img_resp = r
                        break
                    elif r.status_code >= 500 and attempt < 2:
                        logger.warning(f"Image download returned {r.status_code}, retrying ({attempt + 1}/2)...")
                        time.sleep(1)
                    else:
                        logger.warning(f"Failed to download image {image_url}: Status {r.status_code}")
                        return None
                except requests.RequestException as e:
                    if attempt < 2:
                        logger.warning(f"Image download error, retrying ({attempt + 1}/2): {e}")
                        time.sleep(1)
                    else:
                        raise
            if not img_resp:
                return None
            image_bytes = img_resp.content
            
            url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
            headers = {"Authorization": f"Bearer {token}"}
            
            # 从 Header 里获取 Content-Type，回退到 image/jpeg
            content_type = img_resp.headers.get('Content-Type', 'image/jpeg')
            ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
            file_name_val = f"image.{ext}"
            
            # 使用 multipart/form-data 格式上传材料
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
                logger.warning(f"Failed to upload image to Feishu: {res_data}")
                return None
        except Exception as e:
            logger.error(f"Error uploading image {image_url}: {e}")
            return None

    def get_document_url(self, document_id: str, is_wiki: bool = False) -> str:
        """根据 document_id 和类型返回用户可访问的在线链接形式"""
        if is_wiki:
            # 对于 Wiki 模式，document_id 传入的应该是 node_token
            return f"https://feishu.cn/wiki/{document_id}"
        return f"https://feishu.cn/docx/{document_id}"

    def add_collaborator(self, token: str, user_id: str, is_wiki: bool = False, role: str = "full_access") -> bool:
        """为文档或知识库节点添加协作者
        
        Args:
            token: document_id (Docx) 或 node_token (Wiki)
            user_id: 用户的 open_id 或 union_id
            is_wiki: 是否为知识库节点
            role: 权限角色，full_access 为管理权限，edit 为编辑，view 为阅读
        """
        access_token = self._get_tenant_access_token()
        if not access_token:
            return False

        # 飞书权限 API 地址：驱动权限 v1
        # 对于 Wiki 节点，需要使用特定的 Wiki 权限接口，或者先获取 obj_token
        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{token}/members?type=docx"
        if is_wiki:
             url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{token}/members?type=wiki"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "member_type": "userid", # 飞书 API 规范中对应管理员 ID 格式 (如 g3a82bc1) 的类型通常是 userid
            "member_id": user_id,
            "perm": role # full_access, edit, view
        }

        try:
            logger.info(f"正在为飞书文档 {token} 添加协作者 {user_id} (权限: {role})...")
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            res_data = resp.json()
            if res_data.get("code") == 0:
                logger.info(f"✅ 成功赋予用户 {user_id} 文档管理权限。")
                return True
            else:
                # 记录详细错误以供排查
                logger.warning(f"添加协作者失败 (Code {res_data.get('code')}): {res_data.get('msg')}")
                if res_data.get("code") == 1063001:
                    logger.error("参数校验失败，请检查 FEISHU_OWNER_USER_ID 是否为有效的 open_id。")
                return False
        except Exception as e:
            logger.error(f"添加协作者异常: {e}")
            return False

    def transfer_owner(self, token: str, new_owner_id: str, is_wiki: bool = False, doc_type: str = "docx") -> bool:
        """转移文档所有权给指定用户（带重试机制）。这是突破父级文件夹删除限制的关键。
        
        Args:
            token: document_id (Docx) 或 node_token (Wiki)
            new_owner_id: 用户的 open_id 或 userid
            is_wiki: 是否为知识库节点
            doc_type: 默认 docx
        """
        access_token = self._get_tenant_access_token()
        if not access_token:
            return False

        # 飞书官方新版转移所有权 API
        # POST https://open.feishu.cn/open-apis/drive/v1/permissions/:token/members/transfer_owner
        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{token}/members/transfer_owner?type={doc_type}"
        if is_wiki:
            url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{token}/members/transfer_owner?type=wiki"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "member_type": "userid",
            "member_id": new_owner_id,
            "remove_old_owner": False
        }

        try:
            logger.info(f"正在将飞书文档 {token} 的所有权移交给用户 {new_owner_id}...")
            # 转移所有权接口容易遇到并发限制或延迟，增加超时
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            res_data = resp.json()
            if res_data.get("code") == 0:
                logger.info(f"✅ 成功将文档所有权移交给用户: {new_owner_id}。用户现已获得彻底删除权。")
                return True
            else:
                logger.warning(f"移交所有权失败 (Code {res_data.get('code')}): {res_data.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"移交所有权异常: {e}")
            return False

    def set_public_sharing(self, token: str, is_wiki: bool = False) -> bool:
        """设置文档为互联网公开访问 (所有人可阅读)
        
        Args:
            token: document_id (Docx) 或 node_token (Wiki)
            is_wiki: 是否为知识库节点
        """
        access_token = self._get_tenant_access_token()
        if not access_token:
            return False

        # 飞书公共权限 API：驱动权限 v1
        # 必须带上 ?type=docx 或 ?type=wiki 分辨类型，否则报 99992402 参数校验失败
        url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{token}/public?type=docx"
        if is_wiki:
            url = f"https://open.feishu.cn/open-apis/drive/v1/permissions/{token}/public?type=wiki"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # 配置含义：
        # external_access: true (允许非组织成员访问)
        # link_share_entity: anyone_readable (链接分享：互联网所有人可阅读 - V1 规范)
        payload = {
            "external_access": True,
            "link_share_entity": "anyone_readable" 
        }

        try:
            logger.info(f"正在开启飞书文档 {token} 的外部公开访问权限...")
            resp = requests.patch(url, headers=headers, json=payload, timeout=10)
            res_data = resp.json()
            if res_data.get("code") == 0:
                logger.info("✅ 成功开启互联网公开访问权限。")
                return True
            else:
                logger.warning(f"开启公开访问失败 (Code {res_data.get('code')}): {res_data.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"设置公开访问权限异常: {e}")
            return False

# ==========================================
# 辅助构建飞书 Block 的工具库
# ==========================================
class FeishuBlockBuilder:
    @staticmethod
    def header(text: str, level: int = 1) -> Dict[str, Any]:
        """构建标题 Block (1-9)"""
        block_type = max(1, min(9, level))
        return {
            "block_type": block_type + 2, # heading1 type=3, heading2 type=4, ...
            f"heading{block_type}": {
                "elements": [{"text_run": {"content": text}}]
            }
        }

    @staticmethod
    def heading_elements(elements: List[Dict[str, Any]], level: int = 1) -> Dict[str, Any]:
        """构建全自定义样式的标题 Block"""
        block_type = max(1, min(9, level))
        return {
            "block_type": block_type + 2,
            f"heading{block_type}": {
                "elements": elements
            }
        }

    @staticmethod
    def paragraph(text: str) -> Dict[str, Any]:
        """构建普通段落文本 Block"""
        if not text:
            text = " "  # 飞书文本节点严禁内容数组为空，此处用空格进行物理换行
        
        return {
            "block_type": 2, # text
            "text": {
                "elements": [{"text_run": {"content": text}}]
            }
        }

    @staticmethod
    def paragraph_rich(elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建富文本段落 Block，允许复杂的彩色文字或链接混合"""
        return {
            "block_type": 2, # text
            "text": {
                "elements": elements
            }
        }

    @staticmethod
    def paragraph_with_link(text: str, link_url: str) -> Dict[str, Any]:
        """段落包含链接"""
        return {
            "block_type": 2, # text
            "text": {
                "elements": [{"text_run": {"content": text, "text_element_style": {"link": {"url": link_url}}}}]
            }
        }

    @staticmethod
    def ordered_list(text: str, link_url: str = None) -> Dict[str, Any]:
        """构建有序列表 Block，可选支持超链接"""
        element = {"text_run": {"content": text}}
        if link_url:
            element["text_run"]["text_element_style"] = {"link": {"url": link_url}}
            
        return {
            "block_type": 13, # ordered
            "ordered": {
                "elements": [element]
            }
        }

    @staticmethod
    def parse_markdown_bold(text: str) -> List[Dict[str, Any]]:
        """解析 Markdown 加粗语法 **text** 为飞书富文本 elements"""
        import re
        parts = re.split(r'(\*\*.*?\*\*)', text)
        elements = []
        for part in parts:
            if not part: continue
            if part.startswith('**') and part.endswith('**'):
                content = part[2:-2]
                elements.append({"text_run": {"content": content, "text_element_style": {"bold": True}}})
            else:
                elements.append({"text_run": {"content": part}})
        return elements

    @staticmethod
    def bullet_list_rich(text: str) -> Dict[str, Any]:
        """构建支持 Markdown 加粗的高级无序列表 Blocks"""
        return {
            "block_type": 12, # bullet
            "bullet": {
                "elements": FeishuBlockBuilder.parse_markdown_bold(text)
            }
        }

    @staticmethod
    def bullet_list(items: List[str]) -> List[Dict[str, Any]]:
        """构建无序列表 Blocks"""
        return [
            FeishuBlockBuilder.bullet_list_rich(item) for item in items
        ]

    @staticmethod
    def divider() -> Dict[str, Any]:
        """构建分割线 Block"""
        return {
            "block_type": 22, # divider
            "divider": {}
        }

    @staticmethod
    def image(image_token: str) -> Dict[str, Any]:
        """构建图片 Block（使用 image_key 字段，非 token）
        
        注意：飞书 Docx V1 创建块接口实际接收 {"image_key": "..."} 而非 SDK 中的 {"token": "..."}
        这是官方文档与 SDK 不一致的 Bug，必须使用正确字段名才能避免 1770001 invalid param。
        """
        return {
            "block_type": 27,  # image
            "image": {
                "image_key": image_token
            }
        }
