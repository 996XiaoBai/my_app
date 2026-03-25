import requests
from requests.auth import HTTPBasicAuth
import logging
import re

class TAPDClient:
    """TAPD API 简单封装客户端"""
    
    BASE_URL = "https://api.tapd.cn"
    
    @staticmethod
    def parse_story_id(input_str: str) -> str:
        """
        Extract story ID from URL or return as is.
        Supported formats:
        - 1120340332001008677
        - https://www.tapd.cn/20340332/stories/view/1120340332001008677
        - .../prong/stories/view/1120340332001008677
        """
        if not input_str:
            return None

        normalized = str(input_str).strip()
        if not normalized:
            return None

        if re.fullmatch(r"\d+", normalized):
            return normalized

        # Check if it's a URL
        if normalized.startswith("http"):
            if "tapd.cn" not in normalized.lower():
                return None
            # Match .../view/123456...
            match = re.search(r'/view/(\d+)', normalized)
            if match:
                return match.group(1)
            # Match ...?story_id=123456...
            match = re.search(r'[?&]story_id=(\d+)', normalized)
            if match:
                return match.group(1)

            return None

        # fallback: plain text containing story_id=123456
        match = re.search(r'story_id=(\d+)', normalized)
        if match:
            return match.group(1)

        return None
    
    def __init__(self, api_user: str, api_password: str, workspace_id: str):
        self.auth = HTTPBasicAuth(api_user, api_password)
        self.workspace_id = workspace_id
        
    def get_story(self, story_id: str):
        """
        获取需求详情
        :param story_id: 需求 ID
        :return: (bool, data/error_msg)
        """
        url = f"{self.BASE_URL}/stories"
        params = {
            "workspace_id": self.workspace_id,
            "id": story_id
        }
        
        try:
            response = requests.get(url, params=params, auth=self.auth, timeout=10)
            result = response.json()
            
            if response.status_code == 200 and result.get("status") == 1:
                stories = result.get("data", [])
                if stories:
                    story = stories[0].get("Story", {})
                    # Format content
                    title = story.get("name", "")
                    desc = story.get("description", "")
                    status = story.get("status", "")
                    return True, f"【需求标题】{title}\n【状态】{status}\n【需求描述】\n{desc}"
                else:
                    return False, "未找到该需求 ID"
            else:
                error_msg = result.get("info", "未知错误")
                return False, f"API Error: {error_msg}"
        except Exception as e:
            return False, f"Request Exception: {str(e)}"

    def create_bug(self, title: str, description: str, **kwargs):
        """
        创建缺陷
        :param title: 缺陷标题
        :param description: 缺陷描述 (支持 HTML)
        :param kwargs: 其他字段，如 priority, severity, module 等
        :return: (bool, message/bug_id)
        """
        url = f"{self.BASE_URL}/bugs"
        
        # TAPD 基本参数要求
        data = {
            "workspace_id": self.workspace_id,
            "title": title,
            "description": description,
        }
        
        # 合并自定义参数
        data.update(kwargs)
        
        try:
            response = requests.post(url, data=data, auth=self.auth, timeout=10)
            result = response.json()
            
            if response.status_code == 200 and result.get("status") == 1:
                bug_id = result.get("data", {}).get("Bug", {}).get("id")
                return True, bug_id
            else:
                error_msg = result.get("info", "未知错误")
                return False, f"API Error: {error_msg} (Status: {response.status_code})"
        except Exception as e:
            return False, f"Request Exception: {str(e)}"

    def get_bug_url(self, bug_id: str):
        """获取 Bug 的 Web 访问链接"""
        return f"https://www.tapd.cn/{self.workspace_id}/bugtrace/bugs/view?bug_id={bug_id}"

    @staticmethod
    def map_priority(ui_priority: str):
        """将 UI 的优先级映射到 TAPD 的值 (示例)"""
        # TAPD 优先级通常是: "low", "medium", "high", "urgent"
        mapping = {
            "P0 (紧急)": "urgent",
            "P1 (高)": "high",
            "P2 (中)": "medium",
            "P3 (低)": "low"
        }
        return mapping.get(ui_priority, "medium")

    @staticmethod
    def map_severity(ui_severity: str):
        """将 UI 的严重程度映射到 TAPD 的值 (示例)"""
        # TAPD 严重程度通常是: "fatal", "serious", "normal", "slight"
        mapping = {
            "致命": "fatal",
            "严重": "serious",
            "一般": "normal",
            "轻微": "slight"
        }
        return mapping.get(ui_severity, "normal")
