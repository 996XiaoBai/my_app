import pytest
from unittest.mock import patch, MagicMock
from test_platform.core.services.review_service import ReviewService
from test_platform.core.services.document_service import DocumentService
from test_platform.core.data_generators.test_case_exporter import parse_test_cases_from_text
from test_platform.core.skill_modes import SkillMode, SKILL_NAME_MAP
from test_platform.core.db.db_manager import db_manager
import json

class TestServices:
    
    @patch('test_platform.core.services.review_service.DifyClient')
    def setUp(self, MockDifyClient):
        self.mock_client = MockDifyClient.return_value
        self.review_service = ReviewService()
        self.review_service.client = self.mock_client
        self.document_service = DocumentService(self.mock_client, "test_user")

    @patch('test_platform.core.services.review_service.DifyClient')
    def test_identify_modules(self, MockDifyClient):
        # 准备服务
        mock_client = MockDifyClient.return_value
        review_service = ReviewService()
        review_service.client = mock_client
        
        # 模拟 LLM 正常返回 JSON
        mock_client.generate_completion.return_value = '''```json
        [
            {"name": "登录", "pages": [1], "description": "用户登录"}
        ]
        ```'''
        
        modules = review_service._identify_modules("测试文本", "test.txt")
        assert modules is not None
        assert len(modules) == 1
        assert modules[0]["name"] == "登录"
        
    @patch('test_platform.core.services.review_service.DifyClient')
    def test_identify_modules_bad_json(self, MockDifyClient):
        mock_client = MockDifyClient.return_value
        review_service = ReviewService()
        review_service.client = mock_client
        
        # 模拟 LLM 乱返回
        mock_client.generate_completion.return_value = "我听不懂你在说什么"
        
        modules = review_service._identify_modules("测试文本", "test.txt")
        assert modules is None

    @patch('test_platform.core.services.document_service.read_document')
    def test_document_service_non_pdf(self, mock_read):
        document_service = DocumentService()
        mock_read.return_value = ("Hello Markdown", False)
        
        # 我们假设 is_supported 返回 True
        with patch('test_platform.core.services.document_service.is_supported', return_value=True):
            # mock os.path.exists
            with patch('os.path.exists', return_value=True):
                text, vision_map, pages = document_service.process_file("dummy.md")
                assert text == "Hello Markdown"
                assert vision_map == {}
                assert len(pages) == 1
                assert pages[0].text == "Hello Markdown"

    @patch('test_platform.core.services.review_service.DifyClient')
    def test_generate_module_test_cases_normalizes_legacy_string_steps(self, MockDifyClient):
        mock_client = MockDifyClient.return_value
        review_service = ReviewService()
        review_service.client = mock_client

        mock_client.generate_completion.return_value = json.dumps({
            "items": [
                {
                    "priority": "P1",
                    "module": "登录",
                    "title": "登录成功",
                    "steps": "1. 输入账号\n2. 点击登录",
                    "expected": "进入首页"
                }
            ],
            "summary": "覆盖登录主流程"
        }, ensure_ascii=False)

        cases = review_service._generate_module_test_cases(
            module={"name": "登录", "description": "登录模块", "pages": [1]},
            module_text="用户输入账号密码并登录",
            module_images=[],
            skill_prompt="你是测试专家",
            all_modules_summary="- 登录",
            requirement=""
        )

        assert len(cases) == 1
        assert isinstance(cases[0]["steps"], list)
        assert cases[0]["steps"][0]["action"] == "输入账号"
        assert cases[0]["steps"][1]["action"] == "点击登录"
        assert cases[0]["steps"][1]["expected"] == "进入首页"
        assert "tags" not in cases[0]
        assert "remark" not in cases[0]

    @patch('test_platform.core.services.review_service.DifyClient')
    def test_generate_module_test_cases_prompt_excludes_tags_and_remark(self, MockDifyClient):
        mock_client = MockDifyClient.return_value
        review_service = ReviewService()
        review_service.client = mock_client

        mock_client.generate_completion.return_value = json.dumps({
            "items": [],
            "summary": "无结果"
        }, ensure_ascii=False)

        review_service._generate_module_test_cases(
            module={"name": "登录", "description": "登录模块", "pages": [1]},
            module_text="用户输入账号密码并登录",
            module_images=[],
            skill_prompt="你是测试专家",
            all_modules_summary="- 登录",
            requirement=""
        )

        prompt = mock_client.generate_completion.call_args[0][0]
        assert '"tags"' not in prompt
        assert '"remark"' not in prompt
        assert "标签1|标签2" not in prompt
        assert "补充说明" not in prompt

    def test_parse_test_cases_from_text_normalizes_case_suite_contract(self):
        payload = json.dumps({
            "items": [
                {
                    "id": "case-1",
                    "module": "登录",
                    "title": "登录成功",
                    "priority": "P1",
                    "precondition": "账号可用",
                    "steps": [
                        {"action": "输入账号", "expected": ""},
                        {"action": "点击登录", "expected": "进入首页"}
                    ]
                }
            ],
            "summary": "覆盖登录主流程"
        }, ensure_ascii=False)

        cases = parse_test_cases_from_text(payload)

        assert len(cases) == 1
        assert cases[0]["name"] == "登录成功"
        assert cases[0]["module"] == "登录"
        assert cases[0]["steps"][0]["step"] == "输入账号"
        assert cases[0]["steps"][1]["expected"] == "进入首页"

    def test_review_service_initialization(self):
        # 正常初始化应该包含 client
        rs = ReviewService()
        assert rs.client is not None
        assert hasattr(rs, 'config')

    @patch('test_platform.core.services.review_service.DifyClient')
    def test_review_service_uses_safe_default_worker_limits(self, MockDifyClient, monkeypatch):
        monkeypatch.delenv("REVIEW_MAX_WORKERS_SINGLE_ROLE", raising=False)
        monkeypatch.delenv("REVIEW_MAX_WORKERS_MULTI_ROLE", raising=False)

        review_service = ReviewService()
        review_service.client = MockDifyClient.return_value

        assert review_service.max_workers_single_role == 1
        assert review_service.max_workers_multi_role == 1

    @patch('test_platform.core.services.review_service.DifyClient')
    def test_review_service_allows_worker_limits_from_env(self, MockDifyClient, monkeypatch):
        monkeypatch.setenv("REVIEW_MAX_WORKERS_SINGLE_ROLE", "3")
        monkeypatch.setenv("REVIEW_MAX_WORKERS_MULTI_ROLE", "4")

        review_service = ReviewService()
        review_service.client = MockDifyClient.return_value

        assert review_service.max_workers_single_role == 3
        assert review_service.max_workers_multi_role == 4

    @patch('test_platform.core.services.review_service.DifyClient')
    def test_review_service_caps_prompt_input_budget_from_env(self, MockDifyClient, monkeypatch):
        monkeypatch.setenv("LLM_CONTEXT_WINDOW_TOKENS", "1050000")
        monkeypatch.setenv("LLM_RESERVED_OUTPUT_TOKENS", "128000")
        monkeypatch.setenv("LLM_RESERVED_PROMPT_TOKENS", "32000")
        monkeypatch.setenv("LLM_MAX_PROMPT_INPUT_TOKENS", "60000")

        review_service = ReviewService()
        review_service.client = MockDifyClient.return_value

        assert review_service.prompt_input_budget_tokens == 60000

    @patch('test_platform.core.services.review_service.DifyClient')
    def test_trim_simple_skill_context_uses_token_budget(self, MockDifyClient, monkeypatch):
        monkeypatch.setenv("LLM_CONTEXT_WINDOW_TOKENS", "120")
        monkeypatch.setenv("LLM_RESERVED_OUTPUT_TOKENS", "0")
        monkeypatch.setenv("LLM_RESERVED_PROMPT_TOKENS", "0")
        monkeypatch.setenv("LLM_TOKENIZER_ENCODING", "o200k_base")

        review_service = ReviewService()
        review_service.client = MockDifyClient.return_value

        long_text = ("HEAD_SECTION\n" * 20) + ("MIDDLE_SECTION\n" * 200) + ("TAIL_SECTION\n" * 20)

        trimmed = review_service._trim_simple_skill_context(long_text)

        assert trimmed != long_text
        assert "已按 token 预算截断中间内容" in trimmed
        assert "HEAD_SECTION" in trimmed
        assert "TAIL_SECTION" in trimmed
        assert review_service._count_text_tokens(trimmed) <= (
            review_service.prompt_input_budget_tokens - review_service.TOKEN_BUDGET_SAFETY_MARGIN
        )

    @patch('test_platform.core.services.review_service.DifyClient')
    def test_generate_module_requirement_analysis_limits_prompt_by_token_budget(self, MockDifyClient, monkeypatch):
        monkeypatch.setenv("LLM_CONTEXT_WINDOW_TOKENS", "500")
        monkeypatch.setenv("LLM_RESERVED_OUTPUT_TOKENS", "0")
        monkeypatch.setenv("LLM_RESERVED_PROMPT_TOKENS", "0")
        monkeypatch.setenv("LLM_TOKENIZER_ENCODING", "o200k_base")

        mock_client = MockDifyClient.return_value
        mock_client.generate_completion.return_value = "{}"
        review_service = ReviewService()
        review_service.client = mock_client

        module_text = ("HEAD_MODULE\n" * 50) + ("BODY_MODULE\n" * 800) + ("TAIL_MARKER\n" * 50)

        review_service._generate_module_requirement_analysis(
            module={"name": "登录", "description": "登录模块", "pages": [1]},
            module_text=module_text,
            module_images=[],
            skill_prompt="你是分析专家",
            all_modules_summary="- 登录",
            requirement="请分析登录流程",
        )

        prompt = mock_client.generate_completion.call_args[0][0]

        assert review_service._count_text_tokens(prompt) <= review_service.prompt_input_budget_tokens
        assert "HEAD_MODULE" in prompt
        assert "TAIL_MARKER" not in prompt


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_review_normalizes_test_cases_alias_and_uses_module_skill_handler(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    monkeypatch.setattr(db_manager, "add_run_record", lambda **kwargs: True)
    monkeypatch.setattr(
        review_service,
        "parse_requirement",
        lambda *args, **kwargs: {
            "context": {
                "combined_text": "登录需求说明" * 20,
                "vision_files_map": {},
                "pages": [],
                "page_texts": {1: "登录需求说明"},
                "file_basename": "req.md",
                "requirement": "登录需求说明",
            },
            "modules": [{"name": "登录", "pages": [1], "description": "登录模块"}],
        },
    )

    captured = {}

    def fake_run_module_skill_mode(execution_context, skill_key, log_msg, run_mode, **kwargs):
        captured["skill_key"] = skill_key
        captured["run_mode"] = run_mode
        captured["file_basename"] = execution_context.file_basename
        return "module-result"

    monkeypatch.setattr(review_service, "_run_module_skill_mode", fake_run_module_skill_mode)

    result = review_service.run_review(requirement="登录需求", mode="test_cases")

    assert result == "module-result"
    assert captured["skill_key"] == SkillMode.TEST_CASE
    assert captured["run_mode"] == "test_case"
    assert captured["file_basename"] == "req.md"


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_single_skill_with_context_test_case_merges_global_supplements_and_deduplicates(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    modules = [
        {"name": "登录", "pages": [1], "description": "登录模块"},
        {"name": "购物车", "pages": [2], "description": "购物车模块"},
    ]

    monkeypatch.setattr(review_service, "_get_module_text", lambda module, _pages: f"{module['name']}正文")
    monkeypatch.setattr(review_service, "_get_module_images", lambda _module, _vision_map: [])

    def fake_generate_module_cases(module, *_args, **_kwargs):
        if module["name"] == "登录":
            return [
                {
                    "priority": "P1",
                    "module": "登录",
                    "title": "登录成功",
                    "precondition": "账号可用",
                    "steps": [
                        {"action": "输入正确账号密码", "expected": "账号密码输入成功"},
                        {"action": "点击登录", "expected": "进入首页"},
                    ],
                }
            ]
        return [
            {
                "priority": "P1",
                "module": "购物车",
                "title": "加入购物车成功",
                "precondition": "商品库存充足",
                "steps": [
                    {"action": "点击加入购物车", "expected": "购物车数量加一"},
                ],
            }
        ]

    monkeypatch.setattr(review_service, "_generate_module_test_cases", fake_generate_module_cases)
    monkeypatch.setattr(
        review_service,
        "_generate_global_test_case_supplements",
        lambda *_args, **_kwargs: [
            {
                "priority": "P1",
                "module": "跨模块",
                "title": "登录成功",
                "precondition": "账号可用",
                "steps": [
                    {"action": "输入正确账号密码", "expected": "账号密码输入成功"},
                    {"action": "点击登录", "expected": "进入首页"},
                ],
            },
            {
                "priority": "P0",
                "module": "跨模块",
                "title": "登录后加入购物车并提交订单",
                "precondition": "账号可用且商品库存充足",
                "steps": [
                    {"action": "登录成功", "expected": "进入首页"},
                    {"action": "将商品加入购物车", "expected": "购物车中出现目标商品"},
                    {"action": "提交订单", "expected": "订单创建成功"},
                ],
            },
        ],
    )

    result = review_service._run_single_skill_with_context(
        requirement="用户登录后可将商品加入购物车并提交订单",
        combined_text="登录和购物车相关需求",
        vision_files_map={},
        pages=[],
        file_basename="req.md",
        modules=modules,
        skill_prompt="你是测试专家",
        mode="test_case",
        execution_params={"strategy": "full"},
    )

    payload = json.loads(result)
    titles = [item["title"] for item in payload["items"]]

    assert titles.count("登录成功") == 1
    assert "登录后加入购物车并提交订单" in titles
    assert all("tags" not in item for item in payload["items"])
    assert all("remark" not in item for item in payload["items"])


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_review_routes_roles_to_review_handler(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    monkeypatch.setattr(db_manager, "add_run_record", lambda **kwargs: True)
    monkeypatch.setattr(
        review_service,
        "parse_requirement",
        lambda *args, **kwargs: {
            "context": {
                "combined_text": "登录需求说明" * 20,
                "vision_files_map": {},
                "pages": [],
                "page_texts": {1: "登录需求说明"},
                "file_basename": "req.md",
                "requirement": "登录需求说明",
            },
            "modules": [{"name": "登录", "pages": [1], "description": "登录模块"}],
        },
    )

    captured = {}

    def fake_run_review_mode(execution_context, roles, extra_prompt="", status_callback=None):
        captured["roles"] = roles
        captured["full_context"] = execution_context.full_context
        return "review-result"

    monkeypatch.setattr(review_service, "_run_review_mode", fake_run_review_mode)

    result = review_service.run_review(
        requirement="登录需求",
        mode="review",
        roles=["test", "product"],
    )

    assert result == "review-result"
    assert captured["roles"] == ["test", "product"]
    assert "登录需求说明" in captured["full_context"]


@patch('test_platform.core.services.review_service.DifyClient')
def test_load_role_prompts_adds_role_specific_guidance(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    monkeypatch.setattr(review_service, "load_skill", lambda skill_name: "基础评审提示词")

    prompts = review_service._load_role_prompts(["test", "security"])

    assert "test" in prompts
    assert "security" in prompts
    assert prompts["test"] != prompts["security"]
    assert "测试视角" in prompts["test"]
    assert "安全视角" in prompts["security"]
    assert "基础评审提示词" in prompts["test"]


@patch('test_platform.core.services.review_service.DifyClient')
def test_execute_mode_routes_log_diagnosis_with_correct_run_mode(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    execution_context = review_service._build_execution_context(
        context={
            "combined_text": "错误日志",
            "vision_files_map": {},
            "pages": [],
            "page_texts": {},
            "file_basename": "error.log",
            "requirement": "错误日志",
        },
        modules=[{"name": "日志模块", "pages": [1], "description": "日志诊断"}],
        requirement="错误日志",
    )

    captured = {}

    def fake_run_module_skill_mode(execution_context, skill_key, log_msg, run_mode, **kwargs):
        captured["skill_key"] = skill_key
        captured["run_mode"] = run_mode
        return "log-result"

    monkeypatch.setattr(review_service, "_run_module_skill_mode", fake_run_module_skill_mode)

    action_name, result = review_service._execute_mode(
        execution_context=execution_context,
        mode=SkillMode.LOG_DIAGNOSIS,
        roles=None,
        extra_prompt="",
        findings_text="",
    )

    assert action_name == "日志深度诊断"
    assert result == "log-result"
    assert captured["skill_key"] == SkillMode.LOG_DIAGNOSIS
    assert captured["run_mode"] == "log_diagnosis"


@patch('test_platform.core.services.review_service.DifyClient')
def test_execute_mode_routes_test_data_to_specialized_preparation_handler(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    execution_context = review_service._build_execution_context(
        context={
            "combined_text": "CREATE TABLE `xqd_live_room` (`room_id` bigint NOT NULL);",
            "vision_files_map": {},
            "pages": [],
            "page_texts": {},
            "file_basename": "schema.doc",
            "requirement": "直播间表结构",
        },
        modules=[{"name": "核心功能", "pages": [1], "description": "全文解析"}],
        requirement="直播间表结构",
    )

    captured = {}

    def fake_run_test_data_preparation_mode(execution_context, extra_prompt="", status_callback=None):
        captured["file_basename"] = execution_context.file_basename
        captured["extra_prompt"] = extra_prompt
        return "# 识别摘要\n"

    monkeypatch.setattr(review_service, "_run_test_data_preparation_mode", fake_run_test_data_preparation_mode)

    action_name, result = review_service._execute_mode(
        execution_context=execution_context,
        mode=SkillMode.TEST_DATA,
        roles=None,
        extra_prompt="优先直播场景",
        findings_text="",
    )

    assert action_name == "测试数据准备"
    assert result == "# 识别摘要\n"
    assert captured["file_basename"] == "schema.doc"
    assert captured["extra_prompt"] == "优先直播场景"


def test_skill_name_map_does_not_bind_weekly_report_to_local_skill_file():
    assert SkillMode.WEEKLY_REPORT not in SKILL_NAME_MAP


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_multi_role_with_context_preserves_structured_output_shape(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    monkeypatch.setattr(review_service, "load_skill", lambda skill_name: f"prompt:{skill_name}")
    monkeypatch.setattr(
        review_service,
        "_review_single_module",
        lambda module, module_text, module_images, skill_prompt, all_modules_summary, requirement: "模块评审结论",
    )

    result = review_service._run_multi_role_with_context(
        requirement="登录需求",
        combined_text="登录模块需要校验账号密码并记录日志。",
        vision_files_map={},
        pages=[],
        file_basename="req.md",
        modules=[{"name": "登录", "pages": [1, 2], "description": "登录模块"}],
        roles=["test"],
        page_texts={1: "登录页", 2: "校验规则"},
    )

    assert result is not None
    payload = json.loads(result)
    assert payload["test"]["label"] == "🧪 测试视角"
    assert "## 📦 登录（第 1-2 页）" in payload["test"]["content"]
    assert "模块评审结论" in payload["test"]["content"]


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_fulltext_skill_mode_uses_generate_completion_with_files(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    mock_client = MockDifyClient.return_value
    review_service.client = mock_client

    execution_context = review_service._build_execution_context(
        context={
            "combined_text": "支付需求说明",
            "vision_files_map": {
                1: {"type": "image", "upload_file_id": "img-1"},
                2: {"type": "image", "upload_file_id": "img-2"},
            },
            "pages": [],
            "page_texts": {1: "支付流程", 2: "退款流程"},
            "file_basename": "pay.pdf",
            "requirement": "支付需求说明",
        },
        modules=[
            {"name": "支付", "pages": [1], "description": "支付主流程"},
            {"name": "退款", "pages": [2], "description": "退款流程"},
        ],
        requirement="支付需求说明",
    )

    monkeypatch.setattr(review_service, "_load_augmented_skill_prompt", lambda *args, **kwargs: "你是测试方案专家")
    mock_client.generate_completion.return_value = "生成成功"

    result = review_service._run_fulltext_skill_mode(
        execution_context=execution_context,
        skill_key=SkillMode.TEST_PLAN,
        log_msg="生成测试方案",
        result_prefix="测试方案",
    )

    assert result == "# 测试方案：pay.pdf\n\n生成成功"
    _, kwargs = mock_client.generate_completion.call_args
    assert len(kwargs["files"]) == 2


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_simple_skill_mode_truncates_oversized_full_context(MockDifyClient, monkeypatch):
    monkeypatch.setenv("LLM_CONTEXT_WINDOW_TOKENS", "160")
    monkeypatch.setenv("LLM_RESERVED_OUTPUT_TOKENS", "0")
    monkeypatch.setenv("LLM_RESERVED_PROMPT_TOKENS", "0")
    monkeypatch.setenv("LLM_TOKENIZER_ENCODING", "o200k_base")
    review_service = ReviewService()
    mock_client = MockDifyClient.return_value
    review_service.client = mock_client

    execution_context = review_service._build_execution_context(
        context={
            "combined_text": "接口定义\n" + ("A " * 20000),
            "vision_files_map": {},
            "pages": [],
            "page_texts": {1: "接口定义"},
            "file_basename": "openapi.yaml",
            "requirement": "生成接口测试脚本",
        },
        modules=[{"name": "接口模块", "pages": [1], "description": "全文解析"}],
        requirement="生成接口测试脚本",
    )

    monkeypatch.setattr(review_service, "_load_augmented_skill_prompt", lambda *args, **kwargs: "你是接口测试专家")
    mock_client.generate_completion.return_value = "生成成功"

    result = review_service._run_simple_skill_mode(
        execution_context=execution_context,
        skill_key=SkillMode.REVIEW,
        log_msg="生成接口测试脚本",
        result_prefix="接口测试脚本",
    )

    assert result == "# 接口测试脚本：openapi.yaml\n\n生成成功"
    args, _ = mock_client.generate_completion.call_args
    prompt = args[0]
    assert "已按 token 预算截断中间内容" in prompt
    assert review_service._count_text_tokens(prompt) <= review_service.prompt_input_budget_tokens


@patch('test_platform.core.services.review_service.DifyClient')
def test_prepare_simple_skill_context_extracts_api_spec_summary(MockDifyClient):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    raw_context = """
openapi: 3.0.1
info:
  title: 支付中心接口
  version: 1.0.0
servers:
  - url: https://api.example.com
paths:
  /api/login:
    post:
      summary: 用户登录
      operationId: userLogin
      tags:
        - 认证
      parameters:
        - name: traceId
          in: header
          required: true
          schema:
            type: string
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                username:
                  type: string
                  description: 登录账号
                password:
                  type: string
                  description: 登录密码
      responses:
        '200':
          description: 成功
        '401':
          description: 认证失败
components:
  schemas:
    MassivePayload:
      type: object
      description: %s
""" % ("X" * 5000)

    prepared = review_service._prepare_simple_skill_context(
        raw_context,
        SkillMode.API_TEST_GEN,
        "openapi.yaml",
    )

    assert "[接口文档摘要]" in prepared
    assert "支付中心接口" in prepared
    assert "POST /api/login" in prepared
    assert "traceId" in prepared
    assert "username" in prepared
    assert "password" in prepared
    assert "200: 成功" in prepared
    assert "401: 认证失败" in prepared
    assert "MassivePayload" not in prepared
    assert len(prepared) < len(raw_context)


@patch('test_platform.core.services.review_service.DifyClient')
def test_prepare_simple_skill_context_extracts_ui_elements_from_html(MockDifyClient):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    raw_context = """
<html>
  <head>
    <title>登录页</title>
    <style>.hidden { display: none; }</style>
    <script>window.secretToken = "abc";</script>
  </head>
  <body>
    <h1>统一认证</h1>
    <form id="login-form" action="/login">
      <label for="username">账号</label>
      <input id="username" name="username" type="text" placeholder="请输入账号" />
      <label for="password">密码</label>
      <input id="password" name="password" type="password" placeholder="请输入密码" />
      <button id="submit-btn" type="submit">立即登录</button>
    </form>
    <a href="/forgot">忘记密码</a>
  </body>
</html>
"""

    prepared = review_service._prepare_simple_skill_context(
        raw_context,
        SkillMode.AUTO_SCRIPT_GEN,
        "login.html",
    )

    assert "[页面关键信息]" in prepared
    assert "标题：登录页" in prepared
    assert "统一认证" in prepared
    assert "form#login-form" in prepared
    assert "input#username" in prepared
    assert "请输入账号" in prepared
    assert "button#submit-btn" in prepared
    assert "立即登录" in prepared
    assert "a[href=/forgot]" in prepared
    assert "window.secretToken" not in prepared
    assert "display: none" not in prepared


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_api_test_generation_mode_returns_structured_payload_for_openapi_json(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    mock_client = MockDifyClient.return_value
    review_service.client = mock_client

    execution_context = review_service._build_execution_context(
        context={
            "combined_text": json.dumps(
                {
                    "openapi": "3.0.1",
                    "info": {"title": "默认模块", "version": "1.0.0"},
                    "paths": {
                        "/admin/platformGoods/adminList": {
                            "post": {
                                "summary": "adminList",
                                "tags": ["平台带货管理"],
                                "parameters": [
                                    {"name": "Authorization", "in": "header", "schema": {"type": "string"}}
                                ],
                                "requestBody": {
                                    "content": {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/PlatformGoodsQueryDto"}
                                        }
                                    }
                                },
                                "responses": {
                                    "200": {
                                        "content": {
                                            "application/json": {
                                                "schema": {"$ref": "#/components/schemas/ApiResponsePageResPlatformGoodsDto"}
                                            }
                                        }
                                    }
                                },
                            }
                        },
                        "/admin/platformGoods/add": {
                            "post": {
                                "summary": "add",
                                "tags": ["平台带货管理"],
                                "parameters": [
                                    {"name": "Authorization", "in": "header", "schema": {"type": "string"}}
                                ],
                                "requestBody": {
                                    "content": {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/PlatformGoodsAddDto"}
                                        }
                                    }
                                },
                                "responses": {
                                    "200": {
                                        "content": {
                                            "application/json": {
                                                "schema": {"$ref": "#/components/schemas/ApiResponse"}
                                            }
                                        }
                                    }
                                },
                            }
                        },
                    },
                    "components": {
                        "schemas": {
                            "ApiResponse": {
                                "type": "object",
                                "properties": {
                                    "state": {"$ref": "#/components/schemas/State"},
                                    "data": {"type": "object"},
                                },
                            },
                            "State": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "integer"},
                                    "msg": {"type": "string"},
                                },
                            },
                            "ApiResponsePageResPlatformGoodsDto": {
                                "type": "object",
                                "properties": {
                                    "state": {"$ref": "#/components/schemas/State"},
                                    "data": {"$ref": "#/components/schemas/PageResPlatformGoodsDto"},
                                },
                            },
                            "PageResPlatformGoodsDto": {
                                "type": "object",
                                "properties": {
                                    "count": {"type": "integer"},
                                    "list": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/PlatformGoodsDto"},
                                    },
                                },
                            },
                            "PlatformGoodsDto": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "title": {"type": "string"},
                                    "businessId": {"type": "integer"},
                                    "jumpUrl": {"type": "string"},
                                },
                            },
                            "PlatformGoodsQueryDto": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "businessId": {"type": "integer"},
                                },
                            },
                            "PlatformGoodsAddDto": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "businessId": {"type": "integer"},
                                    "jumpUrl": {"type": "string"},
                                },
                            },
                        }
                    },
                    "servers": [{"url": "https://edu-admin.dev1.dachensky.com"}],
                },
                ensure_ascii=False,
            ),
            "vision_files_map": {},
            "pages": [],
            "page_texts": {1: "openapi"},
            "file_basename": "platform-goods.json",
            "requirement": "生成接口测试脚本",
        },
        modules=[{"name": "接口模块", "pages": [1], "description": "全文解析"}],
        requirement="生成接口测试脚本",
    )

    monkeypatch.setattr(review_service, "_load_augmented_skill_prompt", lambda *args, **kwargs: "你是接口测试专家")
    monkeypatch.setattr(
        review_service.api_suite_repository,
        "save_suite",
        lambda **kwargs: {
            "suite_id": "api_suite_platform_goods",
            "suite_version": 1,
            "title": "默认模块",
            "case_count": 2,
            "scene_count": 1,
            "storage_path": "/tmp/api_suites/api_suite_platform_goods/v001.json",
        },
    )
    mock_client.generate_completion.return_value = "```python\nimport pytest\n\ndef test_demo():\n    assert True\n```"

    result = review_service._run_api_test_generation_mode(
        execution_context=execution_context,
        extra_prompt="",
    )

    payload = json.loads(result)
    assert payload["spec"]["title"] == "默认模块"
    assert payload["cases"]
    assert payload["scenes"]
    assert payload["link_plan"]["ordered_case_ids"]
    assert payload["suite"]["suite_id"] == "api_suite_platform_goods"
    assert "生成脚本" in payload["markdown"]
    assert "platformGoods_crud_flow" in payload["markdown"]
    prompt = mock_client.generate_completion.call_args.args[0]
    assert "结构化接口资产" in prompt
    assert "关联场景" in prompt


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_api_test_generation_mode_executes_suite_when_enabled(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    mock_client = MockDifyClient.return_value
    review_service.client = mock_client

    execution_context = review_service._build_execution_context(
        context={
            "combined_text": json.dumps(
                {
                    "openapi": "3.0.1",
                    "info": {"title": "默认模块", "version": "1.0.0"},
                    "paths": {
                        "/admin/platformGoods/add": {
                            "post": {
                                "summary": "add",
                                "tags": ["平台带货管理"],
                                "requestBody": {
                                    "content": {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/PlatformGoodsAddDto"}
                                        }
                                    }
                                },
                                "responses": {
                                    "200": {
                                        "content": {
                                            "application/json": {
                                                "schema": {"$ref": "#/components/schemas/ApiResponse"}
                                            }
                                        }
                                    }
                                },
                            }
                        },
                    },
                    "components": {
                        "schemas": {
                            "ApiResponse": {
                                "type": "object",
                                "properties": {
                                    "state": {"$ref": "#/components/schemas/State"},
                                    "data": {"type": "object"},
                                },
                            },
                            "State": {
                                "type": "object",
                                "properties": {
                                    "code": {"type": "integer"},
                                    "msg": {"type": "string"},
                                },
                            },
                            "PlatformGoodsAddDto": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "businessId": {"type": "integer"},
                                },
                            },
                        }
                    },
                    "servers": [{"url": "https://edu-admin.dev1.dachensky.com"}],
                },
                ensure_ascii=False,
            ),
            "vision_files_map": {},
            "pages": [],
            "page_texts": {1: "openapi"},
            "file_basename": "platform-goods.json",
            "requirement": "生成并执行接口测试",
        },
        modules=[{"name": "接口模块", "pages": [1], "description": "全文解析"}],
        requirement="生成并执行接口测试",
    )

    monkeypatch.setattr(review_service, "_load_augmented_skill_prompt", lambda *args, **kwargs: "你是接口测试专家")
    monkeypatch.setattr(
        review_service.api_suite_repository,
        "save_suite",
        lambda **kwargs: {
            "suite_id": "api_suite_platform_goods",
            "suite_version": 2,
            "title": "默认模块",
            "case_count": 1,
            "scene_count": 0,
            "storage_path": "/tmp/api_suites/api_suite_platform_goods/v002.json",
        },
    )
    mock_client.generate_completion.return_value = "```python\nimport pytest\n\ndef test_demo():\n    assert True\n```"
    monkeypatch.setattr(
        review_service.api_test_execution_service,
        "execute_pack",
        lambda **kwargs: {
            "status": "passed",
            "summary": "执行 1 条 pytest 用例，全部通过。",
            "stats": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            },
            "artifacts": {
                "run_dir": "/tmp/api-run",
                "junit_xml": "/tmp/api-run/junit.xml",
            },
        },
    )
    monkeypatch.setattr(
        review_service.api_report_service,
        "build_report",
        lambda **kwargs: {
            "status": "passed",
            "headline": "默认模块：执行通过",
            "summary_lines": ["总 1 / 通过 1 / 失败 0 / 异常 0 / 跳过 0"],
            "failure_cases": [],
            "artifact_labels": [{"key": "run_dir", "label": "运行目录", "value": "/tmp/api-run"}],
        },
    )

    result = review_service._run_api_test_generation_mode(
        execution_context=execution_context,
        extra_prompt="",
        params={"execute": True, "base_url": "https://edu-admin.dev1.dachensky.com"},
    )

    payload = json.loads(result)
    assert payload["execution"]["status"] == "passed"
    assert payload["suite"]["suite_version"] == 2
    assert payload["report"]["headline"] == "默认模块：执行通过"
    assert "## 执行结果" in payload["markdown"]


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_api_test_generation_mode_reuses_manual_script_without_calling_llm(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    mock_client = MockDifyClient.return_value
    review_service.client = mock_client

    execution_context = review_service._build_execution_context(
        context={
            "combined_text": "忽略原始文档",
            "vision_files_map": {},
            "pages": [],
            "page_texts": {},
            "file_basename": "platform-goods.json",
            "requirement": "执行当前脚本",
        },
        modules=[{"name": "接口模块", "pages": [1], "description": "全文解析"}],
        requirement="执行当前脚本",
    )

    monkeypatch.setattr(review_service, "_load_augmented_skill_prompt", lambda *args, **kwargs: "你是接口测试专家")
    monkeypatch.setattr(
        review_service.api_test_execution_service,
        "execute_pack",
        lambda **kwargs: {
            "status": "passed",
            "summary": "执行当前脚本完成。",
            "stats": {
                "total": 1,
                "passed": 1,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            },
            "artifacts": {},
        },
    )

    result = review_service._run_api_test_generation_mode(
        execution_context=execution_context,
        extra_prompt="",
        params={
            "execute": True,
            "manual_script": "import pytest\n\ndef test_manual():\n    assert True\n",
            "pack_payload": {
                "summary": "已生成接口测试资产。",
                "spec": {
                    "title": "默认模块",
                    "servers": [{"url": "https://example.com"}],
                    "auth_profile": {"required_headers": [], "required_cookies": []},
                    "resources": [],
                    "operations": [],
                },
                "cases": [],
                "scenes": [],
            },
        },
    )

    payload = json.loads(result)
    assert payload["script"].startswith("import pytest")
    assert payload["execution"]["status"] == "passed"
    mock_client.generate_completion.assert_not_called()


@patch('test_platform.core.services.review_service.DifyClient')
def test_get_module_images_skips_invalid_upload_file_id(MockDifyClient):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    valid_image = {
        "type": "image",
        "transfer_method": "local_file",
        "upload_file_id": "78738230-a3b7-4832-8a0d-7c9f9a9a76f7",
    }
    invalid_image = {
        "type": "image",
        "transfer_method": "local_file",
        "upload_file_id": "mock_id_1742459508",
    }

    images = review_service._get_module_images(
        {"name": "核心功能", "pages": [1, 2], "description": "全文解析"},
        {
            1: invalid_image,
            2: valid_image,
        },
    )

    assert images == [valid_image]


@patch('test_platform.core.services.review_service.RequirementContextService')
@patch('test_platform.core.services.review_service.DifyClient')
def test_review_service_initializes_context_service_with_pdf_context_builder(MockDifyClient, MockRequirementContextService):
    ReviewService()

    _, kwargs = MockRequirementContextService.call_args
    assert callable(kwargs["pdf_context_builder"])


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_single_skill_with_context_returns_error_when_test_case_items_are_empty(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    monkeypatch.setattr(review_service, "_generate_module_test_cases", lambda *args, **kwargs: [])

    result = review_service._run_single_skill_with_context(
        requirement="登录需求",
        combined_text="登录功能说明",
        vision_files_map={},
        pages=[],
        file_basename="req.md",
        modules=[{"name": "核心功能", "pages": [1], "description": "全文解析"}],
        skill_prompt="你是测试专家",
        mode="test_case",
        page_texts={1: "登录功能说明"},
    )

    assert result is not None
    assert result.startswith("Error:")
    assert "核心功能" in result


@patch('test_platform.core.services.review_service.DifyClient')
def test_run_review_marks_error_result_as_fail_status(MockDifyClient, monkeypatch):
    review_service = ReviewService()
    review_service.client = MockDifyClient.return_value

    execution_context = review_service._build_execution_context(
        context={
            "combined_text": "登录说明",
            "vision_files_map": {},
            "pages": [],
            "page_texts": {1: "登录说明"},
            "file_basename": "req.md",
            "requirement": "登录说明",
        },
        modules=[{"name": "核心功能", "pages": [1], "description": "全文解析"}],
        requirement="登录说明",
    )

    monkeypatch.setattr(review_service, "_resolve_execution_context", lambda *args, **kwargs: (execution_context, None))
    monkeypatch.setattr(
        review_service,
        "_execute_mode",
        lambda *args, **kwargs: ("测试用例生成", "Error: 测试用例生成失败"),
    )

    captured = {}

    def fake_add_run_record(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(db_manager, "add_run_record", fake_add_run_record)

    result = review_service.run_review(requirement="登录说明", mode="test_case")

    assert result == "Error: 测试用例生成失败"
    assert captured["status"] == "fail"
