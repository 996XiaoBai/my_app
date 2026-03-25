import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_FEISHU_RESEARCH_TESTS") != "1",
    reason="研究类飞书图片上传测试默认跳过；如需真实验证请显式设置 RUN_LIVE_FEISHU_RESEARCH_TESTS=1",
)


def test_lark_image_upload_live():
    """保留为显式开启的真实飞书图片上传研究验证脚本。"""
    import io

    import lark_oapi as lark
    import lark_oapi.api.drive.v1 as drive
    import requests
    from dotenv import load_dotenv
    from lark_oapi.api.docx.v1 import Block, CreateDocumentBlockChildrenRequest, CreateDocumentBlockChildrenRequestBody, Image

    load_dotenv()
    client = (
        lark.Client.builder()
        .app_id(os.getenv("FEISHU_APP_ID"))
        .app_secret(os.getenv("FEISHU_APP_SECRET"))
        .log_level(lark.LogLevel.DEBUG)
        .build()
    )

    doc_id = os.getenv("FEISHU_TEST_DOC_ID")
    assert doc_id, "需要通过 FEISHU_TEST_DOC_ID 指定测试文档"

    img_resp = requests.get("https://www.baidu.com/img/flexible/logo/pc/result.png", timeout=10)
    assert img_resp.status_code == 200

    upload_req = drive.UploadAllMediaRequest.builder().request_body(
        drive.UploadAllMediaRequestBody.builder()
        .file_name("test.png")
        .parent_type("docx_image")
        .parent_node(doc_id)
        .size(len(img_resp.content))
        .file(io.BytesIO(img_resp.content))
        .build()
    ).build()
    upload_resp = client.drive.v1.media.upload_all(upload_req)
    assert upload_resp.code == 0

    file_token = upload_resp.data.file_token
    create_req = (
        CreateDocumentBlockChildrenRequest.builder()
        .document_id(doc_id)
        .block_id(doc_id)
        .document_revision_id(-1)
        .request_body(
            CreateDocumentBlockChildrenRequestBody.builder()
            .children([Block.builder().block_type(27).image(Image.builder().token(file_token).build()).build()])
            .build()
        )
        .build()
    )
    create_resp = client.docx.v1.document_block_children.create(create_req)
    assert create_resp.code == 0
