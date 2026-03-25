from typing import List, Dict, Any, Type
import logging

from publishers.base import PublisherBase
from publishers.feishu import FeishuPublisher, FeishuBlockBuilder
from publishers.wecom import WeComPublisher

logger = logging.getLogger(__name__)

class PublisherFactory:
    """
    发布端架构的工厂类，统一管理和调度所有启用的发布渠道。
    """
    def __init__(self):
        self.publishers: List[PublisherBase] = []
        
    def add_publisher(self, publisher: PublisherBase):
        """注册一个发布渠道"""
        self.publishers.append(publisher)
        return self
        
    def publish_all(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        """
        分发消息到所有已注册的发布渠道
        :param title: 消息标题
        :param content: 消息文本正文
        :param kwargs: 其他扩展参数，如飞书特有的 `blocks` 或企微需要的 `doc_url`
        :return: 合并各个渠道发布的返回状态字典
        """
        results = {}
        for pub in self.publishers:
            pub_name = pub.__class__.__name__
            try:
                res = pub.publish(title=title, content=content, **kwargs)
                results[pub_name] = res
                
                # 特殊逻辑共享：如果飞书先发布成功，拿到了 doc_url，则补充进 kwargs 让下一个渠道（比如企微）能用作超链接
                if pub_name == 'FeishuPublisher' and res.get('success'):
                    kwargs['doc_url'] = res.get('url')
                    kwargs['doc_id'] = res.get('doc_id')
                    
            except Exception as e:
                logger.error(f"Publisher {pub_name} failed: {e}")
                results[pub_name] = {"success": False, "error": str(e)}
                
        return results

# 暴露常用的内部构建工具，方便上游调用
__all__ = [
    'PublisherBase',
    'FeishuPublisher',
    'WeComPublisher',
    'PublisherFactory',
    'FeishuBlockBuilder'
]
