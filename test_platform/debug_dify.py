import os
import sys
import logging
from dotenv import load_dotenv

# 设置导包路径
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from test_platform.config import (
    get_test_platform_dify_api_base,
    get_test_platform_dify_api_key,
    get_test_platform_dify_user_id,
)
from test_platform.services.dify_client import DifyClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_dify():
    load_dotenv()
    api_base = get_test_platform_dify_api_base()
    api_key = get_test_platform_dify_api_key()
    user_id = get_test_platform_dify_user_id("test_user")

    if not api_base or not api_key:
        print("未找到测试平台 Dify 配置，请检查 DIFY_API_BASE 与 TEST_PLATFORM_DIFY_API_KEY/DIFY_API_KEY")
        return
    
    print(f"Testing Dify with Base: {api_base}")
    print(f"Key Prefix: {api_key[:10]}...")
    
    client = DifyClient(api_base, api_key, user_id)
    prompt = "你好，请回复'连接成功'"
    
    print("Sending request...")
    result = client.generate_completion(prompt)
    print(f"Result: {result}")

if __name__ == "__main__":
    test_dify()
