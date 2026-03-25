import os
import json
import logging
import base64
import tempfile
import time
import uuid
import re
import html
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, Any, cast
from concurrent.futures import ThreadPoolExecutor, as_completed
import tiktoken
from test_platform.services.dify_client import DifyClient
from test_platform.infrastructure.tapd_client import TAPDClient  # type: ignore
from test_platform.core.document_processing.pdf_text_extractor import PageContent  # type: ignore
from test_platform.config import AgentConfig
from test_platform.core.skill_modes import SkillMode, SKILL_NAME_MAP
from test_platform.core.db.db_manager import db_manager  # type: ignore
from test_platform.core.services.case_design_service import CaseDesignService
from test_platform.core.services.flowchart_service import FlowchartService
from test_platform.core.services.requirement_analysis_service import RequirementAnalysisService
from test_platform.core.services.requirement_context_service import RequirementContextService
from test_platform.core.services.review_result_service import ReviewResultService
from test_platform.core.services.test_data_preparation_service import TestDataPreparationService
from test_platform.core.services.test_case_review_service import TestCaseReviewService
from test_platform.core.services.result_contracts import build_api_test_pack, sanitize_mermaid_code
from test_platform.core.services.openapi_asset_service import OpenApiAssetService
from test_platform.core.services.api_case_service import ApiCaseService
from test_platform.core.services.api_test_execution_service import ApiTestExecutionService
from test_platform.core.services.api_linking_service import ApiLinkingService
from test_platform.core.services.api_report_service import ApiReportService
from test_platform.core.services.api_suite_repository import ApiSuiteRepository
from test_platform.core.document_processing.vision_analyzer import DifyVisionAnalyzer
from test_platform.core.services.document_service import DocumentService
from test_platform.utils.json_utils import parse_json_markdown  # type: ignore
from logging.handlers import RotatingFileHandler
 
