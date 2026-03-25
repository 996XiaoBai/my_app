import json

from test_platform.core.services.result_contracts import (
    build_api_test_pack,
    build_case_suite,
    build_flowchart_pack,
    build_requirement_analysis_pack,
    build_test_case_review_payload,
    build_test_data_pack,
    normalize_flowchart_item,
    sanitize_mermaid_code,
)


def test_build_case_suite_enforces_priority_order_and_step_expectations():
    suite = build_case_suite(
        [
            {
                "priority": "unknown",
                "module": "登录",
                "title": "登录失败兜底",
                "steps": ["输入错误账号", "点击登录"],
                "expected": "展示账号输入校验结果\n提示账号或密码错误",
            },
            {
                "priority": "P0",
                "module": "支付",
                "title": "支付成功",
                "steps": [
                    {"action": "提交订单", "expected": "订单提交成功"},
                    {"action": "完成支付", "expected": "支付状态更新为成功"},
                ],
            },
            {
                "priority": "P1",
                "module": "登录",
                "title": "登录成功",
                "steps": [
                    {"action": "输入正确账号", "expected": "账号输入成功"},
                    {"action": "点击登录", "expected": "进入首页"},
                ],
            },
        ],
        summary="覆盖登录与支付主流程",
    )

    assert [item["priority"] for item in suite["items"]] == ["P0", "P1", "P3"]
    assert suite["items"][2]["steps"][0]["expected"] == "展示账号输入校验结果"
    assert suite["items"][2]["steps"][1]["expected"] == "提示账号或密码错误"
    assert suite["markdown"].startswith("# 智能测试用例")
    assert "- 用例等级：P0" in suite["markdown"]
    assert "- 步骤描述：\n  1. 步骤：提交订单\n     - 预期结果：订单提交成功" in suite["markdown"]


def test_build_case_suite_markdown_keeps_case_fields_in_template_order():
    suite = build_case_suite(
        [
            {
                "priority": "P0",
                "module": "内容标识传",
                "title": "测试环境 appid 与送审地址申请信息完整性校验",
                "precondition": "已具备提审邮箱和申请字段说明",
                "steps": [
                    {"action": "准备申请邮件内容", "expected": "邮件中包含产品名称、审核回调地址、下线地址、服务器出口 IP"},
                    {"action": "发送至指定邮箱", "expected": "邮件发送成功"},
                ],
            }
        ],
        summary="统一脑图模板输出顺序。",
    )

    markdown = suite["markdown"]
    case_block = markdown.split("### case：测试环境 appid 与送审地址申请信息完整性校验", 1)[1]

    precondition_index = case_block.index("- 前置条件：已具备提审邮箱和申请字段说明")
    steps_index = case_block.index("- 步骤描述：")
    priority_index = case_block.index("- 用例等级：P0")

    assert precondition_index < steps_index < priority_index
    assert "  1. 步骤：准备申请邮件内容\n     - 预期结果：邮件中包含产品名称、审核回调地址、下线地址、服务器出口 IP" in markdown
    assert "  2. 步骤：发送至指定邮箱\n     - 预期结果：邮件发送成功" in markdown


def test_build_case_suite_exposes_explicit_module_hierarchy():
    suite = build_case_suite(
        [
            {
                "priority": "P1",
                "module": "账号/登录",
                "title": "登录成功",
                "steps": [
                    {"action": "输入正确账号", "expected": "账号输入成功"},
                ],
            },
            {
                "priority": "P2",
                "module": "账号/注册",
                "title": "注册成功",
                "steps": [
                    {"action": "提交注册表单", "expected": "注册成功"},
                ],
            },
            {
                "priority": "P0",
                "module": "支付",
                "title": "支付成功",
                "steps": [
                    {"action": "提交订单", "expected": "订单提交成功"},
                ],
            },
        ],
        summary="输出显式模块层级。",
    )

    module_map = {module["name"]: module for module in suite["modules"]}
    assert "账号" in module_map
    assert "支付" in module_map

    account_children = {module["name"]: module for module in module_map["账号"]["children"]}
    assert set(account_children.keys()) == {"登录", "注册"}
    assert account_children["登录"]["path"] == "账号/登录"
    assert account_children["登录"]["cases"][0]["title"] == "登录成功"
    assert account_children["注册"]["cases"][0]["title"] == "注册成功"
    assert module_map["支付"]["cases"][0]["title"] == "支付成功"


