import requests
import os
import json
import time
import logging
from typing import Optional, Any, Dict

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
        self.max_retries = self._read_int_env("DIFY_RATE_LIMIT_MAX_RETRIES", 5, minimum=1)
        self.base_delay_seconds = self._read_int_env("DIFY_RATE_LIMIT_BASE_DELAY_SECONDS", 2, minimum=1)
        self.max_delay_seconds = self._read_int_env("DIFY_RATE_LIMIT_MAX_DELAY_SECONDS", 30, minimum=1)
        self.cooldown_seconds = self._read_int_env("DIFY_RATE_LIMIT_COOLDOWN_SECONDS", 20, minimum=0)
        if self.max_delay_seconds < self.base_delay_seconds:
            self.max_delay_seconds = self.base_delay_seconds

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
        
        try:
            with open(file_path, 'rb') as f:
                upload_files = {
                    'file': (os.path.basename(file_path), f, 'image/jpeg')
                }
                data = {
                    'user': user
                }
                logger.info(f"上传文件到 Dify: {url}")
                response = requests.post(url, headers=headers, files=upload_files, data=data, timeout=30)

            if response.status_code in (200, 201):
                result = response.json()
                file_id = result.get('id')
                logger.info(f"文件上传成功， ID: {file_id}")
                return file_id
            else:
                logger.error(f"Dify 上传失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"上传文件到 Dify 时发生异常: {e}")
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
        max_retries = self.max_retries
        
        for attempt in range(max_retries):
            try:
                logger.info(f"请求 Dify API: {url} (第 {attempt + 1}/{max_retries} 次)")

                # 递增超时时间：60s 基础，每次重试递增 30s
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
                                    pass

                    if stream_error:
                        error_message = self._extract_error_message(stream_error)
                        is_rate_limit_error = self._is_rate_limit_error(stream_error.get("status"), error_message)
                        if self._is_retryable_error(stream_error.get("status"), error_message) and attempt < max_retries - 1:
                            sleep_time = self._calculate_retry_delay(attempt, is_rate_limit=is_rate_limit_error)
                            logger.warning(f"Dify 流式调用触发可重试错误，{sleep_time}s 后重试...")
                            time.sleep(sleep_time)
                            full_answer = ""
                            continue
                        if is_rate_limit_error:
                            raise DifyRateLimitError(self._build_rate_limit_message(error_message))
                        raise DifyRequestError(error_message)
                    return full_answer.strip()
                else:
                    error_message = self._extract_error_message({
                        "status": resp.status_code,
                        "message": resp.text[:500],
                    })
                    logger.warning(f"Dify API 返回异常状态码: {resp.status_code} - {resp.text[:200]}")
                    is_rate_limit_error = self._is_rate_limit_error(resp.status_code, error_message)
                    if self._is_retryable_error(resp.status_code, error_message) and attempt < max_retries - 1:
                        sleep_time = self._calculate_retry_delay(attempt, is_rate_limit=is_rate_limit_error)
                        logger.warning(f"服务端封流/超载，{sleep_time}s 后重试...")
                        time.sleep(sleep_time)
                        continue
                    if is_rate_limit_error:
                        raise DifyRateLimitError(self._build_rate_limit_message(error_message))
                    raise DifyRequestError(error_message)
            except requests.exceptions.Timeout:
                logger.warning(f"Dify API 请求超时 (第 {attempt + 1} 次)")
                if attempt < max_retries - 1:
                    sleep_time = self._calculate_retry_delay(attempt, is_rate_limit=False)
                    time.sleep(sleep_time)
                    continue
                else:
                    logger.error("达到最大超时重试次数，放弃请求")
                    raise DifyRequestError("Dify API 请求超时，已达到最大重试次数")
            except (DifyRequestError, DifyRateLimitError):
                raise
            except Exception as e:
                logger.error(f"调用 Dify API 时发生未知异常: {e}")
                raise DifyRequestError(f"调用 Dify API 时发生未知异常: {e}")
        return None

    def _extract_error_message(self, payload: Dict[str, Any]) -> str:
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

    def _build_rate_limit_message(self, message: str) -> str:
        normalized_message = str(message or "").strip()
        return (
            "Dify/Azure OpenAI 吞吐受限：当前 Provisioned-Managed 部署已超过吞吐上限，"
            "系统已自动重试但仍未恢复。请稍后重试，或降低并发、增加 PTU。"
            f" 原始信息：{normalized_message}"
        )

    def _calculate_retry_delay(self, attempt: int, is_rate_limit: bool) -> int:
        delay_seconds = min(self.base_delay_seconds * (2 ** attempt), self.max_delay_seconds)
        if is_rate_limit:
            return max(delay_seconds, self.cooldown_seconds)
        return delay_seconds

    def _read_int_env(self, env_name: str, default_value: int, minimum: int) -> int:
        raw_value = os.getenv(env_name)
        if raw_value is None or str(raw_value).strip() == "":
            return default_value
        try:
            parsed_value = int(str(raw_value).strip())
        except ValueError:
            logger.warning(f"环境变量 {env_name}={raw_value} 无法解析为整数，回退为默认值 {default_value}")
            return default_value
        if parsed_value < minimum:
            logger.warning(f"环境变量 {env_name}={raw_value} 小于最小值 {minimum}，回退为默认值 {default_value}")
            return default_value
        return parsed_value

if __name__ == "__main__":
    # 手动调试入口
    from dotenv import load_dotenv
    from test_platform.config import (
        get_test_platform_dify_api_base,
        get_test_platform_dify_api_key,
        get_test_platform_dify_user_id,
    )

    load_dotenv()
    
    base = get_test_platform_dify_api_base()
    key = get_test_platform_dify_api_key()
    user_id = get_test_platform_dify_user_id("manual_debug")
    
    if base and key:
        client = DifyClient(base, key, user_id)
        res = client.summarize_content("Test AI News", "OpenAI just released GPT-5. It is very powerful.")
        print(f"Summary: {res}")
    else:
        print("缺少测试平台 Dify 凭证。")
