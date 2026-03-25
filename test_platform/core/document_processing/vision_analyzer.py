import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from test_platform.services.dify_client import DifyClient

logger = logging.getLogger(__name__)

@dataclass
class VisionMediaRef:
    """视觉媒体资源引用契约"""
    provider: str                # 供应商名称 (如 "dify", "openai", "mock")
    success: bool                # 是否准备成功
    media_id: Optional[str] = None   # 平台内部文件 ID
    media_url: Optional[str] = None  # 外部访问 URL
    error_message: Optional[Optional[str]] = None
    latency_ms: Optional[int] = None # 耗时埋点 (P1 可观测性)
    raw_response: Optional[Dict[str, Any]] = None # 原始响应存档

class VisionAnalyzer(ABC):
    """
    视觉分析抽象基类。
    隔离具体平台实现，为 DocumentService 提供统一的媒体准备与分析能力。
    """
    
    @abstractmethod
    def prepare_page_media(self, image_path: str) -> VisionMediaRef:
        """上传并准备页面媒体资源"""
        pass

    def analyze_page(self, image_path: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        """可选：直接分析页面"""
        return {}

class DifyVisionAnalyzer(VisionAnalyzer):
    """Dify 视觉分析适配器"""
    
    def __init__(self, client: DifyClient, user_id: str, max_retries: int = 2):
        self.client = client
        self.user_id = user_id
        self.max_retries = max_retries

    def prepare_page_media(self, image_path: str) -> VisionMediaRef:
        start_time = time.time()
        last_error = ""
        
        for attempt in range(self.max_retries + 1):
            try:
                # 记录打点：开始上传
                file_id = self.client.upload_file(image_path, self.user_id)
                latency = int((time.time() - start_time) * 1000)
                
                if file_id:
                    return VisionMediaRef(
                        provider="dify",
                        success=True,
                        media_id=file_id,
                        latency_ms=latency
                    )
                else:
                    last_error = "Dify 返回空 file_id"
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    logger.warning(f"Dify upload retry {attempt+1}/{self.max_retries} due to: {e}")
                    time.sleep(1)
        
        latency = int((time.time() - start_time) * 1000)
        return VisionMediaRef(
            provider="dify",
            success=False,
            error_message=last_error,
            latency_ms=latency
        )

class MockVisionAnalyzer(VisionAnalyzer):
    """用于测试与降级的 Mock 适配器"""
    
    def prepare_page_media(self, image_path: str) -> VisionMediaRef:
        return VisionMediaRef(
            provider="mock",
            success=True,
            media_id=f"mock_id_{int(time.time())}",
            latency_ms=10
        )