def test_build_case_suite_omits_tags_and_remark_fields_from_items_and_markdown():
    suite = build_case_suite(
        [
            {
                "priority": "P1",
                "module": "登录",
                "title": "登录成功",
                "precondition": "账号可用",
                "tags": "主流程|冒烟",
                "remark": "这条备注不应再出现在输出中",
                "steps": [
                    {"action": "输入正确账号", "expected": "账号输入成功"},
                    {"action": "点击登录", "expected": "进入首页"},
                ],
            }
        ],
        summary="验证输出契约收敛。",
    )

    item = suite["items"][0]
    assert "tags" not in item
    assert "remark" not in item
    assert "- 标签：" not in suite["markdown"]
    assert "- 备注：" not in suite["markdown"]


def test_build_test_case_review_payload_normalizes_findings_and_revised_suite():
    payload = build_test_case_review_payload(
        summary="已评审 2 条测试用例，识别 1 项问题。",
        findings=[
            {
                "risk_level": "high",
                "category": "需求偏离",
                "related_case_ids": ["case-login-2"],
                "related_requirement_points": ["连续失败 5 次锁定 30 分钟"],
                "description": "未覆盖锁定恢复规则。",
                "suggestion": "补充锁定中登录与锁定恢复场景。",
            }
        ],
        reviewed_cases=[
            {
                "case_id": "case-login-1",
                "title": "账号密码登录成功",
                "module": "登录",
                "verdict": "pass",
                "consistency": "aligned",
                "issues": [],
                "suggestions": [],
            }
        ],
        revised_suite=[
            {
                "id": "case-login-1",
                "priority": "P1",
                "module": "登录",
                "title": "账号密码登录成功",
                "steps": [
                    {"action": "输入正确账号密码", "expected": "账号密码输入成功"},
                    {"action": "点击登录", "expected": "进入首页"},
                ],
            },
            {
                "id": "case-login-2",
                "priority": "P0",
                "module": "登录",
                "title": "连续失败 5 次后锁定账号",
                "steps": [
                    {"action": "连续 5 次输入错误密码", "expected": "第 5 次失败后账号进入锁定状态"},
                ],
            },
        ],
    )

    assert payload["findings"][0]["risk_level"] == "H"
    assert payload["reviewed_cases"][0]["case_id"] == "case-login-1"
    assert payload["revised_suite"]["items"][0]["priority"] == "P0"
    assert payload["revised_suite"]["markdown"].startswith("# 智能测试用例")
    assert payload["markdown"].startswith("# 测试用例评审报告")
    assert "连续失败 5 次后锁定账号" in payload["markdown"]


def test_build_requirement_analysis_pack_generates_markdown_sections():
    payload = build_requirement_analysis_pack(
        [
            {
                "module": "发布页",
                "summary": "负责图文和视频发布。",
                "actors": ["用户", "运营"],
                "business_rules": ["图片最多 9 张", "视频最多 1 个"],
                "data_entities": ["帖子", "话题"],
                "exceptions": ["上传失败需提示重试"],
                "open_questions": ["话题上限口径待确认"],
            }
        ],
        summary="完成结构化需求分析。",
    )

    assert payload["summary"] == "完成结构化需求分析。"
    assert payload["items"][0]["actors"] == ["用户", "运营"]
    assert payload["markdown"].startswith("# 智能需求分析")
    assert "## 发布页" in payload["markdown"]
    assert "### 业务规则" in payload["markdown"]
    assert "- 图片最多 9 张" in payload["markdown"]


def test_build_flowchart_pack_generates_mermaid_markdown():
    payload = build_flowchart_pack(
        [
            {
                "module": "发布页",
                "title": "图文发布主流程",
                "summary": "描述用户完成图文发布的核心链路。",
                "mermaid": "flowchart TD\nA[进入发布页] --> B[输入内容]\nB --> C[提交发布]",
                "warnings": ["话题选择上限待确认"],
            }
        ],
        summary="生成业务流程图。",
    )

    assert payload["summary"] == "生成业务流程图。"
    assert payload["items"][0]["module"] == "发布页"
    assert "```mermaid" in payload["markdown"]
    assert "flowchart TD" in payload["markdown"]
    assert "话题选择上限待确认" in payload["markdown"]