# 日志配置
log_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # 限制每文件 10MB，保留 5 个备份文件
        RotatingFileHandler(log_file_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ReviewExecutionContext:
    context: Dict[str, Any]
    modules: List[Dict[str, Any]]
    combined_text: str
    vision_files_map: Dict[int, Dict[str, Any]]
    pages: List[Any]
    page_texts: Dict[int, str]
    file_basename: str
    req_text: str
    full_context: str
    all_modules_summary: str
    all_images: List[Dict[str, Any]]


class ReviewService:
    # Dify API 限制：单次请求最多 3 张图片
    DIFY_MAX_IMAGES = 3
    DEFAULT_LLM_CONTEXT_WINDOW_TOKENS = 1_050_000
    DEFAULT_LLM_RESERVED_OUTPUT_TOKENS = 128_000
    DEFAULT_LLM_RESERVED_PROMPT_TOKENS = 32_000
    DEFAULT_LLM_MAX_PROMPT_INPUT_TOKENS = 60_000
    DEFAULT_LLM_TOKENIZER_ENCODING = "o200k_base"
    TOKEN_BUDGET_SAFETY_MARGIN = 32
    SIMPLE_SKILL_MAX_ENDPOINTS = 40
    SIMPLE_SKILL_MAX_PARAMS = 12
    SIMPLE_SKILL_MAX_RESPONSE_CODES = 8
    SIMPLE_SKILL_MAX_TEXT_LINES = 240
    
    # 线程池并发控制 (避免触发大模型限流)
    DEFAULT_MAX_WORKERS_SINGLE_ROLE = 1
    DEFAULT_MAX_WORKERS_MULTI_ROLE = 1
    ROLE_FOCUS_HINTS: Dict[str, str] = {
        "product": "请严格站在产品视角评审，重点关注需求目标、业务闭环、规则歧义、范围边界与验收标准是否充分。",
        "tech": "请严格站在技术视角评审，重点关注系统边界、实现复杂度、依赖关系、异常处理、一致性与可维护性风险。",
        "design": "请严格站在设计视角评审，重点关注交互流程、状态反馈、信息层级、误操作防护与界面一致性问题。",
        "test": "请严格站在测试视角评审，重点关注可测性、边界条件、异常分支、逆向流程、测试准备与覆盖缺口。",
        "security": "请严格站在安全视角评审，重点关注鉴权、越权、敏感信息保护、输入校验、风控绕过与资损风险。",
        "architect": "请严格站在架构仲裁视角评审，重点识别多方意见冲突，综合形成取舍清晰、可执行的最终结论。",
    }

    def __init__(self):
        self.config = AgentConfig
        self.config.validate()
        self.max_workers_single_role = self._resolve_worker_limit(
            env_name="REVIEW_MAX_WORKERS_SINGLE_ROLE",
            default_value=self.DEFAULT_MAX_WORKERS_SINGLE_ROLE,
        )
        self.max_workers_multi_role = self._resolve_worker_limit(
            env_name="REVIEW_MAX_WORKERS_MULTI_ROLE",
            default_value=self.DEFAULT_MAX_WORKERS_MULTI_ROLE,
        )
        self.tokenizer_encoding = str(
            os.getenv("LLM_TOKENIZER_ENCODING", self.DEFAULT_LLM_TOKENIZER_ENCODING)
        ).strip() or self.DEFAULT_LLM_TOKENIZER_ENCODING
        self.context_window_tokens = self._resolve_env_int(
            env_name="LLM_CONTEXT_WINDOW_TOKENS",
            default_value=self.DEFAULT_LLM_CONTEXT_WINDOW_TOKENS,
            minimum=1,
        )
        self.reserved_output_tokens = self._resolve_env_int(
            env_name="LLM_RESERVED_OUTPUT_TOKENS",
            default_value=self.DEFAULT_LLM_RESERVED_OUTPUT_TOKENS,
            minimum=0,
        )
        self.reserved_prompt_tokens = self._resolve_env_int(
            env_name="LLM_RESERVED_PROMPT_TOKENS",
            default_value=self.DEFAULT_LLM_RESERVED_PROMPT_TOKENS,
            minimum=0,
        )
        self.max_prompt_input_tokens = self._resolve_env_int(
            env_name="LLM_MAX_PROMPT_INPUT_TOKENS",
            default_value=self.DEFAULT_LLM_MAX_PROMPT_INPUT_TOKENS,
            minimum=1,
        )
        self.prompt_input_budget_tokens = max(
            1,
            min(
                self.context_window_tokens - self.reserved_output_tokens - self.reserved_prompt_tokens,
                self.max_prompt_input_tokens,
            ),
        )
        self.tokenizer = self._load_tokenizer(self.tokenizer_encoding)
        self.client = DifyClient(
            self.config.DIFY_API_BASE,
            self.config.DIFY_API_KEY,
            self.config.DIFY_USER_ID
        )
        self.case_design_service = CaseDesignService()
        self.flowchart_service = FlowchartService()
        self.requirement_analysis_service = RequirementAnalysisService()
        self.context_service = RequirementContextService(
            module_identifier=self._identify_modules,
            pdf_context_builder=self._build_pdf_context,
        )
        self.review_result_service = ReviewResultService()
        self.test_data_preparation_service = TestDataPreparationService()
        self.test_case_review_service = TestCaseReviewService()
        self.openapi_asset_service = OpenApiAssetService()
        self.api_case_service = ApiCaseService()
        self.api_linking_service = ApiLinkingService()
        self.api_test_execution_service = ApiTestExecutionService()
        self.api_report_service = ApiReportService()
        self.api_suite_repository = ApiSuiteRepository()
        
        # 初始化 TAPD 客户端（可选）
        if self.config.TAPD_API_USER and self.config.TAPD_API_PASSWORD:
            self.tapd_client = TAPDClient(
                self.config.TAPD_API_USER,
                self.config.TAPD_API_PASSWORD,
                self.config.TAPD_WORKSPACE_ID
            )
        else:
            self.tapd_client = None
            logger.warning("TAPD credentials not found. TAPD features disabled.")
            
        self.review_roles = self._load_roles_config()

    def _resolve_worker_limit(self, env_name: str, default_value: int) -> int:
        return self._resolve_env_int(env_name, default_value, minimum=1)

    def _resolve_env_int(self, env_name: str, default_value: int, minimum: int) -> int:
        raw_value = os.getenv(env_name)
        if raw_value is None:
            return default_value

        try:
            parsed_value = int(raw_value)
        except ValueError:
            logger.warning(f"{env_name} 配置非法，已回退到默认值 {default_value}: {raw_value}")
            return default_value

        if parsed_value < minimum:
            logger.warning(f"{env_name} 小于 {minimum}，已回退到默认值 {default_value}: {raw_value}")
            return default_value
        return parsed_value

    def _load_tokenizer(self, encoding_name: str) -> Any:
        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception as error:
            logger.warning(f"Tokenizer 编码 {encoding_name} 不可用，已回退到本地近似分词: {error}")
            return None

    def _fallback_tokenize(self, text: str) -> List[str]:
        return re.findall(r"\s+|[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\w\s]", str(text or ""))

    def _encode_text_tokens(self, text: str) -> List[Any]:
        if self.tokenizer is None:
            return cast(List[Any], self._fallback_tokenize(text))
        return cast(List[Any], self.tokenizer.encode(str(text or "")))

    def _decode_text_tokens(self, tokens: List[Any]) -> str:
        if self.tokenizer is None:
            return "".join(str(token) for token in tokens)
        return cast(str, self.tokenizer.decode(cast(List[int], tokens)))

    def _count_text_tokens(self, text: str) -> int:
        return len(self._encode_text_tokens(text))

    def _trim_text_by_token_budget(
        self,
        text: str,
        max_tokens: int,
        preserve_tail: bool = False,
        truncation_notice: str = "",
    ) -> str:
        raw_text = str(text or "")
        text_tokens = self._encode_text_tokens(raw_text)
        if len(text_tokens) <= max_tokens:
            return raw_text

        notice_block = truncation_notice if truncation_notice else ""
        notice_tokens = self._encode_text_tokens(notice_block) if notice_block else []
        available_text_tokens = max(1, max_tokens - len(notice_tokens))

        if preserve_tail:
            head_tokens = max(1, int(available_text_tokens * 0.7))
            tail_tokens = max(1, available_text_tokens - head_tokens)
            if head_tokens + tail_tokens > len(text_tokens):
                return raw_text
            return (
                f"{self._decode_text_tokens(text_tokens[:head_tokens])}"
                f"{notice_block}"
                f"{self._decode_text_tokens(text_tokens[-tail_tokens:])}"
            )

        return self._decode_text_tokens(text_tokens[:available_text_tokens])

    def _trim_text_for_prompt_slot(
        self,
        text: str,
        prompt_prefix: str = "",
        prompt_suffix: str = "",
        preserve_tail: bool = False,
        truncation_notice: str = "",
    ) -> str:
        available_tokens = (
            self.prompt_input_budget_tokens
            - self._count_text_tokens(prompt_prefix)
            - self._count_text_tokens(prompt_suffix)
            - self.TOKEN_BUDGET_SAFETY_MARGIN
        )
        return self._trim_text_by_token_budget(
            text=text,
            max_tokens=max(1, available_tokens),
            preserve_tail=preserve_tail,
            truncation_notice=truncation_notice,
        )

    def _load_roles_config(self) -> Dict:
        """从配置文件加载评审角色定义。"""
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'roles.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load roles config from {config_path}: {e}")
            return {}
    
    def load_skill(self, skill_name: str) -> Optional[str]:
        """加载指定技能的提示词。支持重构后的动态回流映射。"""
        # 1. 自动回流映射：如果请求的是已被整合的旧技能，直接映射至新全能专家
        LEGACY_MAPPING = {
            "review_test": "requirement_expert_reviewer",
            "review_product": "requirement_expert_reviewer",
            "review_tech": "requirement_expert_reviewer",
            "review_security": "requirement_expert_reviewer",
            "review_design": "requirement_expert_reviewer",
            "business_flowchart_expert": "flowchart_master"
        }
        
        target_skill = LEGACY_MAPPING.get(skill_name, skill_name)
        skill_path = self.config.get_skill_path(target_skill)
        
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    return parts[2].strip()
                return content
        except FileNotFoundError:
            # 2. 增强容错：如果文件依然找不到，且含有 review 关键字，降级至全能专家
            if "review" in skill_name.lower() and skill_name != "requirement_expert_reviewer":
                logger.warning(f"Skill {skill_name} not found, falling back to requirement_expert_reviewer")
                return self.load_skill("requirement_expert_reviewer")
            
            logger.error(f"Skill file not found: {skill_path}")
            return None
        except Exception as e:
            logger.error(f"Error loading skill {skill_name}: {e}")
            return None

    # ================================================================
    # 辅助功能
    # ================================================================

    def fetch_requirement_from_tapd(self, story_id: str) -> Optional[str]:
        """从 TAPD 获取需求详情。"""
        if not self.tapd_client:
            logger.error("TAPD Client not initialized.")
            return None
        logger.info(f"Fetching story {story_id} from TAPD...")
        success, result = self.tapd_client.get_story(story_id)
        if success:
            return result
        else:
            logger.error(f"Failed to fetch story: {result}")
            return None

    def _build_pdf_context(self, file_path: str, max_pages: int) -> Dict[str, Any]:
        document_service = DocumentService(
            vision_analyzer=DifyVisionAnalyzer(
                client=self.client,
                user_id=self.config.DIFY_USER_ID,
            )
        )
        combined_text, vision_files_map, pages = document_service.process_file(file_path, max_pages=max_pages)
        page_texts_map = {
            page.page_num: page.text
            for page in pages
            if getattr(page, "text", "")
        }
        return {
            "combined_text": combined_text,
            "vision_files_map": vision_files_map,
            "pages": pages,
            "page_texts": page_texts_map,
        }

    def _extract_file_content(self, file_path: str) -> str:
        """从各种格式的文件中提取文本内容。"""
        if not file_path or not os.path.exists(file_path):
            return ""
        
        if file_path.lower().endswith('.pdf'):
            try:
                import pdfplumber  # type: ignore
                with pdfplumber.open(file_path) as pdf:
                    return "\n\n".join([p.extract_text() or "" for p in pdf.pages])
            except Exception as e:
                logger.error(f"Failed to extract PDF: {e}")
                return ""
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read file: {e}")
                return ""

    def recommend_experts(self, requirement_text: str) -> List[str]:
        """根据需求内容推荐评审专家角色。"""
        if not requirement_text:
            return ["product", "test"] # 默认兜底
            
        role_definitions = ""
        for rid, info in self.review_roles.items():
            role_definitions += f"- {rid}: {info['label']}\n"
            
        safe_req: Any = requirement_text or ""
        req_snippet = str(safe_req)[:2000]  # type: ignore
        
        prompt = f"""分析以下需求内容，从以下角色列表中推荐最适合进行评审的 2-4 个角色。
如果是金融/支付相关，务必包含 security。
如果是纯 UI/交互，务必包含 design。
如果是后端逻辑/架构变更，务必包含 tech。

角色列表：
{role_definitions}

需求内容（前 2000 字）：
{req_snippet}

请直接以 JSON 数组形式返回角色 ID（如 ["product", "tech"]），不要包含任何其他说明文字："""

        logger.info("🔮 正在智能推荐专家角色...")
        try:
            response = self.client.generate_completion(prompt)
            recommended = parse_json_markdown(response)
            if isinstance(recommended, list):
                # 过滤掉不存在的角色，并确保 architect 不在推荐列表中（它是仲裁者）
                valid_roles = [r for r in recommended if r in self.review_roles and r != 'architect']
                logger.info(f"✅ 推荐角色: {valid_roles}")
                return valid_roles
        except Exception as e:
            logger.error(f"Expert recommendation failed: {e}")
            
        return ["product", "test", "tech"] # 兜底推荐

    # ================================================================
    # 模块化评审核心逻辑
    # ================================================================

    def _identify_modules(self, combined_text: str, file_basename: str) -> Optional[List[Dict]]:
        """
        步骤2：调用 AI 识别需求文档中的功能模块。
        返回模块列表，每个模块包含 name, pages, description。
        """
        prompt = f"""请分析以下需求文档的内容，识别出其中的功能模块。

要求：
1. 将需求按照功能边界拆分为粒度更细的独立模块（建议 5-15 个模块）
2. 每个模块应该是一个相对独立的功能单元
3. 请以严格的 JSON 数组格式返回结果，不要包含任何其他文字或 markdown 标记
4. 每个模块需包含：name（模块名称）、pages（涉及的页码列表）、description（简要描述）

JSON 格式示例：
[
  {{"name": "活动创建与管理", "pages": [2, 3, 4], "description": "活动的创建、编辑、发布流程"}},
  {{"name": "用户报名", "pages": [5, 6], "description": "报名、取消报名、人数限制"}}
]

文件名: {file_basename}

需求文档内容：
{combined_text}

请直接输出 JSON 数组，不要包含 ```json 标记或任何其他文字："""

        logger.info("🔍 正在识别功能模块...")
        response = self.client.generate_completion(prompt)
        
        if not response:
            logger.error("模块识别失败：AI 返回空响应")
            return None
        
        # 解析 JSON 响应
        modules = parse_json_markdown(response)
        
        if not modules or not isinstance(modules, list) or len(modules) == 0:
            logger.error("模块识别失败：返回格式不正确或为空")
            return None
        
        logger.info(f"✅ 识别到 {len(modules)} 个功能模块：")
        for m in modules:
            logger.info(f"   📦 {m.get('name', '未命名')} - 页码 {m.get('pages', [])} - {m.get('description', '')}")
        
        return modules

    def parse_requirement(
        self,
        requirement: str = "",
        file_path: Optional[str] = None,
        max_pages: int = 0,
        skip_module_split: bool = False,
    ) -> Dict:
        return self.context_service.prepare_context(
            requirement=requirement,
            file_path=file_path,
            max_pages=max_pages,
            skip_module_split=skip_module_split,
        )

    def prepare_context(
        self,
        requirement: str = "",
        file_path: Optional[str] = None,
        max_pages: int = 0,
        skip_module_split: bool = False,
    ) -> Dict:
        return self.context_service.prepare_context(
            requirement=requirement,
            file_path=file_path,
            max_pages=max_pages,
            skip_module_split=skip_module_split,
        )

    def get_context(self, context_id: str) -> Optional[Dict]:
        return self.context_service.get_context(context_id)

    def _normalize_mode(self, mode: str) -> str:
        normalized_mode = str(mode).replace("-", "_").lower()
        if normalized_mode == "test_cases":
            return "test_case"
        return normalized_mode

    def _extract_findings_text(self, preparsed_data: Optional[Dict[str, Any]]) -> str:
        if preparsed_data and "historical_findings" in preparsed_data:
            return str(preparsed_data["historical_findings"] or "")
        return ""

    def _build_execution_context(self, context: Dict[str, Any], modules: List[Dict[str, Any]], requirement: str) -> ReviewExecutionContext:
        combined_text = str(context.get("combined_text") or "")
        vision_files_map = cast(Dict[int, Dict[str, Any]], context.get("vision_files_map") or {})
        pages = cast(List[Any], context.get("pages") or [])
        page_texts = cast(Dict[int, str], context.get("page_texts") or {})
        file_basename = str(context.get("file_basename") or "")
        req_text = str(context.get("requirement", requirement) or requirement)
        full_context = combined_text if combined_text else req_text
        all_modules_summary = "\n".join(
            [f"  - {module['name']}: {module.get('description', '')}" for module in modules]
        )
        all_images: List[Dict[str, Any]] = []
        for module in modules:
            all_images.extend(self._get_module_images(module, vision_files_map))

        return ReviewExecutionContext(
            context=context,
            modules=modules,
            combined_text=combined_text,
            vision_files_map=vision_files_map,
            pages=pages,
            page_texts=page_texts,
            file_basename=file_basename,
            req_text=req_text,
            full_context=full_context,
            all_modules_summary=all_modules_summary,
            all_images=all_images,
        )

    def _resolve_execution_context(
        self,
        requirement: str,
        file_path: Optional[str],
        max_pages: int,
        preparsed_data: Optional[Dict[str, Any]],
        context_id: Optional[str],
        skip_module_split: bool = False,
    ) -> Tuple[Optional[ReviewExecutionContext], Optional[str]]:
        if preparsed_data:
            context = cast(Dict[str, Any], preparsed_data.get("context") or {})
            modules = cast(List[Dict[str, Any]], preparsed_data.get("modules") or [])
            return self._build_execution_context(context, modules, requirement), None

        if context_id:
            parse_res = self.get_context(context_id)
            if not parse_res:
                return None, "context not found"
            context = cast(Dict[str, Any], parse_res["context"])
            modules = cast(List[Dict[str, Any]], parse_res["modules"])
            return self._build_execution_context(context, modules, requirement), None

        parse_res = self.parse_requirement(
            requirement,
            file_path,
            max_pages,
            skip_module_split=skip_module_split,
        )
        if "error" in parse_res:
            return None, str(parse_res["error"])

        context = cast(Dict[str, Any], parse_res["context"])
        modules = cast(List[Dict[str, Any]], parse_res["modules"])
        return self._build_execution_context(context, modules, requirement), None

    def _load_augmented_skill_prompt(
        self,
        skill_key: str,
        extra_prompt: str = "",
        findings_text: Optional[str] = None,
    ) -> str:
        skill_prompt = self.load_skill(SKILL_NAME_MAP.get(skill_key, skill_key)) or ""
        if not skill_prompt:
            return ""

        if findings_text:
            skill_prompt += (
                "\n\n[需求评审风险项反哺]\n"
                "以下是之前评审中发现的核心风险项，请在执行任务时重点关注并覆盖这些点：\n"
                f"{findings_text}"
            )

        if extra_prompt:
            skill_prompt += f"\n\n[用户附加要求] {extra_prompt}"

        return skill_prompt

    def _run_simple_skill_mode(
        self,
        execution_context: ReviewExecutionContext,
        skill_key: str,
        log_msg: str,
        result_prefix: str,
        extra_prompt: str = "",
        status_callback=None,
    ) -> Optional[str]:
        """通用简单技能：加载技能、拼接内容、调用 AI。"""
        skill_prompt = self._load_augmented_skill_prompt(skill_key, extra_prompt=extra_prompt)
        if not skill_prompt:
            return None

        if status_callback:
            status_callback(log_msg)

        safe_full_context = self._prepare_simple_skill_context(
            execution_context.full_context,
            skill_key,
            execution_context.file_basename,
        )
        prompt_prefix = f"""{skill_prompt}

**语言约束：所有注释和描述必须使用纯简体中文。**

---
[文档名称] {execution_context.file_basename}

[接口定义内容]
"""
        safe_full_context = self._trim_simple_skill_context(
            safe_full_context,
            prompt_prefix=prompt_prefix,
        )
        prompt = f"""{prompt_prefix}{safe_full_context}
"""
        result = self.client.generate_completion(prompt)
        return f"# {result_prefix}：{execution_context.file_basename}\n\n{result}" if result else None

    def _run_test_case_review_mode(
        self,
        execution_context: ReviewExecutionContext,
        params: Optional[Dict[str, Any]] = None,
        extra_prompt: str = "",
        status_callback=None,
        preparsed_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if status_callback:
            status_callback("🧾 正在解析测试用例内容...")

        uploaded_paths = cast(List[str], (preparsed_data or {}).get("uploaded_paths") or [])
        try:
            suite = self.test_case_review_service.resolve_case_suite(params, uploaded_paths)
        except ValueError as error:
            return f"Error: {error}"

        if status_callback:
            status_callback("🔗 正在对齐需求与测试用例...")
            status_callback("🧠 正在评审测试用例质量与覆盖情况...")

        payload = self.test_case_review_service.review_cases(
            requirement_text=execution_context.full_context or execution_context.req_text,
            suite=suite,
            reviewer=self.client.generate_completion,
            extra_prompt=extra_prompt,
        )

        if status_callback:
            status_callback("🛠️ 正在生成修订建议版测试用例...")

        return json.dumps(payload, ensure_ascii=False)

    def _run_api_test_generation_mode(
        self,
        execution_context: ReviewExecutionContext,
        extra_prompt: str = "",
        status_callback=None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        skill_prompt = self._load_augmented_skill_prompt(
            SkillMode.API_TEST_GEN,
            extra_prompt=extra_prompt,
        )
        if not skill_prompt:
            return None

        manual_pack = self._extract_manual_api_test_pack(params)
        if manual_pack:
            manual_script = str((params or {}).get("manual_script") or "").strip()
            if not manual_script:
                return "Error: 缺少可执行的接口测试脚本"
            link_plan = self.api_linking_service.build_link_plan(
                cases=cast(List[Dict[str, Any]], manual_pack.get("cases") or []),
                scenes=cast(List[Dict[str, Any]], manual_pack.get("scenes") or []),
            )

            execution_result: Dict[str, Any] = {}
            if status_callback:
                status_callback("♻️ 正在复用当前接口测试资产...")
            if isinstance(params, dict) and params.get("execute"):
                if status_callback:
                    status_callback("🧪 正在执行编辑后的 Pytest 脚本...")
                try:
                    execution_result = self.api_test_execution_service.execute_pack(
                        spec=cast(Dict[str, Any], manual_pack.get("spec") or {}),
                        cases=cast(List[Dict[str, Any]], manual_pack.get("cases") or []),
                        scenes=cast(List[Dict[str, Any]], manual_pack.get("scenes") or []),
                        params=params,
                        script=manual_script,
                    )
                except Exception as error:
                    logger.exception("API test manual execution failed:")
                    execution_result = {
                        "status": "error",
                        "summary": f"执行接口测试时发生异常：{error}",
                        "stats": {
                            "total": 0,
                            "passed": 0,
                            "failed": 0,
                            "errors": 1,
                            "skipped": 0,
                        },
                        "artifacts": {},
                        "stderr": str(error),
                    }

            report_payload = self.api_report_service.build_report(
                spec=cast(Dict[str, Any], manual_pack.get("spec") or {}),
                cases=cast(List[Dict[str, Any]], manual_pack.get("cases") or []),
                scenes=cast(List[Dict[str, Any]], manual_pack.get("scenes") or []),
                execution=execution_result,
            )
            suite_payload = self.api_suite_repository.save_suite(
                spec=cast(Dict[str, Any], manual_pack.get("spec") or {}),
                cases=cast(List[Dict[str, Any]], manual_pack.get("cases") or []),
                scenes=cast(List[Dict[str, Any]], manual_pack.get("scenes") or []),
                script=manual_script,
                link_plan=link_plan,
                execution=execution_result,
                report=report_payload,
            )
            payload = build_api_test_pack(
                spec=manual_pack.get("spec") or {},
                raw_cases=manual_pack.get("cases") or [],
                raw_scenes=manual_pack.get("scenes") or [],
                script=manual_script,
                summary=str(manual_pack.get("summary") or "").strip(),
                execution=execution_result,
                link_plan=link_plan,
                suite=suite_payload,
                report=report_payload,
            )
            return json.dumps(payload, ensure_ascii=False)

        if status_callback:
            status_callback("🔌 正在解析 OpenAPI 文档并构建结构化接口测试资产...")

        parsed_spec = self._parse_structured_api_document(execution_context.full_context)
        if not self._is_openapi_spec(parsed_spec):
            return self._run_simple_skill_mode(
                execution_context,
                SkillMode.API_TEST_GEN,
                "🔌 正在解析接口并生成 Pytest 脚本...",
                "🔌 接口测试脚本",
                extra_prompt=extra_prompt,
                status_callback=status_callback,
            )

        asset = self.openapi_asset_service.build_asset(
            cast(Dict[str, Any], parsed_spec),
            file_name=execution_context.file_basename,
        )
        suite = self.api_case_service.build_suite(asset)
        link_plan = self.api_linking_service.build_link_plan(
            cases=cast(List[Dict[str, Any]], suite.get("cases") or []),
            scenes=cast(List[Dict[str, Any]], suite.get("scenes") or []),
        )

        prompt = f"""{skill_prompt}

**语言约束：所有注释和描述必须使用纯简体中文。**
**输出约束：请直接输出完整的 Python Pytest 脚本，禁止附带额外解释。**

---
[文档名称] {execution_context.file_basename}

[结构化接口资产]
{json.dumps(asset, ensure_ascii=False, indent=2)}

[结构化用例]
{json.dumps(suite.get("cases") or [], ensure_ascii=False, indent=2)}

[关联场景]
{json.dumps(suite.get("scenes") or [], ensure_ascii=False, indent=2)}
"""

        script = self.client.generate_completion(prompt) or ""
        execution_result: Dict[str, Any] = {}
        should_execute = isinstance(params, dict) and bool(params.get("execute"))
        if should_execute:
            if status_callback:
                status_callback("🧪 正在执行生成的 Pytest 用例...")
            try:
                execution_result = self.api_test_execution_service.execute_pack(
                    spec=asset,
                    cases=cast(List[Dict[str, Any]], suite.get("cases") or []),
                    scenes=cast(List[Dict[str, Any]], suite.get("scenes") or []),
                    params=params,
                    script=script,
                )
            except Exception as error:
                logger.exception("API test execution failed:")
                execution_result = {
                    "status": "error",
                    "summary": f"执行接口测试时发生异常：{error}",
                    "stats": {
                        "total": 0,
                        "passed": 0,
                        "failed": 0,
                        "errors": 1,
                        "skipped": 0,
                    },
                        "artifacts": {},
                        "stderr": str(error),
                    }
        report_payload = self.api_report_service.build_report(
            spec=asset,
            cases=cast(List[Dict[str, Any]], suite.get("cases") or []),
            scenes=cast(List[Dict[str, Any]], suite.get("scenes") or []),
            execution=execution_result,
        )
        suite_payload = self.api_suite_repository.save_suite(
            spec=asset,
            cases=cast(List[Dict[str, Any]], suite.get("cases") or []),
            scenes=cast(List[Dict[str, Any]], suite.get("scenes") or []),
            script=script,
            link_plan=link_plan,
            execution=execution_result,
            report=report_payload,
        )
        payload = build_api_test_pack(
            spec=asset,
            raw_cases=suite.get("cases") or [],
            raw_scenes=suite.get("scenes") or [],
            script=script,
            summary=str(suite.get("summary") or "").strip(),
            execution=execution_result,
            link_plan=link_plan,
            suite=suite_payload,
            report=report_payload,
        )
        return json.dumps(payload, ensure_ascii=False)

    def _is_openapi_spec(self, spec: Optional[Dict[str, Any]]) -> bool:
        if not isinstance(spec, dict):
            return False
        paths = spec.get("paths")
        has_version = bool(str(spec.get("openapi") or spec.get("swagger") or "").strip())
        return isinstance(paths, dict) and bool(paths) and has_version

    def _extract_manual_api_test_pack(self, params: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(params, dict):
            return None
        raw_pack = params.get("pack_payload")
        if not isinstance(raw_pack, dict):
            return None
        if not isinstance(raw_pack.get("spec"), dict):
            return None
        if not isinstance(raw_pack.get("cases"), list):
            return None
        if not isinstance(raw_pack.get("scenes"), list):
            return None
        return cast(Dict[str, Any], raw_pack)

    def _prepare_simple_skill_context(
        self,
        full_context: str,
        skill_key: str,
        file_basename: str = "",
    ) -> str:
        normalized_text = self._normalize_simple_skill_context(full_context)
        processed_text = normalized_text

        if skill_key in (SkillMode.API_TEST_GEN, SkillMode.API_PERF_TEST):
            processed_text = self._extract_api_doc_summary(normalized_text)
        elif skill_key == SkillMode.AUTO_SCRIPT_GEN:
            processed_text = self._extract_ui_doc_summary(normalized_text, file_basename)

        if not processed_text:
            processed_text = normalized_text

        return processed_text

    def _normalize_simple_skill_context(self, full_context: str) -> str:
        text = str(full_context or "").replace("\r\n", "\n").replace("\r", "\n")
        if not text.strip():
            return ""

        text = re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+", "[图片Base64已省略]", text, flags=re.IGNORECASE)
        text = re.sub(r"<!--.*?-->", "\n", text, flags=re.DOTALL)
        text = re.sub(r"(?is)<script[^>]*>.*?</script>", "\n", text)
        text = re.sub(r"(?is)<style[^>]*>.*?</style>", "\n", text)
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _extract_api_doc_summary(self, text: str) -> str:
        spec = self._parse_structured_api_document(text)
        if isinstance(spec, dict):
            summary = self._build_api_doc_summary(spec)
            if summary:
                return summary
        return self._filter_api_doc_lines(text)

    def _parse_structured_api_document(self, text: str) -> Optional[Dict[str, Any]]:
        candidate = str(text or "").strip()
        if not candidate:
            return None

        try:
            parsed_json = json.loads(candidate)
            if isinstance(parsed_json, dict):
                return cast(Dict[str, Any], parsed_json)
        except Exception:
            pass

        try:
            import yaml  # type: ignore

            parsed_yaml = yaml.safe_load(candidate)
            if isinstance(parsed_yaml, dict):
                return cast(Dict[str, Any], parsed_yaml)
        except Exception:
            pass

        return None

    def _build_api_doc_summary(self, spec: Dict[str, Any]) -> str:
        lines: List[str] = ["[接口文档摘要]"]
        version = str(spec.get("openapi") or spec.get("swagger") or "").strip()
        info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
        title = str((info or {}).get("title") or "").strip()
        doc_version = str((info or {}).get("version") or "").strip()
        server_urls = self._collect_api_server_urls(spec)
        paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}

        if title:
            lines.append(f"标题：{title}")
        if version:
            lines.append(f"协议版本：{version}")
        if doc_version:
            lines.append(f"文档版本：{doc_version}")
        if server_urls:
            lines.append(f"服务地址：{'；'.join(server_urls[:3])}")
        lines.append(f"接口数量：{self._count_api_operations(paths)}")

        endpoint_lines = self._build_api_endpoint_lines(spec, paths)
        if endpoint_lines:
            lines.append("")
            lines.extend(endpoint_lines)

        return "\n".join(line for line in lines if line is not None).strip()

    def _collect_api_server_urls(self, spec: Dict[str, Any]) -> List[str]:
        urls: List[str] = []
        servers = spec.get("servers")
        if isinstance(servers, list):
            for server in servers:
                if isinstance(server, dict):
                    url = str(server.get("url") or "").strip()
                    if url:
                        urls.append(url)

        host = str(spec.get("host") or "").strip()
        base_path = str(spec.get("basePath") or "").strip()
        if host:
            scheme = ""
            schemes = spec.get("schemes")
            if isinstance(schemes, list) and schemes:
                scheme = str(schemes[0] or "").strip()
            if scheme:
                urls.append(f"{scheme}://{host}{base_path}")
            else:
                urls.append(f"{host}{base_path}")

        return list(dict.fromkeys(urls))

    def _count_api_operations(self, paths: Any) -> int:
        if not isinstance(paths, dict):
            return 0

        count = 0
        for path_item in paths.values():
            if not isinstance(path_item, dict):
                continue
            for method_name in path_item.keys():
                if str(method_name).lower() in {"get", "post", "put", "delete", "patch", "options", "head"}:
                    count += 1
        return count

    def _build_api_endpoint_lines(self, spec: Dict[str, Any], paths: Dict[str, Any]) -> List[str]:
        lines: List[str] = []
        endpoint_count = 0

        for raw_path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            path_parameters = path_item.get("parameters") if isinstance(path_item.get("parameters"), list) else []
            for raw_method, operation in path_item.items():
                method = str(raw_method).lower()
                if method not in {"get", "post", "put", "delete", "patch", "options", "head"}:
                    continue
                if not isinstance(operation, dict):
                    continue

                endpoint_count += 1
                if endpoint_count > self.SIMPLE_SKILL_MAX_ENDPOINTS:
                    lines.append("（其余接口已省略，超长部分会交由统一截断保护处理）")
                    return lines

                path = str(raw_path or "").strip()
                lines.append(f"## {method.upper()} {path}")

                summary = str(operation.get("summary") or operation.get("description") or "").strip()
                if summary:
                    lines.append(f"摘要：{summary}")

                operation_id = str(operation.get("operationId") or "").strip()
                if operation_id:
                    lines.append(f"操作ID：{operation_id}")

                tags = operation.get("tags")
                if isinstance(tags, list):
                    visible_tags = [str(tag).strip() for tag in tags if str(tag).strip()]
                    if visible_tags:
                        lines.append(f"标签：{'、'.join(visible_tags[:4])}")

                parameters = self._collect_api_parameters(spec, path_parameters, operation)
                if parameters:
                    lines.append(f"参数：{'；'.join(parameters[:self.SIMPLE_SKILL_MAX_PARAMS])}")

                request_body_fields = self._collect_api_request_body_fields(spec, operation)
                if request_body_fields:
                    lines.append(f"请求体：{'；'.join(request_body_fields[:self.SIMPLE_SKILL_MAX_PARAMS])}")

                response_descriptions = self._collect_api_response_descriptions(operation)
                if response_descriptions:
                    lines.append(f"响应：{'；'.join(response_descriptions[:self.SIMPLE_SKILL_MAX_RESPONSE_CODES])}")

                lines.append("")

        return lines

    def _collect_api_parameters(
        self,
        spec: Dict[str, Any],
        path_parameters: List[Any],
        operation: Dict[str, Any],
    ) -> List[str]:
        raw_parameters: List[Any] = []
        raw_parameters.extend(path_parameters)
        if isinstance(operation.get("parameters"), list):
            raw_parameters.extend(cast(List[Any], operation.get("parameters")))

        normalized: List[str] = []
        seen = set()
        for parameter in raw_parameters:
            resolved = self._resolve_api_ref(spec, parameter)
            if not isinstance(resolved, dict):
                continue

            name = str(resolved.get("name") or "").strip()
            location = str(resolved.get("in") or "").strip()
            required = "必填" if bool(resolved.get("required")) else "可选"

            schema = resolved.get("schema")
            if not schema and isinstance(resolved.get("content"), dict):
                first_content = next(iter(cast(Dict[str, Any], resolved["content"]).values()), None)
                if isinstance(first_content, dict):
                    schema = first_content.get("schema")
            schema = self._resolve_api_ref(spec, schema)
            type_name = self._infer_schema_type(schema)
            description = str(resolved.get("description") or "").strip()

            pieces = [name]
            if location:
                pieces.append(location)
            if type_name:
                pieces.append(type_name)
            pieces.append(required)
            label = ",".join(piece for piece in pieces if piece)
            if description:
                label = f"{label},{description[:18]}"

            if label and label not in seen:
                normalized.append(label)
                seen.add(label)

        return normalized

    def _collect_api_request_body_fields(self, spec: Dict[str, Any], operation: Dict[str, Any]) -> List[str]:
        request_body = self._resolve_api_ref(spec, operation.get("requestBody"))
        if not isinstance(request_body, dict):
            return []

        content = request_body.get("content")
        if not isinstance(content, dict) or not content:
            return []

        first_content = next(iter(content.values()), None)
        if not isinstance(first_content, dict):
            return []

        schema = self._resolve_api_ref(spec, first_content.get("schema"))
        return self._describe_api_schema_fields(spec, schema)

    def _collect_api_response_descriptions(self, operation: Dict[str, Any]) -> List[str]:
        responses = operation.get("responses")
        if not isinstance(responses, dict):
            return []

        items: List[str] = []
        for status_code, payload in responses.items():
            description = ""
            if isinstance(payload, dict):
                description = str(payload.get("description") or "").strip()
            label = str(status_code).strip()
            if description:
                items.append(f"{label}: {description[:24]}")
            elif label:
                items.append(label)
        return items

    def _describe_api_schema_fields(self, spec: Dict[str, Any], schema: Any, prefix: str = "") -> List[str]:
        resolved = self._resolve_api_ref(spec, schema)
        if not isinstance(resolved, dict):
            return []

        properties = resolved.get("properties")
        if not isinstance(properties, dict):
            item_schema = self._resolve_api_ref(spec, resolved.get("items"))
            if isinstance(item_schema, dict):
                item_type = self._infer_schema_type(item_schema)
                if prefix and item_type:
                    return [f"{prefix}[]({item_type})"]
            return []

        required_fields = resolved.get("required")
        required_set = set(required_fields) if isinstance(required_fields, list) else set()

        items: List[str] = []
        for field_name, field_schema in properties.items():
            field_label = str(field_name).strip()
            if not field_label:
                continue

            normalized_schema = self._resolve_api_ref(spec, field_schema)
            type_name = self._infer_schema_type(normalized_schema)
            required_flag = "必填" if field_label in required_set else "可选"
            description = ""
            if isinstance(normalized_schema, dict):
                description = str(normalized_schema.get("description") or "").strip()

            current_name = f"{prefix}{field_label}"
            detail = f"{current_name}({type_name or 'any'},{required_flag}"
            if description:
                detail += f",{description[:18]}"
            detail += ")"
            items.append(detail)

        return items

    def _infer_schema_type(self, schema: Any) -> str:
        if not isinstance(schema, dict):
            return ""
        schema_type = str(schema.get("type") or "").strip()
        if schema_type:
            return schema_type
        if isinstance(schema.get("properties"), dict):
            return "object"
        if schema.get("items") is not None:
            return "array"
        if isinstance(schema.get("allOf"), list):
            return "object"
        return ""

    def _resolve_api_ref(self, spec: Dict[str, Any], node: Any) -> Any:
        if not isinstance(node, dict):
            return node

        ref = str(node.get("$ref") or "").strip()
        if not ref.startswith("#/"):
            return node

        current: Any = spec
        for part in ref[2:].split("/"):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return node
        return current

    def _filter_api_doc_lines(self, text: str) -> str:
        lines = str(text or "").splitlines()
        kept_lines: List[str] = ["[接口文档摘要]"]
        pattern = re.compile(
            r"(openapi|swagger|paths|components|schema|request|response|参数|字段|headers?|body|query|summary|description|operationid|/api/|^/{1,2}|^\s{0,4}(get|post|put|delete|patch|options|head)\s*:?)",
            re.IGNORECASE,
        )

        for line in lines:
            candidate = line.strip()
            if not candidate:
                continue
            if pattern.search(candidate):
                kept_lines.append(candidate[:200])
            if len(kept_lines) >= self.SIMPLE_SKILL_MAX_TEXT_LINES:
                break

        if len(kept_lines) == 1:
            return text
        return "\n".join(kept_lines)

    def _extract_ui_doc_summary(self, text: str, file_basename: str = "") -> str:
        if self._looks_like_html_document(text, file_basename):
            summary = self._build_html_ui_summary(text)
            if summary:
                return summary
        return text

    def _looks_like_html_document(self, text: str, file_basename: str = "") -> bool:
        basename = str(file_basename or "").lower()
        if basename.endswith((".html", ".htm")):
            return True
        return bool(re.search(r"</?(html|body|form|input|button|a|label|select|textarea|main|section)\b", str(text or ""), re.IGNORECASE))

    def _build_html_ui_summary(self, html_text: str) -> str:
        lines: List[str] = ["[页面关键信息]"]
        title = self._extract_html_tag_text(html_text, "title")
        if title:
            lines.append(f"标题：{title}")

        page_texts = self._collect_ui_texts_from_html(html_text)
        if page_texts:
            lines.append(f"页面文案：{'；'.join(page_texts[:10])}")

        elements: List[str] = []
        seen = set()
        for description in self._collect_ui_elements_from_html(html_text):
            if description and description not in seen:
                elements.append(description)
                seen.add(description)

        if elements:
            lines.append("交互元素：")
            lines.extend(elements[:40])

        return "\n".join(lines).strip()

    def _collect_ui_texts_from_html(self, html_text: str) -> List[str]:
        texts: List[str] = []
        seen = set()
        for tag_name in ("h1", "h2", "h3", "label", "button", "a", "legend"):
            pattern = re.compile(fr"<{tag_name}\b[^>]*>(.*?)</{tag_name}>", re.IGNORECASE | re.DOTALL)
            for match in pattern.finditer(html_text):
                normalized = self._strip_html_tags(match.group(1))
                if not normalized or len(normalized) > 40:
                    continue
                if normalized not in seen:
                    texts.append(normalized)
                    seen.add(normalized)
        return texts

    def _collect_ui_elements_from_html(self, html_text: str) -> List[str]:
        elements: List[str] = []
        tag_patterns = [
            ("form", re.compile(r"<form\b([^>]*)>", re.IGNORECASE)),
            ("input", re.compile(r"<input\b([^>]*)/?>", re.IGNORECASE)),
            ("button", re.compile(r"<button\b([^>]*)>(.*?)</button>", re.IGNORECASE | re.DOTALL)),
            ("select", re.compile(r"<select\b([^>]*)>(.*?)</select>", re.IGNORECASE | re.DOTALL)),
            ("textarea", re.compile(r"<textarea\b([^>]*)>(.*?)</textarea>", re.IGNORECASE | re.DOTALL)),
            ("a", re.compile(r"<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)),
        ]

        for tag_name, pattern in tag_patterns:
            for match in pattern.finditer(html_text):
                attrs = self._parse_html_attrs(match.group(1))
                visible_text = self._strip_html_tags(match.group(2)) if len(match.groups()) > 1 else ""
                elements.append(self._describe_ui_element(tag_name, attrs, visible_text))

        return [item for item in elements if item]

    def _parse_html_attrs(self, raw_attrs: str) -> Dict[str, str]:
        attrs: Dict[str, str] = {}
        for match in re.finditer(r'([:@A-Za-z0-9_-]+)\s*=\s*(".*?"|\'.*?\'|[^\s>]+)', raw_attrs or ""):
            key = str(match.group(1) or "").strip().lower()
            value = str(match.group(2) or "").strip().strip("\"'")
            if key:
                attrs[key] = html.unescape(value)
        return attrs

    def _describe_ui_element(self, tag_name: str, attrs: Dict[str, str], visible_text: str = "") -> str:
        parts = [tag_name]
        element_id = str(attrs.get("id") or "").strip()
        if element_id:
            parts.append(f"#{element_id}")

        attr_parts: List[str] = []
        for attr_name in ("name", "type", "placeholder", "action", "href"):
            attr_value = str(attrs.get(attr_name) or "").strip()
            if attr_value:
                attr_parts.append(f"[{attr_name}={attr_value}]")

        description = "".join(parts) + "".join(attr_parts)
        visible = html.unescape(str(visible_text or "").strip())
        if visible and len(visible) <= 40:
            description += f"{{{visible}}}"
        return description

    def _extract_html_tag_text(self, html_text: str, tag_name: str) -> str:
        match = re.search(fr"<{tag_name}\b[^>]*>(.*?)</{tag_name}>", html_text, re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return self._strip_html_tags(match.group(1))

    def _strip_html_tags(self, text: str) -> str:
        normalized = re.sub(r"(?is)<[^>]+>", " ", str(text or ""))
        normalized = html.unescape(normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _trim_simple_skill_context(
        self,
        full_context: str,
        prompt_prefix: str = "",
        prompt_suffix: str = "",
    ) -> str:
        text = str(full_context or "").strip()
        if not text:
            return ""
        return self._trim_text_for_prompt_slot(
            text=text,
            prompt_prefix=prompt_prefix,
            prompt_suffix=prompt_suffix,
            preserve_tail=True,
            truncation_notice="\n\n【以下内容过长，已按 token 预算截断中间内容；请优先依据首尾关键接口定义生成结果。】\n\n",
        )

    def _run_fulltext_skill_mode(
        self,
        execution_context: ReviewExecutionContext,
        skill_key: str,
        log_msg: str,
        result_prefix: str,
        extra_prompt: str = "",
        extra_constraints: str = "",
        status_callback=None,
    ) -> Optional[str]:
        """通用全文视角技能（测试方案、测试数据等）：合并所有模块后一次性生成。"""
        skill_prompt = self._load_augmented_skill_prompt(skill_key, extra_prompt=extra_prompt)
        if not skill_prompt:
            return None

        if status_callback:
            status_callback(log_msg)

        prompt_prefix = f"""{skill_prompt}

**重要约束：输出中禁止出现任何人名，直接输出内容。**
**语言约束：所有输出必须使用纯简体中文，严禁中英混杂，禁止出现英文括号注释。**
{extra_constraints}

---
[文档名称] {execution_context.file_basename}

[功能模块清单]
{execution_context.all_modules_summary}

[完整需求内容]
"""
        safe_full_context = self._trim_simple_skill_context(
            execution_context.full_context,
            prompt_prefix=prompt_prefix,
        )
        prompt = f"""{prompt_prefix}{safe_full_context}
        """
        if execution_context.all_images:
            safe_images = list(execution_context.all_images)[:20]  # type: ignore
            result = self.client.generate_completion(prompt, files=safe_images)
        else:
            result = self.client.generate_completion(prompt)
        return f"# {result_prefix}：{execution_context.file_basename}\n\n{result}" if result else None

    def _run_module_skill_mode(
        self,
        execution_context: ReviewExecutionContext,
        skill_key: str,
        log_msg: str,
        run_mode: str,
        extra_prompt: str = "",
        findings_text: Optional[str] = None,
        status_callback=None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """通用逐模块视角技能（需求评审、测试点、流程图等），支持并行处理。"""
        skill_prompt = self._load_augmented_skill_prompt(
            skill_key,
            extra_prompt=extra_prompt,
            findings_text=findings_text,
        )
        if not skill_prompt:
            return None

        if status_callback:
            status_callback(log_msg)

        return self._run_single_skill_with_context(
            execution_context.req_text,
            execution_context.combined_text,
            execution_context.vision_files_map,
            execution_context.pages,
            execution_context.file_basename,
            execution_context.modules,
            skill_prompt,
            mode=run_mode,
            status_callback=status_callback,
            page_texts=execution_context.page_texts,
            execution_params=params,
        )

    def _run_review_mode(
        self,
        execution_context: ReviewExecutionContext,
        roles: Optional[List[str]],
        extra_prompt: str = "",
        status_callback=None,
    ) -> Optional[str]:
        if roles and len(roles) > 0:
            logger.info(f"开始多角色评审，角色: {roles}")
            result_json = self._run_multi_role_with_context(
                execution_context.req_text,
                execution_context.combined_text,
                execution_context.vision_files_map,
                execution_context.pages,
                execution_context.file_basename,
                execution_context.modules,
                roles,
                page_texts=execution_context.page_texts,
                status_callback=status_callback,
            )
            try:
                safe_json_str = str(result_json or "{}")
                parsed_result = json.loads(safe_json_str)
                all_text = ""
                for role_id in parsed_result:
                    all_text += f"\n{parsed_result[role_id].get('content', '')}"

                findings = self._extract_actionable_findings(all_text)
                if status_callback:
                    status_callback("📌 风险等级划分与汇总...")
                return self.review_result_service.serialize(parsed_result, findings)
            except Exception as error:
                logger.error(f"Review aggregation failed: {error}")
                return result_json

        skill_prompt = self._load_augmented_skill_prompt(SkillMode.REVIEW, extra_prompt=extra_prompt)
        if not skill_prompt:
            return None

        logger.info("开始单专家评审")
        return self._run_single_skill_with_context(
            execution_context.req_text,
            execution_context.combined_text,
            execution_context.vision_files_map,
            execution_context.pages,
            execution_context.file_basename,
            execution_context.modules,
            skill_prompt,
            page_texts=execution_context.page_texts,
        )

    def _run_test_data_preparation_mode(
        self,
        execution_context: ReviewExecutionContext,
        extra_prompt: str = "",
        status_callback=None,
    ) -> str:
        source_text = execution_context.full_context or execution_context.req_text
        payload = self.test_data_preparation_service.prepare_result(
            document_name=execution_context.file_basename or "Requirement",
            raw_text=source_text,
            extra_prompt=extra_prompt,
            status_callback=status_callback,
        )
        return json.dumps(payload, ensure_ascii=False)

    def _load_role_prompts(self, roles: List[str]) -> Dict[str, str]:
        role_prompts: Dict[str, str] = {}
        for role_id in roles:
            role_info = self.review_roles.get(role_id)
            if not role_info:
                continue
            prompt = self.load_skill(role_info["skill"])
            if prompt:
                role_label = str(role_info.get("label") or role_id)
                role_focus = self.ROLE_FOCUS_HINTS.get(role_id, "请严格围绕当前角色职责进行评审，避免输出泛化结论。")
                role_prompts[role_id] = (
                    f"{prompt}\n\n"
                    f"[当前评审角色]\n"
                    f"- 角色：{role_label}\n"
                    f"- 角色要求：{role_focus}"
                )
        return role_prompts

    def _resolve_module_review_text(
        self,
        module: Dict[str, Any],
        pages: List[Any],
        page_texts: Optional[Dict[int, str]],
        combined_text: str,
    ) -> str:
        module_text = self._get_module_text(module, pages)
        if not module_text and page_texts:
            module_page_nums = module.get("pages", [])
            page_parts = []
            for pg in module_page_nums:
                try:
                    pg_int = int(pg)
                    text_content = page_texts.get(pg_int)
                    if text_content is not None:
                        page_parts.append(f"--- 第 {pg_int} 页 ---\n{text_content}")
                except (ValueError, TypeError):
                    pass
            if page_parts:
                module_text = "\n\n".join(page_parts)
        if not module_text and combined_text:
            module_text = combined_text
        return module_text

    def _build_multi_role_tasks(
        self,
        modules: List[Dict[str, Any]],
        role_prompts: Dict[str, str],
    ) -> Tuple[List[Tuple[str, int, Dict[str, Any]]], int]:
        tasks = []
        for role_id in role_prompts:
            for idx, module in enumerate(modules):
                tasks.append((role_id, idx, module))
        return tasks, len(tasks)

    def _run_parallel_role_reviews(
        self,
        expert_tasks: List[Tuple[str, int, Dict[str, Any]]],
        role_prompts: Dict[str, str],
        pages: List[Any],
        page_texts: Optional[Dict[int, str]],
        combined_text: str,
        vision_files_map: Dict[int, Dict[str, Any]],
        all_modules_summary: str,
        effective_requirement: str,
        status_callback=None,
        total_tasks: int = 0,
    ) -> Dict[str, List[Any]]:
        results: Dict[str, List[Any]] = {role_id: [] for role_id in role_prompts}
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers_multi_role) as executor:
            future_map = {}
            for role_id, idx, module in expert_tasks:
                module_text = self._resolve_module_review_text(module, pages, page_texts, combined_text)
                module_images = self._get_module_images(module, vision_files_map)
                future = executor.submit(  # type: ignore
                    lambda m, t, i, p, s, r: self._review_single_module(m, t, i, p, s, r),
                    module, module_text, module_images,
                    role_prompts[role_id], all_modules_summary, effective_requirement
                )
                future_map[future] = (role_id, idx, module)

            for future in as_completed(future_map):
                role_id, idx, module = future_map[future]
                module_name = module.get("name", f"模块{idx+1}")
                completed += 1
                try:
                    result = future.result()
                    results[role_id].append((idx, module_name, result or "> ⚠️ 无效结果"))
                except Exception as e:
                    results[role_id].append((idx, module_name, f"> ⚠️ 错误: {e}"))
                if status_callback:
                    status_callback(f"⚖️ 视角对碰与逻辑冲突识别... ({completed}/{total_tasks})")

        return results

    def _apply_architect_arbitration(
        self,
        results: Dict[str, List[Any]],
        role_prompts: Dict[str, str],
        effective_requirement: str,
        status_callback=None,
    ) -> None:
        if 'architect' not in role_prompts:
            return

        logger.info("🏛️ 专家评审已完成，正在启动架构仲裁...")
        if status_callback:
            status_callback("🏛️ 架构师最终仲裁建议生成...")

        all_reports = ""
        for role_id, result_list in results.items():
            if role_id == 'architect':
                continue
            label = self.review_roles[role_id]['label']
            role_summary = "\n".join([f"### {module_name}\n{review_text}" for _, module_name, review_text in sorted(result_list)])
            all_reports += f"\n\n=== {label} 评审意见 ===\n{role_summary}"

        architect_result = self._run_architect_arbitration(
            all_reports,
            role_prompts['architect'],
            effective_requirement,
        )
        results['architect'] = [(0, "架构仲裁总结", architect_result or "")]

    def _serialize_multi_role_results(
        self,
        results: Dict[str, List[Any]],
        modules: List[Dict[str, Any]],
    ) -> str:
        structured_result = {}
        for role_id in results:
            role_results: Any = results[role_id]
            role_results.sort(key=lambda x: x[0])  # type: ignore

            role_label = self.review_roles[role_id]["label"]
            role_report_parts = []
            for idx, module_name, review_text in role_results:
                module_info = cast(Any, modules)[idx]
                module_pages = module_info.get("pages", [])
                page_range = f"第 {min(module_pages)}-{max(module_pages)} 页" if module_pages else ""
                role_report_parts.append(
                    f"## 📦 {module_name}（{page_range}）\n\n{review_text}"
                )
            structured_result[role_id] = {
                "label": role_label,
                "content": "\n\n---\n\n".join(role_report_parts)
            }

        return json.dumps(structured_result, ensure_ascii=False)

    def _execute_mode(
        self,
        execution_context: ReviewExecutionContext,
        mode: str,
        roles: Optional[List[str]],
        extra_prompt: str,
        findings_text: str,
        status_callback=None,
        params: Optional[Dict[str, Any]] = None,
        preparsed_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Optional[str]]:
        if mode == SkillMode.TEST_CASE:
            return "测试用例生成", self._run_module_skill_mode(
                execution_context,
                SkillMode.TEST_CASE,
                "🚀 开始生成测试用例...",
                "test_case",
                extra_prompt=extra_prompt,
                findings_text=findings_text,
                status_callback=status_callback,
                params=params,
            )

        if mode == SkillMode.TEST_CASE_REVIEW:
            return "测试用例评审", self._run_test_case_review_mode(
                execution_context,
                params=params,
                extra_prompt=extra_prompt,
                status_callback=status_callback,
                preparsed_data=preparsed_data,
            )

        if mode == SkillMode.LOG_DIAGNOSIS:
            return "日志深度诊断", self._run_module_skill_mode(
                execution_context,
                SkillMode.LOG_DIAGNOSIS,
                "🔍 正在诊断日志...",
                "log_diagnosis",
                extra_prompt=extra_prompt,
                status_callback=status_callback,
                params=params,
            )

        if mode == SkillMode.TEST_DATA:
            return "测试数据准备", self._run_test_data_preparation_mode(
                execution_context,
                extra_prompt=extra_prompt,
                status_callback=status_callback,
            )

        if mode == SkillMode.IMPACT_ANALYSIS:
            return "影响面分析", self._run_impact_analysis_from_context(
                execution_context.combined_text,
                execution_context.req_text,
                preparsed_data,
                self.load_skill(SKILL_NAME_MAP[SkillMode.IMPACT_ANALYSIS]),
            )

        if mode == SkillMode.TEST_PLAN:
            constraint = (
                f"**重要约束：你需要生成一份完整的、全局性的测试方案，而非按模块拆分的多份方案。{findings_text}**"
                if findings_text else
                "**重要约束：你需要生成一份完整的、全局性的测试方案，而非按模块拆分的多份方案。**"
            )
            return "测试方案制定", self._run_fulltext_skill_mode(
                execution_context,
                SkillMode.TEST_PLAN,
                "📅 正在制定测试方案...",
                "📅 整体测试方案",
                extra_prompt=extra_prompt,
                extra_constraints=constraint,
                status_callback=status_callback,
            )

        if mode == SkillMode.API_TEST_GEN:
            return "接口测试资产生成", self._run_api_test_generation_mode(
                execution_context,
                extra_prompt=extra_prompt,
                status_callback=status_callback,
                params=params,
            )

        if mode == SkillMode.API_PERF_TEST:
            return "性能压测配置", self._run_simple_skill_mode(
                execution_context,
                SkillMode.API_PERF_TEST,
                "🚀 正在解析接口并生成 Locust 压测脚本...",
                "🚀 性能压测脚本",
                extra_prompt=extra_prompt,
                status_callback=status_callback,
            )

        if mode == SkillMode.AUTO_SCRIPT_GEN:
            return "UI自动化编写", self._run_simple_skill_mode(
                execution_context,
                SkillMode.AUTO_SCRIPT_GEN,
                "🤖 正在生成 Playwright 脚本...",
                "🤖 UI 自动化脚本",
                extra_prompt=extra_prompt,
                status_callback=status_callback,
            )

        if mode == SkillMode.FLOWCHART:
            return "业务流程提取", self._run_module_skill_mode(
                execution_context,
                SkillMode.FLOWCHART,
                "📊 正在提取业务逻辑并绘制流程图...",
                "flowchart",
                extra_prompt=extra_prompt,
                status_callback=status_callback,
                params=params,
            )

        if mode == SkillMode.REQ_ANALYSIS:
            return "需求结构剥离", self._run_module_skill_mode(
                execution_context,
                SkillMode.REQ_ANALYSIS,
                "🔬 正在深度拆解需求结构...",
                "req_analysis",
                extra_prompt=extra_prompt,
                findings_text=findings_text,
                status_callback=status_callback,
                params=params,
            )

        if mode == SkillMode.TEST_POINT:
            return "九维测试点拆解", self._run_module_skill_mode(
                execution_context,
                SkillMode.TEST_POINT,
                "🎯 正在九维全景提取测试点...",
                "test_point",
                extra_prompt=extra_prompt,
                findings_text=findings_text,
                status_callback=status_callback,
                params=params,
            )

        return "需求智能评审", self._run_review_mode(
            execution_context,
            roles=roles,
            extra_prompt=extra_prompt,
            status_callback=status_callback,
        )

    def _get_module_text(self, module: Dict, pages: List) -> str:
        """提取单个模块涉及的页面文字内容。"""
        module_pages = module.get("pages", [])
        parts = []
        for page in pages:
            if page.page_num in module_pages and page.text_length > 0:
                parts.append(f"--- 第 {page.page_num} 页 ---\n{page.text}")
        return "\n\n".join(parts) if parts else ""

    def _get_module_images(self, module: Dict, vision_files_map: Dict[int, Dict]) -> List[Dict]:
        """提取单个模块涉及的图片文件（最多 3 张）。"""
        module_pages = module.get("pages", [])
        images = []
        for pg in module_pages:
            try:
                page_num = int(pg)
                if page_num in vision_files_map:
                    sanitized_image = self._sanitize_module_image(vision_files_map[page_num])
                    if sanitized_image:
                        images.append(sanitized_image)
            except (ValueError, TypeError):
                continue
            if len(images) >= self.DIFY_MAX_IMAGES:
                break
        return images

    def _sanitize_module_image(self, image: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(image, dict):
            return None

        sanitized = {
            key: value
            for key, value in image.items()
            if value not in (None, "")
        }
        if not sanitized:
            return None

        transfer_method = str(sanitized.get("transfer_method") or "").strip()
        upload_file_id = sanitized.get("upload_file_id")
        image_url = str(sanitized.get("url") or "").strip()

        if transfer_method == "local_file":
            if self._is_valid_dify_upload_file_id(upload_file_id):
                sanitized["upload_file_id"] = str(upload_file_id).strip()
                return sanitized
            if image_url:
                sanitized.pop("upload_file_id", None)
                return sanitized
            logger.warning("检测到非法视觉文件 ID，已跳过该图片引用。")
            return None

        return sanitized

    def _is_valid_dify_upload_file_id(self, upload_file_id: Any) -> bool:
        text = str(upload_file_id or "").strip()
        if not text:
            return False
        try:
            uuid.UUID(text)
            return True
        except (ValueError, TypeError, AttributeError):
            return False

    def _review_single_module(self, module: Dict, module_text: str, 
                              module_images: List[Dict], skill_prompt: str,
                              all_modules_summary: str, requirement: str) -> Optional[str]:
        """
        步骤3：对单个模块进行独立处理。
        """
        module_name = module.get("name", "未命名模块")
        module_desc = module.get("description", "")
        module_pages = module.get("pages", [])
        
        safe_module_text: Any = module_text or "（该模块主要为图片/原型图内容，请结合上传的图片进行分析）"
        prompt_prefix = f"""
{skill_prompt}

**重要约束：输出中禁止出现任何人名，不要称呼用户姓名，不要使用"你好，XXX"等问候语。直接输出内容。**
**语言约束：所有输出必须使用纯简体中文，严禁中英混杂（如"边界测试(Boundary)"），禁止出现英文括号注释。**

---

[当前模块上下文]
模块名称：**{module_name}**
模块描述：{module_desc}
涉及页码：第 {module_pages} 页

本文档的完整模块结构如下（供你理解上下文和跨模块关联）：
{all_modules_summary}

以下是该模块涉及页面的文字内容：
"""
        prompt_suffix = f"""

{"上传的图片是该模块涉及的原型图/流程图页面，请结合图片内容一起分析。" if module_images else ""}

{requirement}
"""
        module_text_snippet = self._trim_text_for_prompt_slot(
            text=str(safe_module_text),
            prompt_prefix=prompt_prefix,
            prompt_suffix=prompt_suffix,
        )
        prompt = f"""{prompt_prefix}{module_text_snippet}{prompt_suffix}"""
        
        prompt_preview = str(prompt)[:500]  # type: ignore
        logger.info(f"  ⚙️ 正在处理模块「{module_name}」（{len(module_images)} 张图片）...")
        logger.debug(f"Prompt sent to LLM: {prompt_preview}...")
        response = self.client.generate_completion(prompt, files=module_images if module_images else [])
        
        if response:
            logger.info(f"  ✅ 模块「{module_name}」处理完成，响应长度: {len(response)}")
        else:
            logger.error(f"  ❌ 模块「{module_name}」处理失败或返回空")
        
        return response

    # ================================================================
    # 动态风险洞察
    # ================================================================
    def generate_dynamic_insight(self, generated_content: Optional[str]) -> Optional[str]:
        """为生成的文档片段提炼 1-2 句话的核心动态风险洞察，返回给前端供 HUD 显示。"""
        if not generated_content or len(str(generated_content)) < 50:
            return None
            
        prompt = f"""
请根据以下生成的测试/评审内容，用 1 句简练的话（字数严格控制在 50 字以内）总结出其中风险最高、或最容易出现边界漏洞的业务点。
重点：要像资深测试隐患专家那样一语破的，语气带专业性警示。不需要任何寒暄、称呼和“这段内容说明了”、“风险点是”等废话，直接输出结论，如：“本需求涉及优惠券逆向流程，建议重点关注退款并发时的资金防资损用例。”

生成的文档内容截取：
{str(generated_content)[:3000]}
"""
        logger.info("💡 正在追加生成动态风险洞察 (Dynamic Insight)...")
        try:
            insight = self.client.generate_completion(prompt)
            if insight:
                insight = insight.replace("\"", "").replace("'", "").strip()
                logger.info(f"💡 洞察提取成功: {insight}")
            return insight
        except Exception as e:
            logger.error(f"Failed to generate insight: {e}")
            return None

    # ================================================================
    # 评审入口
    # ================================================================



    def run_review(self, requirement: str = "", file_path: Optional[str] = None, 
                  mode: str = "review", roles: Optional[List[str]] = None,
                  max_pages: int = 0,
                  preparsed_data: Optional[Dict] = None,
                  context_id: Optional[str] = None,
                  status_callback=None,
                  params: Optional[Dict[str, Any]] = None,
                  extra_prompt: str = "") -> Optional[str]:
        """
        执行评审/生成流程。
        支持传入 preparsed_data (from parse_requirement) 以跳过重复解析。
        status_callback: function(msg: str) -> None, 用于实时回传进度
        extra_prompt: 用户附加指令，会追加到技能提示词末尾
        """
        def update_status(msg):
            logger.info(msg)
            if status_callback:
                status_callback(msg)

        normalized_mode = self._normalize_mode(mode)
        execution_context, context_error = self._resolve_execution_context(
            requirement=requirement,
            file_path=file_path,
            max_pages=max_pages,
            preparsed_data=cast(Optional[Dict[str, Any]], preparsed_data),
            context_id=context_id,
            skip_module_split=normalized_mode == SkillMode.TEST_DATA,
        )

        if context_error:
            db_manager.add_run_record(
                action=normalized_mode,
                target=file_path or "未知文件",
                status="fail",
                error_msg=context_error,
            )
            return f"Error: {context_error}"

        if not execution_context:
            return None

        findings_text = self._extract_findings_text(cast(Optional[Dict[str, Any]], preparsed_data))
            
        start_time = time.time()
        final_result = None
        error_msg = ""
        action_name = "未明动作"
        
        try:
            action_name, final_result = self._execute_mode(
                execution_context,
                normalized_mode,
                roles=roles,
                extra_prompt=extra_prompt,
                findings_text=findings_text,
                status_callback=update_status,
                params=params,
                preparsed_data=cast(Optional[Dict[str, Any]], preparsed_data),
            )
            status = "success" if final_result and not str(final_result).startswith("Error:") else "fail"
            
        except Exception as e:
            status = "fail"
            error_msg = str(e)
            logger.exception("AI Skill execution crashed:")
            raise e
        finally:
            cost_time = time.time() - start_time
            # 静默记录到 SQLite
            db_manager.add_run_record(
                action=action_name,
                target=execution_context.file_basename or "直接输入文本",
                status=status,
                cost_time=cost_time,
                error_msg=error_msg
            )
            
        return final_result

    def _run_single_skill_with_context(self, requirement: str, combined_text: str, 
                                     vision_files_map: Dict, pages: List, file_basename: str, 
                                     modules: List[Dict], skill_prompt: str, mode: str = "review",
                                     status_callback=None, page_texts: Optional[Dict[int, str]] = None,
                                     execution_params: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """使用上下文执行单技能评审。"""
        
        # 纯文本模式兜底
        if not combined_text and not vision_files_map:
             full_prompt = f"""
            {skill_prompt}
            **重要约束：输出中禁止出现任何人名，直接输出内容。**
            **语言约束：所有输出必须使用纯简体中文，严禁中英混杂，禁止出现英文括号注释。**
            ---
            [用户输入需求]
            {requirement}
            """
             return self.client.generate_completion(full_prompt)

        # 逐模块评审
        all_modules_summary = "\n".join(
            [f"  - {m['name']}（第 {m.get('pages', [])} 页）: {m.get('description', '')}" 
             for m in modules]
        )
        
        # 逐模块分析与结果拼装
        report_parts = []
        all_module_results = []
        module_case_results: List[Dict[str, Any]] = []
        
        # 根据模式设置报告标题
        mode_title_map = {
            "test_case": None,
            "test_plan": f"# 📅 整体测试方案：{file_basename}\n",
            "flowchart": f"# 📊 业务流程导图：{file_basename}\n",
            "log_diagnosis": f"# 🔍 日志诊断报告：{file_basename}\n",
            "req_analysis": f"# 🔬 需求结构化分析：{file_basename}\n",
            "test_point": f"# 🎯 全维度测试点分析：{file_basename}\n",
        }
        title = mode_title_map.get(mode, f"# 📋 需求评审报告：{file_basename}\n")
        if title:
            report_parts.append(title)

        total_modules = len(modules)
        
        # 定义任务函数
        def process_module_task(idx, module):
            module_name = module.get("name", f"模块{idx+1}")
            module_pages = module.get("pages", [])
            
            # 尝试在线程中调用 callback (注意 Streamlit 上下文问题，可能需要容错)
            def safe_callback(msg):
                if status_callback:
                    try:
                        status_callback(msg)
                    except Exception:
                        pass # 忽略线程中 UI 更新失败
            
            safe_callback(f"🚀 [{idx+1}/{total_modules}] 开始处理：{module_name}")
            try:
                module_text = self._get_module_text(module, pages)
                # 优先使用 page_texts 按模块页码提取对应文本
                if not module_text and page_texts:
                    module_page_nums = module.get("pages", [])
                    page_parts = []
                    for pg in module_page_nums:
                        try:
                            pg_int = int(pg)
                            text_content = page_texts.get(pg_int) if page_texts else None
                            if text_content is not None:
                                page_parts.append(f"--- 第 {pg_int} 页 ---\n{text_content}")
                        except (ValueError, TypeError):
                            pass
                    if page_parts:
                        module_text = "\n\n".join(page_parts)
                # 最终兜底：当以上都无法获取到模块文本时，使用 combined_text
                if not module_text and combined_text:
                    module_text = combined_text
                module_images = self._get_module_images(module, vision_files_map)

                result = None
                if mode == "test_case":
                    result = self._generate_module_test_cases(
                        module, module_text, module_images,
                        skill_prompt, all_modules_summary, requirement,
                        safe_callback,
                        execution_params=execution_params,
                    )
                elif mode == "req_analysis":
                    result = self._generate_module_requirement_analysis(
                        module, module_text, module_images,
                        skill_prompt, all_modules_summary, requirement
                    )
                elif mode == "flowchart":
                    result = self._generate_module_flowchart(
                        module, module_text, module_images,
                        skill_prompt, all_modules_summary, requirement
                    )
                else:
                    result = self._review_single_module(
                        module, module_text, module_images,
                        skill_prompt, all_modules_summary, requirement
                    )

                safe_callback(f"✅ [{idx+1}/{total_modules}] 完成：{module_name}")
                return idx, module, result, None
            except Exception as error:
                error_message = str(error) or "未知错误"
                logger.error(f"模块处理失败：{module_name} - {error_message}")
                safe_callback(f"❌ [{idx+1}/{total_modules}] 失败：{module_name} - {error_message}")
                return idx, module, None, error_message

        # 并行执行
        results = []
        # 限制并发数，避免触发 Dify 速率限制
        with ThreadPoolExecutor(max_workers=self.max_workers_single_role) as executor:
            futures = []
            for idx, m in enumerate(modules):
                # 使用 lambda 并显式 ignore 以通过 Pyre2 的严格校验
                f = executor.submit(lambda i=idx, mod=m: process_module_task(i, mod))  # type: ignore
                futures.append(f)
            
            for future in as_completed(futures):
                try:
                    idx, module, res, error_message = future.result()
                    results.append((idx, module, res, error_message))
                except Exception as e:
                    logger.error(f"Module processing failed: {e}")

        # 按原始顺序排序
        results.sort(key=lambda x: x[0])
        failed_test_case_modules: List[str] = []

        # 处理结果
        for idx, module, res, error_message in results:
            module_name = module.get("name", f"模块{idx+1}")
            module_pages = module.get("pages", [])
            
            if mode == "test_case":
                if isinstance(res, list) and res:
                    module_case_results.append({
                        "module": module,
                        "items": res,
                    })
                else:
                    failed_label = module_name
                    if error_message:
                        failed_label = f"{module_name}（{error_message}）"
                    failed_test_case_modules.append(failed_label)
            elif mode == "flowchart":
                if res:
                    all_module_results.append(res)
            elif mode == "test_plan":
                if res:
                    report_parts.append(f"### 📋 模块方案：{module_name}\n\n{res}")
            elif mode == "req_analysis":
                if res:
                    all_module_results.append(res)
            elif mode == "test_point":
                if res:
                    report_parts.append(f"### 🎯 测试点：{module_name}\n\n{res}")
            else:
                if res:
                    page_range = f"第 {min(module_pages)}-{max(module_pages)} 页" if module_pages else ""
                    report_parts.append(
                        f"## 📦 模块{idx+1}：{module_name}（{page_range}）\n\n{res}"
                    )
                else:
                    report_parts.append(
                        f"## 📦 模块{idx+1}：{module_name}\n\n> ⚠️ 该模块未获得有效结果\n"
                    )

        if mode == "test_case":
             # 将所有模块的用例列表扁平化并返回统一结构
             if status_callback:
                 status_callback("🧪 正在汇总测试用例结果...")
             flattened_items = []
             for module_result in module_case_results:
                 res_list = module_result.get("items")
                 if isinstance(res_list, list):
                     flattened_items.extend(res_list)

             if not flattened_items:
                 failure_summary = "测试用例生成失败：所有模块均未获得有效结果。"
                 if failed_test_case_modules:
                     visible_modules = "；".join(failed_test_case_modules[:5])
                     if len(failed_test_case_modules) > 5:
                         visible_modules += "；其余模块已省略"
                     failure_summary = f"{failure_summary} 失败模块：{visible_modules}"
                 logger.error(failure_summary)
                 return f"Error: {failure_summary}"

             deduplicated_module_items = self._deduplicate_test_case_items(flattened_items, [])
             global_supplement_items = self._generate_global_test_case_supplements(
                 modules=modules,
                 requirement=requirement,
                 all_modules_summary=all_modules_summary,
                 module_case_results=module_case_results,
                 skill_prompt=skill_prompt,
                 execution_params=execution_params,
                 status_callback=status_callback,
             )
             final_items = self._deduplicate_test_case_items(
                 deduplicated_module_items,
                 global_supplement_items,
             )

             summary = f"已完成 {len(modules)} 个模块的用例生成，共计 {len(final_items)} 条测试用例。"
             supplement_added_count = max(0, len(final_items) - len(deduplicated_module_items))
             if supplement_added_count:
                 summary = f"{summary} 其中新增 {supplement_added_count} 条跨模块或全局补漏用例。"
             if failed_test_case_modules:
                 visible_modules = "；".join(failed_test_case_modules[:5])
                 if len(failed_test_case_modules) > 5:
                     visible_modules += "；其余模块已省略"
                 summary = f"{summary} 另有 {len(failed_test_case_modules)} 个模块未获得有效结果：{visible_modules}"

             return self.case_design_service.serialize_suite(
                 final_items,
                 summary=summary
             )
        elif mode == "req_analysis":
             if status_callback:
                 status_callback("🔬 正在汇总结构化需求分析结果...")
             analysis_items = [item for item in all_module_results if isinstance(item, dict) and item]
             return self.requirement_analysis_service.serialize_pack(
                 analysis_items,
                 summary=f"已完成 {len(modules)} 个模块的结构化需求分析。"
             )
        elif mode == "flowchart":
             if status_callback:
                 status_callback("📊 正在汇总业务流程图结果...")
             flowchart_items = [item for item in all_module_results if isinstance(item, dict) and item]
             return self.flowchart_service.serialize_pack(
                 flowchart_items,
                 summary=f"已完成 {len(modules)} 个模块的业务流程提取。"
             )
        else:
             final_report = "\n\n---\n\n".join(report_parts)
             logger.info(f"✅ 处理完成，共 {len(modules)} 个模块")
             return final_report

    def _format_test_case_preferences(self, execution_params: Optional[Dict[str, Any]] = None) -> str:
        params = execution_params or {}
        strategy_map = {
            "happy": "核心路径（Happy Path）",
            "full": "全量覆盖（Full Coverage）",
            "negative": "异常攻防（Negative）",
            "smoke": "快速冒烟（Sanity）",
        }
        level_map = {
            "integration": "集成测试",
            "system": "系统测试",
            "regression": "回归测试",
            "集成测试": "集成测试",
            "系统测试": "系统测试",
            "回归测试": "回归测试",
        }
        strategy = strategy_map.get(str(params.get("strategy") or "happy"), str(params.get("strategy") or "happy"))
        level = level_map.get(str(params.get("level") or "system"), str(params.get("level") or "system"))
        environment = str(params.get("environment") or "default")
        variables = params.get("variables")

        lines = [
            "[生成偏好]",
            f"- 生成策略：{strategy}",
            f"- 覆盖层级：{level}",
            f"- 目标环境：{environment}",
            "- 用例等级：严格只允许输出 P0、P1、P2、P3 四个等级",
            "- 步骤要求：每一步必须提供对应的预期结果，禁止留空",
        ]
        if isinstance(variables, dict) and variables:
            lines.append("- 全局变量：")
            for key, value in variables.items():
                lines.append(f"  - {key}={value}")
        return "\n".join(lines)

    def _build_module_case_coverage_summary(
        self,
        modules: List[Dict[str, Any]],
        module_case_results: List[Dict[str, Any]],
    ) -> str:
        result_map: Dict[str, List[Dict[str, Any]]] = {}
        for module_result in module_case_results:
            if not isinstance(module_result, dict):
                continue
            module = module_result.get("module")
            if not isinstance(module, dict):
                continue
            module_name = str(module.get("name") or "").strip()
            items = module_result.get("items")
            if not module_name or not isinstance(items, list):
                continue
            result_map[module_name] = items

        lines: List[str] = []
        for index, module in enumerate(modules, start=1):
            module_name = str(module.get("name") or f"模块{index}").strip() or f"模块{index}"
            module_desc = str(module.get("description") or "").strip()
            module_pages = module.get("pages") or []
            module_items = result_map.get(module_name, [])

            lines.append(f"### 模块{index}：{module_name}")
            if module_desc:
                lines.append(f"- 模块说明：{module_desc}")
            if module_pages:
                lines.append(f"- 涉及页码：{module_pages}")

            if not module_items:
                lines.append("- 已有模块级用例：无")
                continue

            lines.append("- 已有模块级用例：")
            for case_index, item in enumerate(module_items, start=1):
                title = str(item.get("title") or "未命名用例").strip() or "未命名用例"
                precondition = str(item.get("precondition") or "").strip()
                step_actions = []
                for step in item.get("steps") or []:
                    if isinstance(step, dict):
                        action = str(step.get("action") or "").strip()
                        if action:
                            step_actions.append(action)
                step_summary = " -> ".join(step_actions)
                lines.append(f"  - 用例{case_index}：{title}")
                if precondition:
                    lines.append(f"    前置条件：{precondition}")
                if step_summary:
                    lines.append(f"    关键步骤：{step_summary}")

        return "\n".join(lines)

    def _strip_internal_case_fields(self, raw_item: Dict[str, Any], default_module: str = "") -> Dict[str, Any]:
        item = raw_item if isinstance(raw_item, dict) else {}
        module_name = str(item.get("module") or default_module or "未分类").strip() or default_module or "未分类"
        priority = str(item.get("priority") or "P3").strip() or "P3"
        title = str(item.get("title") or item.get("name") or "未命名用例").strip() or "未命名用例"
        precondition = str(item.get("precondition") or "").strip()

        steps: List[Dict[str, str]] = []
        raw_steps = item.get("steps") or []
        if isinstance(raw_steps, list):
            for raw_step in raw_steps:
                if not isinstance(raw_step, dict):
                    continue
                action = str(raw_step.get("action") or raw_step.get("step") or "").strip()
                expected = str(raw_step.get("expected") or raw_step.get("result") or "").strip()
                if action or expected:
                    steps.append({
                        "action": action,
                        "expected": expected,
                    })

        return {
            "priority": priority,
            "module": module_name,
            "title": title,
            "precondition": precondition,
            "steps": steps,
        }

    def _build_test_case_dedup_key(self, item: Dict[str, Any], include_module: bool = True) -> Tuple[Any, ...]:
        def normalize_text(value: Any) -> str:
            return re.sub(r"\s+", " ", str(value or "")).strip()

        step_actions = tuple(
            normalize_text(step.get("action"))
            for step in item.get("steps") or []
            if isinstance(step, dict) and normalize_text(step.get("action"))
        )
        title = normalize_text(item.get("title"))
        precondition = normalize_text(item.get("precondition"))
        module_name = normalize_text(item.get("module")) if include_module else ""
        return (module_name, title, precondition, step_actions)

    def _deduplicate_test_case_items(
        self,
        module_case_items: List[Dict[str, Any]],
        supplement_case_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        normalized_module_items = self.case_design_service.normalize_module_cases(module_case_items)
        normalized_supplement_items = self.case_design_service.normalize_module_cases(
            supplement_case_items,
            default_module="跨模块",
        )

        deduplicated_items: List[Dict[str, Any]] = []
        module_seen_keys = set()
        cross_module_seen_keys = set()

        for item in normalized_module_items:
            cleaned_item = self._strip_internal_case_fields(item)
            module_key = self._build_test_case_dedup_key(cleaned_item, include_module=True)
            if module_key in module_seen_keys:
                continue
            module_seen_keys.add(module_key)
            cross_module_seen_keys.add(self._build_test_case_dedup_key(cleaned_item, include_module=False))
            deduplicated_items.append(cleaned_item)

        for item in normalized_supplement_items:
            cleaned_item = self._strip_internal_case_fields(item, default_module="跨模块")
            cross_module_key = self._build_test_case_dedup_key(cleaned_item, include_module=False)
            if cross_module_key in cross_module_seen_keys:
                continue
            cross_module_seen_keys.add(cross_module_key)
            deduplicated_items.append(cleaned_item)

        return deduplicated_items

    def _generate_global_test_case_supplements(
        self,
        modules: List[Dict[str, Any]],
        requirement: str,
        all_modules_summary: str,
        module_case_results: List[Dict[str, Any]],
        skill_prompt: str,
        execution_params: Optional[Dict[str, Any]] = None,
        status_callback=None,
    ) -> List[Dict[str, Any]]:
        coverage_summary = self._build_module_case_coverage_summary(modules, module_case_results)
        if not coverage_summary.strip():
            return []

        if status_callback:
            status_callback("🧩 正在补充跨模块和全局规则测试用例...")

        prompt_prefix = f"""
{skill_prompt}

---------------------------------------------------
👑 **[重要] 全局补漏指令** 👑

请基于“已有模块级测试用例覆盖摘要”，只补充目前尚未覆盖但高价值的测试用例。
你的输出必须聚焦以下类型：
1. 跨模块主流程和端到端业务链路
2. 全局业务规则、风控规则、限额规则、锁定规则
3. 角色权限差异、越权访问、状态流转
4. 异常逆向流程、边界条件、幂等、重复提交、并发冲突

禁止事项：
1. 禁止重复已有模块级用例
2. 禁止改写或重述已有模块级用例
3. 禁止输出 tags、remark、id、source 等额外字段

如果没有需要新增的全局补漏用例，请返回：
{{"items": [], "summary": "无新增全局补漏用例"}}

请直接输出一个 JSON 对象，格式如下：
{{
  "items": [
    {{
      "priority": "P0/P1/P2/P3",
      "module": "跨模块",
      "title": "简短明确的测试标题",
      "precondition": "前置条件，可为空字符串",
      "steps": [
        {{
          "action": "步骤1",
          "expected": "步骤1对应的预期结果"
        }}
      ]
    }}
  ],
  "summary": "本次新增的全局补漏覆盖摘要"
}}

额外要求：
1. 每个步骤都必须有明确且非空的 expected
2. 预期结果必须与当前步骤一一对应
3. 只输出新增用例，不解释原因，不输出 Markdown
---------------------------------------------------

{self._format_test_case_preferences(execution_params)}

[功能模块总览]
{all_modules_summary}

[已有模块级测试用例覆盖摘要]
"""
        trimmed_requirement = self._trim_text_by_token_budget(
            text=str(requirement or ""),
            max_tokens=max(1, int(self.prompt_input_budget_tokens * 0.25)),
            preserve_tail=True,
            truncation_notice="\n\n[... 原始需求已按 token 预算截断 ...]\n\n",
        )
        prompt_suffix = f"""

[原始需求]
{trimmed_requirement}
"""
        coverage_summary_snippet = self._trim_text_for_prompt_slot(
            text=coverage_summary,
            prompt_prefix=prompt_prefix,
            prompt_suffix=prompt_suffix,
            preserve_tail=True,
            truncation_notice="\n\n[... 已有模块级用例摘要已按 token 预算截断 ...]\n\n",
        )
        prompt = f"{prompt_prefix}{coverage_summary_snippet}{prompt_suffix}"

        try:
            response = self.client.generate_completion(prompt)
        except Exception as error:
            logger.error(f"全局补漏测试用例生成失败: {error}")
            return []

        if not response:
            return []

        try:
            data = parse_json_markdown(response)
        except Exception as error:
            logger.error(f"全局补漏测试用例解析失败: {error}")
            return []

        raw_items: Any = []
        if isinstance(data, dict):
            raw_items = data.get("items")
        elif isinstance(data, list):
            raw_items = data

        if not isinstance(raw_items, list):
            return []

        normalized_items = self.case_design_service.normalize_module_cases(
            raw_items,
            default_module="跨模块",
        )
        return [self._strip_internal_case_fields(item, default_module="跨模块") for item in normalized_items]

    def _generate_module_test_cases(self, module: Dict, module_text: str, 
                                   module_images: List[Dict], skill_prompt: str,
                                   all_modules_summary: str, requirement: str,
                                   status_callback=None,
                                   execution_params: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """按模块生成结构化的测试用例 JSON 数据。"""
        module_name = module.get("name", "未命名模块")
        module_desc = module.get("description", "")
        module_pages = module.get("pages", [])
        safe_module_text = module_text or ""
        
        msg = f"  🔄 [{module_name}] 正在执行确定性 JSON 结构化生成..."
        if status_callback:
            status_callback(msg)
        else:
            logger.info(msg)
        
        prompt_prefix = f"""
{skill_prompt}

---------------------------------------------------
👑 **[重要] 结构化输出指令** 👑

为了确保工程稳定性，请严禁输出 Markdown 或任何解释性文字。
请直接输出一个 JSON 对象，格式如下：
{{
  "items": [
    {{
      "priority": "P0/P1/P2/P3",
      "module": "{module_name}",
      "title": "简短的测试标题",
      "precondition": "前置条件，可为空字符串",
      "steps": [
        {{
          "action": "步骤1",
          "expected": "步骤1对应的预期结果"
        }},
        {{
          "action": "步骤2",
          "expected": "步骤2对应的预期结果"
        }}
      ]
    }}
  ],
  "summary": "该模块用例设计的核心覆盖点简述"
}}

额外要求：
1. 用例等级严格只允许输出 P0、P1、P2、P3 四档。
2. 每个步骤都必须有非空 expected，且 expected 必须对应当前步骤。
3. 禁止把所有预期结果合并成一段总预期。
4. 一个步骤对应一个预期结果，禁止留空字符串。
---------------------------------------------------

{self._format_test_case_preferences(execution_params)}

[当前模块上下文]
模块名称：{module_name}
模块描述：{module_desc}
页码范围：{module_pages}

[模块文本内容]
"""
        prompt_suffix = f"""

{requirement}
"""
        module_text_snippet = self._trim_text_for_prompt_slot(
            text=str(safe_module_text),
            prompt_prefix=prompt_prefix,
            prompt_suffix=prompt_suffix,
        )
        prompt = f"""{prompt_prefix}{module_text_snippet}{prompt_suffix}"""
        response = self.client.generate_completion(prompt, files=module_images)
        
        if response:
            try:
                # 使用现有的快速解析器
                data = parse_json_markdown(response)
                if data and isinstance(data, dict) and "items" in data:
                    normalized_items = self.case_design_service.normalize_module_cases(
                        data["items"],
                        default_module=module_name
                    )
                    done_msg = f"    ✅ [{module_name}] 结构化数据生成完毕 (Count: {len(data['items'])})"
                    if status_callback:
                        status_callback(done_msg)
                    else:
                        logger.info(done_msg)
                    return normalized_items
            except Exception as e:
                logger.error(f"JSON Parsing failed for module {module_name}: {e}")
        
        fail_msg = f"    ⚠️ [{module_name}] 结构化生成失败，数据流断裂"
        if status_callback:
            status_callback(fail_msg)
        else:
            logger.warning(fail_msg)
        return []

    def _generate_module_requirement_analysis(self, module: Dict, module_text: str,
                                             module_images: List[Dict], skill_prompt: str,
                                             all_modules_summary: str, requirement: str) -> Dict[str, Any]:
        module_name = module.get("name", "未命名模块")
        module_desc = module.get("description", "")
        module_pages = module.get("pages", [])
        safe_module_text = module_text or ""
        prompt_prefix = f"""
{skill_prompt}

---------------------------------------------------
👑 **[重要] 结构化输出指令** 👑

请直接输出 JSON 对象，禁止输出 Markdown。
格式如下：
{{
  "module": "{module_name}",
  "summary": "模块业务摘要",
  "actors": ["参与角色"],
  "business_rules": ["规则1", "规则2"],
  "data_entities": ["实体1", "实体2"],
  "preconditions": ["前置条件"],
  "postconditions": ["后置条件"],
  "exceptions": ["异常或边界处理"],
  "risks": ["显性风险"],
  "open_questions": ["待确认问题"]
}}
---------------------------------------------------

[当前模块上下文]
模块名称：{module_name}
模块描述：{module_desc}
页码范围：{module_pages}

[完整模块结构]
{all_modules_summary}

[模块文本内容]
"""
        prompt_suffix = f"""

{requirement}
"""
        module_text_snippet = self._trim_text_for_prompt_slot(
            text=str(safe_module_text),
            prompt_prefix=prompt_prefix,
            prompt_suffix=prompt_suffix,
        )
        prompt = f"""{prompt_prefix}{module_text_snippet}{prompt_suffix}"""

        response = self.client.generate_completion(prompt, files=module_images if module_images else [])
        data = parse_json_markdown(response) if response else None
        if isinstance(data, dict):
            return self.requirement_analysis_service.normalize_module_analysis(data, default_module=module_name)
        if response:
            return self.requirement_analysis_service.normalize_module_analysis({
                "module": module_name,
                "summary": response.strip(),
            }, default_module=module_name)
        return {}

    def _generate_module_flowchart(self, module: Dict, module_text: str,
                                  module_images: List[Dict], skill_prompt: str,
                                  all_modules_summary: str, requirement: str) -> Dict[str, Any]:
        module_name = module.get("name", "未命名模块")
        module_desc = module.get("description", "")
        module_pages = module.get("pages", [])
        safe_module_text = module_text or ""
        prompt_prefix = f"""
{skill_prompt}

---------------------------------------------------
👑 **[重要] 结构化输出指令** 👑

请直接输出 JSON 对象，禁止输出 Markdown。
格式如下：
{{
  "module": "{module_name}",
  "title": "该模块流程图标题",
  "summary": "该模块流程说明",
  "mermaid": "flowchart TD\\nA[开始] --> B[处理]\\nB --> C[结束]",
  "warnings": ["待确认的规则或风险"]
}}

额外要求：
1. mermaid 字段中只保留 Mermaid 图代码。
2. 必须使用 flowchart TD 或 graph TD 形式。
3. 同一模块优先绘制主流程，必要时补充异常分支。
---------------------------------------------------

[当前模块上下文]
模块名称：{module_name}
模块描述：{module_desc}
页码范围：{module_pages}

[完整模块结构]
{all_modules_summary}

[模块文本内容]
"""
        prompt_suffix = f"""

{requirement}
"""
        module_text_snippet = self._trim_text_for_prompt_slot(
            text=str(safe_module_text),
            prompt_prefix=prompt_prefix,
            prompt_suffix=prompt_suffix,
        )
        prompt = f"""{prompt_prefix}{module_text_snippet}{prompt_suffix}"""

        response = self.client.generate_completion(prompt, files=module_images if module_images else [])
        data = parse_json_markdown(response) if response else None
        if isinstance(data, dict):
            return self.flowchart_service.normalize_module_flowchart(data, default_module=module_name)

        mermaid_code = sanitize_mermaid_code(response)
        if mermaid_code:
            return self.flowchart_service.normalize_module_flowchart({
                "module": module_name,
                "title": module_name,
                "summary": module_desc,
                "mermaid": mermaid_code,
            }, default_module=module_name)
        return {}

    def _run_multi_role_with_context(self, requirement: str, combined_text: str,
                                     vision_files_map: Dict, pages: List, file_basename: str,
                                     modules: List[Dict], roles: List[str],
                                     page_texts: Optional[Dict[int, str]] = None,
                                     status_callback=None) -> Optional[str]:
        """多角色评审（使用上下文）。"""
        role_prompts = self._load_role_prompts(roles)
        if not role_prompts:
            return None

        # 纯文本模式：当无 PDF 提取内容且无图片时，走纯文本路径
        # 关键修复：优先使用 combined_text（PDF 提取内容），其次才是用户手输的 requirement
        effective_requirement = combined_text if combined_text else requirement
        if not combined_text and not vision_files_map:
            return self._multi_role_text_only(effective_requirement, role_prompts)

        all_modules_summary = "\n".join(
            [f"  - {m['name']}（第 {m.get('pages', [])} 页）: {m.get('description', '')}" 
             for m in modules]
        )

        tasks, total_tasks = self._build_multi_role_tasks(modules, role_prompts)
        logger.info(f"📊 总任务数: {total_tasks}")
        if status_callback:
            status_callback("🧠 专家角色并行深度分析...")

        # 区分普通专家和架构师
        expert_tasks = []
        for role_id, idx, module in tasks:
            if role_id == 'architect':
                continue
            expert_tasks.append((role_id, idx, module))

        results = self._run_parallel_role_reviews(
            expert_tasks=expert_tasks,
            role_prompts=role_prompts,
            pages=pages,
            page_texts=page_texts,
            combined_text=combined_text,
            vision_files_map=vision_files_map,
            all_modules_summary=all_modules_summary,
            effective_requirement=effective_requirement,
            status_callback=status_callback,
            total_tasks=total_tasks,
        )

        self._apply_architect_arbitration(
            results=results,
            role_prompts=role_prompts,
            effective_requirement=effective_requirement,
            status_callback=status_callback,
        )

        return self._serialize_multi_role_results(results, modules)

    def _run_impact_analysis_from_context(
            self, combined_text: str, req_text: str,
            preparsed_data: Optional[Dict], skill_prompt: Optional[str]) -> Optional[str]:
        """从 Handler 字典直接调用的影响面分析入口，自动获取 V2 文件并拼接上下文。"""
        if not skill_prompt:
            return None
        v2_path = preparsed_data.get("v2_file_path") if preparsed_data else None
        v2_text = ""
        if v2_path:
            v2_text = self._extract_file_content(v2_path)
        comparison_context = f"""
[版本 V1.0 (旧)]
{combined_text if combined_text else req_text}

[版本 V2.0 (新)]
{v2_text}
"""
        return self._run_impact_analysis(comparison_context, skill_prompt)

    def _run_impact_analysis(self, comparison_context: str, skill_prompt: str) -> Optional[str]:
        """执行影响面分析。"""
        full_prompt = f"""
        {skill_prompt}

        **重要约束：输出中禁止出现任何人名，直接输出分析报告。**
        **语言约束：所有输出必须使用纯简体中文，严禁中英混杂，禁止出现英文括号注释。**

        ---

        {comparison_context}
        """
        logger.info("⚡ 正在执行影响面分析...")
        return self.client.generate_completion(full_prompt)

    def _multi_role_text_only(self, requirement: str, role_prompts: Dict[str, str]) -> str:
        """多角色纯文本评审（无文件）。"""
        structured_result = {}
        
        for role_id, skill_prompt in role_prompts.items():
            role_label = self.review_roles[role_id]["label"]
            full_prompt = f"""
            {skill_prompt}
            
            **重要约束：输出中禁止出现任何人名，直接输出评审内容。**
            **语言约束：所有输出必须使用纯简体中文，严禁中英混杂，禁止出现英文括号注释。**
            
            ---
            
            [用户输入需求]
            {requirement}
            """
            logger.info(f"📝 {role_label} 纯文本评审...")
            result = self.client.generate_completion(full_prompt)
            structured_result[role_id] = {
                "label": role_label,
                "content": result or "> ⚠️ 评审未获得有效结果"
            }
        
        return json.dumps(structured_result, ensure_ascii=False)

    def _run_architect_arbitration(self, reports: str, skill_prompt: str, requirement: str) -> str:
        """执行资深架构师仲裁逻辑。"""
        # 使用 Any 绕过 Pyre2 对 slice 类型的误判
        safe_req: Any = requirement or ""
        req_preview = str(safe_req)[:3000]  # type: ignore
        
        prompt = f"""{skill_prompt}

[当前全量需求内容预览]
{req_preview}

---
[待仲裁的专家评审汇总]
{reports}

请根据以上专家意见，识别冲突、达成共识，并给出最终仲裁执行建议："""

        logger.info("⚖️ 正在进行架构仲裁决策...")
        response = self.client.generate_completion(prompt)
        return response or "> ⚠️ 仲裁失败：未获得有效输出"

    def _extract_actionable_findings(self, markdown_text: str) -> List[Dict]:
        """从 Markdown 文本中提取结构化风险项（Findings）。
        优先从 <findings_json> 标签中解析，否则降级使用 AI 提取。
        """
        # 1. 尝试正则表达式提取嵌入的 JSON
        import re
        json_pattern = re.compile(r'<findings_json>(.*?)</findings_json>', re.DOTALL)
        match = json_pattern.search(markdown_text)
        
        if match:
            try:
                findings_str = match.group(1).strip()
                findings = parse_json_markdown(findings_str)
                if isinstance(findings, list):
                    return findings
            except Exception as e:
                print(f"Error parsing embedded findings: {e}")

        # 2. 降级逻辑：使用 AI 提取（向后兼容旧版 Prompt）
        prompt_prefix = """分析以下评审报告，提取出所有明确的“改进建议”或“风险点”。
请以 JSON 数组格式返回，包含：
1. category: 风险分类，必须且限定为 ['逻辑缺陷', '安全隐患', '易用性建议'] 之一
2. risk_level: 风险等级 (H/M/L)
3. description: 简明风险描述
4. source_quote: 能直接支撑该问题判断的需求原文或报告原句，尽量保留原话；如果无法定位则返回空字符串
5. suggestion: 具体的建议修复措施

报告内容：
"""
        prompt_suffix = """

请直接以 JSON 数组形式返回："""
        markdown_text_preview = self._trim_text_for_prompt_slot(
            text=str(markdown_text),
            prompt_prefix=prompt_prefix,
            prompt_suffix=prompt_suffix,
        )
        prompt = f"""{prompt_prefix}{markdown_text_preview}{prompt_suffix}"""
        
        try:
            response = self.client.generate_completion(prompt)
            findings = parse_json_markdown(response)
            if isinstance(findings, list):
                return findings
        except Exception as e:
            logger.error(f"Findings extraction failed: {e}")
        return []
