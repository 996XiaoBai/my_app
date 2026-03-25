import io
import json
import zipfile
from xml.etree import ElementTree as ET

from fastapi.testclient import TestClient

import test_platform.api_server as api_server


def _build_case_suite_payload() -> str:
    return json.dumps(
        {
            "items": [
                {
                    "id": "case-login-1",
                    "priority": "P1",
                    "module": "登录",
                    "title": "登录成功",
                    "precondition": "账号可用",
                    "steps": [
                        {"action": "输入账号", "expected": "账号输入成功"},
                        {"action": "点击登录", "expected": "进入首页"},
                    ],
                }
            ],
            "summary": "覆盖登录主流程",
        },
        ensure_ascii=False,
    )


def test_get_tapd_story_returns_story_content(monkeypatch):
    monkeypatch.setattr(api_server.review_service, "tapd_client", object())
    monkeypatch.setattr(
        api_server.review_service,
        "fetch_requirement_from_tapd",
        lambda story_id: f"【需求标题】登录优化\n【Story ID】{story_id}",
    )

    client = TestClient(api_server.app)
    response = client.get(
        "/api/tapd/story",
        params={"input": "https://www.tapd.cn/20340332/stories/view/1120340332001008677"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["story_id"] == "1120340332001008677"
    assert "登录优化" in payload["content"]


def test_get_tapd_story_returns_503_when_tapd_is_unavailable(monkeypatch):
    monkeypatch.setattr(api_server.review_service, "tapd_client", None)

    client = TestClient(api_server.app)
    response = client.get("/api/tapd/story", params={"input": "1120340332001008677"})

    assert response.status_code == 503
    assert "TAPD" in response.json()["detail"]


def test_export_test_cases_as_excel_returns_xlsx_file():
    client = TestClient(api_server.app)

    response = client.post(
        "/api/test-cases/export",
        json={
            "format": "excel",
            "result": _build_case_suite_payload(),
            "filename": "登录模块",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert 'attachment; filename="test-cases.xlsx"' in response.headers["content-disposition"]
    assert "filename*=UTF-8''%E7%99%BB%E5%BD%95%E6%A8%A1%E5%9D%97_%E6%B5%8B%E8%AF%95%E7%94%A8%E4%BE%8B.xlsx" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "xl/worksheets/sheet1.xml" in archive.namelist()


def test_export_test_cases_as_xmind_returns_workbook_file():
    client = TestClient(api_server.app)

    response = client.post(
        "/api/test-cases/export",
        json={
            "format": "xmind",
            "result": _build_case_suite_payload(),
            "filename": "登录模块",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/octet-stream")
    assert 'attachment; filename="test-cases.xmind"' in response.headers["content-disposition"]
    assert "filename*=UTF-8''%E7%99%BB%E5%BD%95%E6%A8%A1%E5%9D%97_%E6%B5%8B%E8%AF%95%E7%94%A8%E4%BE%8B.xmind" in response.headers["content-disposition"]

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "content.xml" in archive.namelist()
        assert "META-INF/manifest.xml" in archive.namelist()


def test_export_test_cases_exposes_content_disposition_for_cors():
    client = TestClient(api_server.app)

    response = client.post(
        "/api/test-cases/export",
        headers={"Origin": "http://localhost:3000"},
        json={
            "format": "xmind",
            "result": _build_case_suite_payload(),
            "filename": "登录模块",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "Content-Disposition" in response.headers["access-control-expose-headers"]


def test_export_test_cases_uses_uploaded_filename_stem_as_download_basename():
    client = TestClient(api_server.app)

    response = client.post(
        "/api/test-cases/export",
        json={
            "format": "excel",
            "result": _build_case_suite_payload(),
            "filename": "登录需求说明_v2.docx",
        },
    )

    assert response.status_code == 200
    assert (
        "filename*=UTF-8''%E7%99%BB%E5%BD%95%E9%9C%80%E6%B1%82%E8%AF%B4%E6%98%8E_v2_%E6%B5%8B%E8%AF%95%E7%94%A8%E4%BE%8B.xlsx"
        in response.headers["content-disposition"]
    )


def test_export_test_cases_as_xmind_uses_template_order_and_grouping():
    client = TestClient(api_server.app)

    response = client.post(
        "/api/test-cases/export",
        json={
            "format": "xmind",
            "result": json.dumps(
                {
                    "items": [
                        {
                            "id": "case-login-1",
                            "priority": "P0",
                            "module": "内容标识传",
                            "title": "测试环境 appid 与送审地址申请信息完整性校验",
                            "precondition": "已具备提审邮箱和申请字段说明",
                            "steps": [
                                {"action": "准备申请邮件内容", "expected": "邮件中包含产品名称、审核回调地址、下线地址、服务器出口 IP"},
                                {"action": "发送至指定邮箱", "expected": "邮件发送成功"},
                            ],
                        },
                        {
                            "id": "case-login-2",
                            "priority": "P1",
                            "module": "内容标识传",
                            "title": "正式环境 appid 与送审地址申请信息完整性校验",
                            "precondition": "已具备正式环境申请信息",
                            "steps": [
                                {"action": "准备正式环境邮件内容", "expected": "邮件字段完整"},
                            ],
                        },
                    ],
                    "summary": "统一脑图导出结构",
                },
                ensure_ascii=False,
            ),
            "filename": "内容标识传",
        },
    )

    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        content_xml = archive.read("content.xml")

    ns = {"x": "urn:xmind:xmap:xmlns:content:2.0"}
    root = ET.fromstring(content_xml)
    titles = [title.text for title in root.findall(".//x:title", ns)]

    assert titles.count("内容标识传") == 1
    assert "case：测试环境 appid 与送审地址申请信息完整性校验" in titles
    assert "前置条件：已具备提审邮箱和申请字段说明" in titles
    assert "步骤描述" in titles
    assert "用例等级：P0" in titles
    assert "步骤：准备申请邮件内容" in titles
    assert "预期结果：邮件中包含产品名称、审核回调地址、下线地址、服务器出口 IP" in titles

    case_topic = root.find(".//x:topic[x:title='case：测试环境 appid 与送审地址申请信息完整性校验']", ns)
    assert case_topic is not None
    case_child_titles = [
        title.text
        for title in case_topic.findall("./x:children/x:topics/x:topic/x:title", ns)
    ]
    assert case_child_titles == [
        "前置条件：已具备提审邮箱和申请字段说明",
        "步骤描述",
        "用例等级：P0",
    ]

    steps_topic = case_topic.find("./x:children/x:topics/x:topic[x:title='步骤描述']", ns)
    assert steps_topic is not None
    step_titles = [
        title.text
        for title in steps_topic.findall("./x:children/x:topics/x:topic/x:title", ns)
    ]
    assert step_titles == [
        "步骤：准备申请邮件内容",
        "步骤：发送至指定邮箱",
    ]

    first_step_topic = steps_topic.find("./x:children/x:topics/x:topic[x:title='步骤：准备申请邮件内容']", ns)
    assert first_step_topic is not None
    expected_titles = [
        title.text
        for title in first_step_topic.findall("./x:children/x:topics/x:topic/x:title", ns)
    ]
    assert expected_titles == [
        "预期结果：邮件中包含产品名称、审核回调地址、下线地址、服务器出口 IP",
    ]
