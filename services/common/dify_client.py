import requests
import os
import json
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DifyClient:
    def __init__(self, api_base: str, api_key: str, user_id: str):
        self.api_base = api_base
        self.api_key = api_key
        self.user_id = user_id

    def generate_completion(self, prompt: str, files: Optional[list] = None) -> Optional[str]:
        """
        Generic method to generate completion from Dify.
        Args:
            prompt: Text prompt
            files: List of dicts, e.g. [{"type": "image", "transfer_method": "local_file", "url": "base64_string"}]
        """
        return self._call_dify_api(prompt, files)

    def summarize_content(self, title: str, content: str) -> Optional[str]:
        """
        Calls Dify API to summarize/translate the given content.
        Uses streaming mode required for Agent apps.
        """
        # Construct prompt
        prompt = f"""
[标题]
(这里填写翻译后的中文标题)

[摘要]
(这里填写中文摘要，不超过 300 字)

[亮点]
(请严格遵循 wechat_article_style 技能的 News Daily 模板，提取 3 个关键点。
格式必须为：
* Emoji **关键词**: 描述
常用 Emoji：🔥(核心), 🚀(发布), 💰(融资), 🧠(模型), 🛡️(安全), 💡(观点).
)

标题: {title}
内容: {content}

要求：
1. 必须翻译标题。
2. 翻译准确，保留专业术语，适合微信公众号阅读。
3. 重点突出这篇新闻的核心价值。
4. 亮点部分必须使用 Emoji 列表格式。
"""
        return self._call_dify_api(prompt)

    def upload_file(self, file_path: str, user: str) -> Optional[str]:
        """
        Uploads a file to Dify and returns the file ID.
        """
        # Upload endpoint: /files/upload
        # Assuming base URL is like .../v1
        if self.api_base.endswith('/chat-messages'):
            base = self.api_base.replace('/chat-messages', '')
        else:
            base = self.api_base

        url = f"{base}/files/upload"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with open(file_path, 'rb') as f:
                    upload_files = {
                        'file': (os.path.basename(file_path), f, 'image/jpeg')
                    }
                    data = {
                        'user': user
                    }
                    logger.info(f"上传文件到 Dify: {url} (第 {attempt + 1}/{max_retries} 次)")
                    response = requests.post(url, headers=headers, files=upload_files, data=data, timeout=30 + (attempt * 10))

                if response.status_code in (200, 201):
                    result = response.json()
                    file_id = result.get('id')
                    logger.info(f"文件上传成功， ID: {file_id}")
                    return file_id
                else:
                    logger.warning(f"Dify 上传失败，状态码: {response.status_code} - {response.text}")
                    if response.status_code in (429, 502, 503, 504) and attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
            except requests.exceptions.Timeout:
                logger.warning(f"Dify 上传文件超时 (第 {attempt + 1} 次)")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
            except Exception as e:
                logger.error(f"上传文件到 Dify 时发生异常: {e}")
                return None
        return None

    def _call_dify_api(self, prompt: str, files: Optional[list] = None) -> Optional[str]:
        url = f"{self.api_base}/chat-messages"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Sanitize files payload: Remove empty upload_file_id
        if files:
            cleaned_files = []
            for f in files:
                new_f = {}
                for k, v in f.items():
                    if k == "upload_file_id" and not v:
                        continue
                    new_f[k] = v
                cleaned_files.append(new_f)
            files = cleaned_files

        payload = {
            "inputs": {},
            "query": prompt,
            "response_mode": "streaming", 
            "conversation_id": "",
            "user": self.user_id,
            "files": files or []
        }
        
        full_answer = ""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"请求 Dify API: {url} (第 {attempt + 1}/{max_retries} 次)")

                # 递增超时时间：60s 基础，每次重试递增 30s
                current_timeout = 60 + (attempt * 30)

                resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=current_timeout)

                if resp.status_code == 200:
                    for line in resp.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith('data: '):
                                json_str = decoded_line[6:]
                                try:
                                    data = json.loads(json_str)
                                    event = data.get('event')
                                    if event in ('agent_message', 'message'):
                                        full_answer += data.get('answer', '')
                                    elif event == 'error':
                                        logger.error(f"Dify Stream 返回错误事件: {data}")
                                except json.JSONDecodeError:
                                    pass
                                    
                    answer = full_answer.strip()
                    if not answer:
                        logger.warning(f"Dify API 响应为空 (状态码 200)，准备重试... (第 {attempt + 1} 次)")
                        if attempt < max_retries - 1:
                            time.sleep(min(2 ** attempt, 10))
                            continue
                        logger.error("达到最大重试次数，放弃请求 (响应始终为空)")
                        return None
                        
                    return answer
                else:
                    logger.warning(f"Dify API 返回异常状态码: {resp.status_code} - {resp.text[:200]}")
                    sleep_time = min(2 ** attempt, 10)  # 指数退避：1s, 2s, 4s ≤ 10s
                    if resp.status_code in (429, 502, 503, 504):
                        logger.warning(f"服务端限流或网关异常，{sleep_time}s 后重试...")
                        time.sleep(sleep_time)
                        continue
                    return None
            except requests.exceptions.Timeout:
                logger.warning(f"Dify API 请求超时 (第 {attempt + 1} 次)")
                sleep_time = min(2 ** attempt, 10)
                if attempt < max_retries - 1:
                    time.sleep(sleep_time)
                    continue
                else:
                    logger.error("达到最大超时重试次数，放弃请求")
                    return None
            except Exception as e:
                logger.error(f"调用 Dify API 时发生未知异常: {e}")
                return None
        return None

if __name__ == "__main__":
    # Test
    from dotenv import load_dotenv
    load_dotenv()
    
    base = os.getenv("DIFY_API_BASE")
    key = os.getenv("DIFY_API_KEY")
    
    if base and key:
        client = DifyClient(base, key, "test_user")
        res = client.summarize_content("Test AI News", "OpenAI just released GPT-5. It is very powerful.")
        print(f"Summary: {res}")
    else:
        print("Missing credentials for test.")