def test_sanitize_mermaid_code_extracts_flowchart_from_json_like_text():
    raw_text = r'''{
  "module": "埋点数据对接",
  "title": "埋点数据对接",
  "summary": "联合产品事件设计",
  "mermaid": "flowchart TD\nA[开始] --> B[设计事件]\nB --> C[完成上报]",
  "warnings": ["字段待确认"]
}'''

    mermaid = sanitize_mermaid_code(raw_text)

    assert mermaid == "flowchart TD\nA[开始] --> B[设计事件]\nB --> C[完成上报]"


def test_sanitize_mermaid_code_extracts_flowchart_from_pseudo_json_with_unescaped_quotes():
    raw_text = '''{
  "module": "埋点数据对接",
  "title": "埋点数据对接",
  "summary": "联合产品事件设计",
  "mermaid": "flowchart TD\\nStart[\\"开始\\"] --> DocEvent["事件设计表(xlsx)"]\\nDocEvent --> End[\\"完成\\"]",
  "warnings": ["字段待确认"]
}'''

    mermaid = sanitize_mermaid_code(raw_text)

    assert mermaid == 'flowchart TD\nStart["开始"] --> DocEvent["事件设计表(xlsx)"]\nDocEvent --> End["完成"]'


def test_sanitize_mermaid_code_extracts_flowchart_from_pseudo_json_wrapped_by_code_block():
    raw_text = '''```mermaid
{
  "module": "埋点数据对接",
  "title": "埋点数据对接",
  "summary": "联合产品事件设计",
  "mermaid": "flowchart TD\\nStart[\\"开始\\"] --> DocEvent["事件设计表(xlsx)"]\\nDocEvent --> End[\\"完成\\"]",
  "warnings": ["字段待确认"]
}
```'''

    mermaid = sanitize_mermaid_code(raw_text)

    assert mermaid == 'flowchart TD\nStart["开始"] --> DocEvent["事件设计表(xlsx)"]\nDocEvent --> End["完成"]'


def test_sanitize_mermaid_code_repairs_mismatched_label_closers():
    raw_text = """flowchart TD
Start("进入课程库列表"):::start --> User("运营/内容管理员"):::role
User --> ViewList["查看内容条目"):::process
ViewList --> GetStatus["读取审核状态"):::process
GetStatus --> DecideStatus{"当前审核状态?"}:::decision
"""

    mermaid = sanitize_mermaid_code(raw_text)

    assert 'ViewList["查看内容条目"]:::process' in mermaid
    assert 'GetStatus["读取审核状态"]:::process' in mermaid


def test_normalize_flowchart_item_adds_warning_when_mermaid_was_auto_repaired():
    item = normalize_flowchart_item({
        "module": "课程库",
        "title": "审核快捷操作",
        "mermaid": """flowchart TD
Start("进入课程库列表"):::start --> User("运营/内容管理员"):::role
User --> ViewList["查看内容条目"):::process
""",
        "warnings": [],
    })

    assert item["mermaid"] == """flowchart TD
Start("进入课程库列表"):::start --> User("运营/内容管理员"):::role
User --> ViewList["查看内容条目"]:::process"""
    assert "Mermaid 语法已自动修复" in item["warnings"][0]


