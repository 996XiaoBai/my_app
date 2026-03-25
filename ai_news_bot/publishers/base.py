from abc import ABC, abstractmethod
from typing import Dict, Any, List

class PublisherBase(ABC):
    """
    发布平台基类，所有具体的发布渠道（如飞书、企业微信、钉钉）必须继承此基类。
    """

    @abstractmethod
    def publish(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        核心发布方法
        :param title: 文章或消息的标题
        :param content: 文章的主体内容（Markdown 格式）
        :param kwargs: 其他渠道特定的参数
        :return: 包含发布结果状态和相关链接的字典，例如 {"success": True, "url": "..."}
        """
        pass
