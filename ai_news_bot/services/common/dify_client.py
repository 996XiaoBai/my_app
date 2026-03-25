import requests
import os
import json
import time
import logging
from typing import Optional, Any, Dict
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

logger = logging.getLogger(__name__)


class DifyRequestError(RuntimeError):
    """Dify 请求失败时抛出的统一异常。"""
    pass


class DifyRateLimitError(DifyRequestError):
    """Dify 因吞吐或限流失败时抛出的可识别异常。"""
    pass

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

    def summarize_content(self, title: str, content: str, prompt_template: Optional[str] = None) -> Optional[str]:
        """
        调用 Dify API 对文章进行评分与摘要。
        提示词由调用方动态提供以实现不同的评分与抽取维度的区分，
        如果没有传入，则使用基础的通用摘要提示词。
        """
        if prompt_template:
            prompt = prompt_template.format(title=title, content=content)
        else:
            prompt = f"""标题: {title}
内容: {content}

请严格遵守以下 JSON 格式返回，不要包含任何其他说明文字或 Markdown 标记：
{{
  "title": "(精炼后的中文标题，必须简洁专业且与标题主旨一致)",
  "summary": "(中文摘要，紧贴核心价值，不超过250字)",
  "highlights": "(提取3个核心看点。格式：'* [Emoji] **关键词**: 说明')",
  "score": (整数，1-10，文章价值越高分数越高),
  "category": "(文章所属类别)"
}}"""
        return self._call_dify_api(prompt)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(Exception))
    def upload_file(self, file_path: str, user: str) -> Optional[str]:
        """
        Uploads a file to Dify and returns the file ID. (with tenacity retry)
        """
        if self.api_base.endswith('/chat-messages'):
            base = self.api_base.replace('/chat-messages', '')
        else:
            base = self.api_base

        url = f"{base}/files/upload"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            with open(file_path, 'rb') as f:
                upload_files = {
                    'file': (os.path.basename(file_path), f, 'image/jpeg')
                }
                data = {'user': user}
                logger.info(f"上传文件到 Dify: {url}")
                response = requests.post(url, headers=headers, files=upload_files, data=data, timeout=30)
                response.raise_for_status()

            result = response.json()
            file_id = result.get('id')
            logger.info(f"文件上传成功， ID: {file_id}")
            return file_id
        except Exception as e:
            logger.error(f"上传文件到 Dify 异常: {e}")
            raise  # 触发 tenacity 重试

    def _call_dify_api(self, prompt: str, files: Optional[list] = None) -> Optional[str]:
        url = f"{self.api_base}/chat-messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        if files:
            cleaned_files = []
            for f in files:
                new_f = {k: v for k, v in f.items() if not (k == "upload_file_id" and not v)}
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
        
        max_retries = 3

        for attempt in range(max_retries):
            full_answer = ""
            try:
                logger.info(f"请求 Dify API: {url} (第 {attempt + 1}/{max_retries} 次)")
                current_timeout = 60 + (attempt * 30)
                resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=current_timeout)

                if resp.status_code == 200:
                    stream_error: Optional[Dict[str, Any]] = None
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
                                        stream_error = data
                                except json.JSONDecodeError:
                                    continue

                    if stream_error:
                        error_message = self._extract_error_message(stream_error)
                        if self._is_retryable_error(stream_error.get("status"), error_message) and attempt < max_retries - 1:
                            sleep_time = min(2 ** attempt, 10)
                            logger.warning(f"Dify 流式调用触发可重试错误，{sleep_time}s 后重试...")
                            time.sleep(sleep_time)
                            continue
                        if self._is_rate_limit_error(stream_error.get("status"), error_message):
                            raise DifyRateLimitError(error_message)
                        raise DifyRequestError(error_message)

                    answer = full_answer.strip()
                    if answer:
                        return answer
                    logger.warning("Dify API 响应为空载荷")
                    if attempt < max_retries - 1:
                        sleep_time = min(2 ** attempt, 10)
                        time.sleep(sleep_time)
                        continue
                    raise DifyRequestError("Empty Dify Response")

                error_message = self._extract_error_message(
                    {
                        "status": resp.status_code,
                        "message": getattr(resp, "text", "")[:500],
                    }
                )
                logger.warning(f"Dify API 返回异常状态码: {resp.status_code} - {getattr(resp, 'text', '')[:200]}")
                if self._is_retryable_error(resp.status_code, error_message) and attempt < max_retries - 1:
                    sleep_time = min(2 ** attempt, 10)
                    logger.warning(f"Dify 服务端封流或超载，{sleep_time}s 后重试...")
                    time.sleep(sleep_time)
                    continue
                if self._is_rate_limit_error(resp.status_code, error_message):
                    raise DifyRateLimitError(error_message)
                raise DifyRequestError(error_message)
            except requests.exceptions.Timeout:
                logger.warning(f"Dify API 请求超时 (第 {attempt + 1} 次)")
                if attempt < max_retries - 1:
                    sleep_time = min(2 ** attempt, 10)
                    time.sleep(sleep_time)
                    continue
                raise DifyRequestError("Dify API 请求超时，已达到最大重试次数")
            except (DifyRequestError, DifyRateLimitError):
                raise
            except Exception as e:
                logger.error(f"调用 Dify API 异常: {e}")
                raise DifyRequestError(f"调用 Dify API 异常: {e}")
        return None

    def _extract_error_message(self, payload: Dict[str, Any]) -> str:
        """从 Dify 错误载荷中提取可读错误信息。"""
        message = str(payload.get("message") or "").strip()
        status = payload.get("status")
        if status and message:
            return f"Dify 调用失败（{status}）：{message}"
        if message:
            return message
        if status:
            return f"Dify 调用失败（{status}）"
        return "Dify 调用失败"

    def _is_retryable_error(self, status_code: Optional[Any], message: str) -> bool:
        """判断当前错误是否适合重试。"""
        normalized_message = str(message or "").lower()
        if status_code in (429, 502, 503, 504):
            return True
        retryable_keywords = (
            "bad gateway",
            "openresty",
            "throughput limit",
            "rate limit",
            "temporarily unavailable",
            "try again later",
            "overloaded",
        )
        return any(keyword in normalized_message for keyword in retryable_keywords)

    def _is_rate_limit_error(self, status_code: Optional[Any], message: str) -> bool:
        """判断是否是吞吐或限流导致的错误。"""
        normalized_message = str(message or "").lower()
        if status_code == 429:
            return True
        rate_limit_keywords = (
            "throughput limit",
            "rate limit",
            "provisioned-managed deployment",
            "too many requests",
        )
        return any(keyword in normalized_message for keyword in rate_limit_keywords)

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