def test_build_test_data_pack_generates_fixed_markdown_hierarchy():
    payload = build_test_data_pack(
        raw_tables=[
            {
                "name": "xqd_platform_goods",
                "display_name": "直播商品表",
                "columns": [
                    {
                        "name": "id",
                        "sql_type": "bigint",
                        "description": "主键",
                        "primary_key": True,
                        "required": False,
                    },
                    {
                        "name": "goods_name",
                        "sql_type": "varchar(128)",
                        "description": "商品名称",
                        "primary_key": False,
                        "required": True,
                    },
                ],
                "select_sql": "SELECT `id`, `goods_name` FROM `xqd_platform_goods` LIMIT 20;",
                "insert_sql": "INSERT INTO `xqd_platform_goods` (`goods_name`) VALUES ('示例名称');",
                "update_sql": "UPDATE `xqd_platform_goods` SET `goods_name` = '示例名称' WHERE `id` = 10001;",
                "delete_sql": "DELETE FROM `xqd_platform_goods` WHERE `id` = 10001;",
            }
        ],
        raw_scenarios=[
            {
                "name": "查询与插入直播商品",
                "tables": ["xqd_platform_goods"],
                "select_sql": "SELECT `id`, `goods_name` FROM `xqd_platform_goods` LIMIT 20;",
                "insert_sql": "INSERT INTO `xqd_platform_goods` (`goods_name`) VALUES ('示例名称');",
                "update_sql": "UPDATE `xqd_platform_goods` SET `goods_name` = '示例名称' WHERE `id` = 10001;",
                "delete_sql": "DELETE FROM `xqd_platform_goods` WHERE `id` = 10001;",
            }
        ],
        summary="已生成测试数据 SQL。",
        warnings=["字段默认值依赖人工确认"],
        document_name="直播提效.doc",
    )

    markdown = payload["markdown"]

    assert markdown.startswith("# 识别摘要")
    assert "## 表清单" in markdown
    assert "## 场景清单" in markdown
    assert "# 按表 SQL" in markdown
    assert "## 直播商品表 (`xqd_platform_goods`)" in markdown
    assert "### 字段摘要" in markdown
    assert "### SELECT" in markdown
    assert "### INSERT" in markdown
    assert "### UPDATE" in markdown
    assert "### DELETE" in markdown
    assert "# 按场景 SQL" in markdown
    assert "## 查询与插入直播商品" in markdown
    assert "### 依赖表" in markdown
    assert "# 识别告警" in markdown
    assert "UPDATE `xqd_platform_goods`" in markdown
    assert "DELETE FROM `xqd_platform_goods`" in markdown
    assert payload["sql_file_content"].startswith("-- 识别摘要")


def test_build_api_test_pack_generates_markdown_sections():
    payload = build_api_test_pack(
        spec={
            "title": "默认模块",
            "version": "1.0.0",
            "openapi_version": "3.0.1",
            "servers": [{"url": "https://edu-admin.dev1.dachensky.com", "description": "测试环境dev1"}],
            "auth_profile": {
                "required_headers": ["Authorization", "Authorization-User"],
                "required_cookies": ["cookie", "userId"],
            },
            "resources": [
                {
                    "resource_key": "platformGoods",
                    "tag": "平台带货管理",
                    "lookup_fields": ["title", "businessId", "jumpUrl"],
                    "operation_ids": [
                        "POST /admin/platformGoods/adminList",
                        "POST /admin/platformGoods/add",
                    ],
                }
            ],
            "operations": [
                {
                    "operation_id": "POST /admin/platformGoods/adminList",
                    "summary": "adminList",
                    "category": "list",
                    "resource_key": "platformGoods",
                },
                {
                    "operation_id": "POST /admin/platformGoods/add",
                    "summary": "add",
                    "category": "create",
                    "resource_key": "platformGoods",
                },
            ],
        },
        raw_cases=[
            {
                "case_id": "platformGoods_add_success",
                "title": "新增平台带货成功",
                "operation_id": "POST /admin/platformGoods/add",
                "category": "create",
                "priority": "P1",
                "depends_on": [],
            },
            {
                "case_id": "platformGoods_lookup_after_add",
                "title": "新增后回查平台带货记录",
                "operation_id": "POST /admin/platformGoods/adminList",
                "category": "list",
                "priority": "P1",
                "depends_on": ["platformGoods_add_success"],
            },
        ],
        raw_scenes=[
            {
                "scene_id": "platformGoods_crud_flow",
                "title": "平台带货管理 CRUD 主链路",
                "steps": [
                    "platformGoods_add_success",
                    "platformGoods_lookup_after_add",
                ],
            }
        ],
        script="import pytest\n\ndef test_demo():\n    assert True\n",
        summary="已识别 2 个接口，生成 2 条结构化用例和 1 个关联场景。",
    )

    assert payload["summary"] == "已识别 2 个接口，生成 2 条结构化用例和 1 个关联场景。"
    assert payload["spec"]["title"] == "默认模块"
    assert payload["cases"][0]["case_id"] == "platformGoods_add_success"
    assert payload["scenes"][0]["scene_id"] == "platformGoods_crud_flow"
    assert payload["markdown"].startswith("# 接口测试资产")
    assert "## 规范概览" in payload["markdown"]
    assert "## 鉴权信息" in payload["markdown"]
    assert "## 资源分组" in payload["markdown"]
    assert "## 用例清单" in payload["markdown"]
    assert "## 关联场景" in payload["markdown"]
    assert "## 生成脚本" in payload["markdown"]
    assert "```python" in payload["markdown"]


def test_build_api_test_pack_appends_execution_summary_when_present():
    payload = build_api_test_pack(
        spec={
            "title": "默认模块",
            "servers": [{"url": "https://edu-admin.dev1.dachensky.com"}],
            "auth_profile": {"required_headers": [], "required_cookies": []},
            "resources": [],
            "operations": [],
        },
        raw_cases=[],
        raw_scenes=[],
        script="import pytest\n",
        summary="已生成接口测试资产。",
        execution={
            "status": "passed",
            "summary": "执行 3 条 pytest 用例，全部通过。",
            "stats": {
                "total": 3,
                "passed": 3,
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

    assert payload["execution"]["status"] == "passed"
    assert "## 执行结果" in payload["markdown"]
    assert "执行 3 条 pytest 用例，全部通过。" in payload["markdown"]
    assert "junit.xml" in payload["markdown"]


def test_build_api_test_pack_keeps_execution_report_content():
    payload = build_api_test_pack(
        spec={
            "title": "默认模块",
            "servers": [],
            "auth_profile": {"required_headers": [], "required_cookies": []},
            "resources": [],
            "operations": [],
        },
        raw_cases=[],
        raw_scenes=[],
        execution={
            "status": "passed",
            "summary": "执行通过。",
            "junit_xml_content": "<?xml version=\"1.0\" encoding=\"utf-8\"?><testsuites />",
            "execution_summary_content": "{\n  \"status\": \"passed\"\n}",
            "runtime_config_content": "{\n  \"base_url\": \"https://example.com\"\n}",
            "asset_snapshot_content": "{\n  \"title\": \"默认模块\"\n}",
            "case_snapshot_content": "[\n  {\n    \"case_id\": \"platformGoods_add_success\"\n  }\n]",
            "scene_snapshot_content": "[\n  {\n    \"scene_id\": \"platformGoods_crud_flow\"\n  }\n]",
            "artifacts": {},
        },
    )

    assert payload["execution"]["junit_xml_content"].startswith("<?xml")
    assert '"status": "passed"' in payload["execution"]["execution_summary_content"]
    assert '"base_url": "https://example.com"' in payload["execution"]["runtime_config_content"]
    assert '"title": "默认模块"' in payload["execution"]["asset_snapshot_content"]
    assert '"case_id": "platformGoods_add_success"' in payload["execution"]["case_snapshot_content"]
    assert '"scene_id": "platformGoods_crud_flow"' in payload["execution"]["scene_snapshot_content"]


def test_build_api_test_pack_includes_link_plan_suite_and_report_sections():
    payload = build_api_test_pack(
        spec={
            "title": "默认模块",
            "servers": [{"url": "https://example.com"}],
            "auth_profile": {"required_headers": [], "required_cookies": []},
            "resources": [],
            "operations": [{"operation_id": "POST /admin/platformGoods/add", "category": "create"}],
        },
        raw_cases=[
            {
                "case_id": "platformGoods_add_success",
                "title": "新增平台带货成功",
                "operation_id": "POST /admin/platformGoods/add",
                "category": "create",
                "priority": "P1",
                "depends_on": [],
                "extract": [{"name": "resource_id", "pick": "response.data.id"}],
            }
        ],
        raw_scenes=[],
        link_plan={
            "ordered_case_ids": ["platformGoods_add_success"],
            "standalone_case_ids": ["platformGoods_add_success"],
            "scene_orders": [],
            "case_dependencies": {"platformGoods_add_success": []},
            "extract_variables": {"resource_id": ["platformGoods_add_success"]},
            "warnings": [],
        },
        suite={
            "suite_id": "api_suite_default",
            "suite_version": 2,
            "title": "默认模块",
            "case_count": 1,
            "scene_count": 0,
            "storage_path": "/tmp/api_suites/api_suite_default/v002.json",
        },
        report={
            "status": "passed",
            "headline": "默认模块：执行通过",
            "summary_lines": ["总 1 / 通过 1 / 失败 0 / 异常 0 / 跳过 0"],
            "failure_cases": [],
            "artifact_labels": [{"key": "run_dir", "label": "运行目录", "value": "/tmp/api_runs/run-001"}],
        },
    )

    assert payload["link_plan"]["ordered_case_ids"] == ["platformGoods_add_success"]
    assert payload["suite"]["suite_version"] == 2
    assert payload["report"]["headline"] == "默认模块：执行通过"
    assert "## 关联编排" in payload["markdown"]
    assert "## 套件沉淀" in payload["markdown"]
    assert "## 执行报告" in payload["markdown"]
