import os
import sys
import requests
from dotenv import load_dotenv

sys.path.append('.')
load_dotenv()

import lark_oapi as lark
from lark_oapi.api.drive.v1 import UploadAllMediaRequest, UploadAllMediaRequestBody, ListFileRequest
from lark_oapi.api.docx.v1 import (
    CreateDocumentRequest,
    CreateDocumentRequestBody,
    CreateDocumentBlockChildrenRequest,
    CreateDocumentBlockChildrenRequestBody,
    Block,
    Image,
    ListDocumentBlockRequest
)

def run():
    client = lark.Client.builder() \
        .app_id(os.getenv("FEISHU_APP_ID")) \
        .app_secret(os.getenv("FEISHU_APP_SECRET")) \
        .build()
        
    # Through the search interface, find a recent document, hoping it contains images
    list_req = ListFileRequest.builder() \
        .build()
        
    res = client.drive.v1.file.list(list_req)
    if not res.success():
        print("List files failed", res.code, res.msg)
        return
        
    for item in res.data.files:
        if item.type == 'docx':
            print(f"Found docx: {item.name}, token: {item.token}")
            # Get all blocks inside
            block_req = ListDocumentBlockRequest.builder().document_id(item.token).build()
            block_res = client.docx.v1.document_block.list(block_req)
            if block_res.success():
                for b in block_res.data.items:
                    if b.block_type == 27:
                        print("BINGO!!! Found an image block!")
                        import json
                        def obj_to_dict(obj):
                            if hasattr(obj, '__dict__'):
                                return {k: obj_to_dict(v) for k, v in vars(obj).items() if v is not None}
                            elif isinstance(obj, list):
                                return [obj_to_dict(i) for i in obj]
                            else:
                                return obj
                        print(json.dumps(obj_to_dict(b), indent=2))
                        return
                    
    print("No existing docx with images found.")
        
    doc_req = CreateDocumentRequest.builder() \
        .request_body(CreateDocumentRequestBody.builder().title("OAPI Root Test").build()) \
        .build()
        
    doc_res = client.docx.v1.document.create(doc_req)
    if not doc_res.success():
        print("Create doc fail", doc_res.code, doc_res.msg)
        return
        
    doc_id = doc_res.data.document.document_id
    print("Created Doc in root:", doc_id)

    # 1. 独立插入文本测试（仅做参照）
    from lark_oapi.api.docx.v1 import Text, TextElement, TextRun
    text_block = Block.builder() \
        .block_type(2) \
        .text(Text.builder().elements([
            TextElement.builder().text_run(TextRun.builder().content("This is a simple text").build()).build()
        ]).build()) \
        .build()

    # 2. 获取图片媒体并上传到 Docx 命名空间返回 token
    import requests
    from io import BytesIO
    from lark_oapi.api.drive.v1 import UploadAllMediaRequestBody, UploadAllMediaRequest
    img_resp = requests.get("https://www.baidu.com/img/flexible/logo/pc/result.png")
    f = BytesIO(img_resp.content)
    f.name = "image.png"
    
    upload_reqBody = UploadAllMediaRequestBody.builder() \
        .file_name("image.png") \
        .parent_type("docx_image") \
        .parent_node(doc_id) \
        .size(len(img_resp.content)) \
        .file(f) \
        .build()
        
    upload_req = UploadAllMediaRequest.builder() \
        .request_body(upload_reqBody) \
        .build()
        
    upload_res = client.drive.v1.media.upload_all(upload_req)
    if not upload_res.success():
        print("Upload failed:", upload_res.code, upload_res.msg)
        return
        
    file_token = upload_res.data.file_token
    print("File token:", file_token)
        
    # 写入 Block 
    block = Block.builder() \
        .block_type(27) \
        .image(Image.builder().token(file_token).width(202).height(66).align(1).build()) \
        .build()

    children_req_body = CreateDocumentBlockChildrenRequestBody.builder() \
        .children([text_block, block]) \
        .index(-1) \
        .build()
        
    import json
    def obj_to_dict(obj):
        if hasattr(obj, '__dict__'):
            return {k: obj_to_dict(v) for k, v in vars(obj).items() if v is not None}
        elif isinstance(obj, list):
            return [obj_to_dict(i) for i in obj]
        else:
            return obj
            import json
    payload = {
        "children": [
            {
                "block_type": 2,
                "text": {
                    "elements": [
                        {
                            "text_run": {
                                "content": "Raw HTTP test"
                            }
                        }
                    ]
                }
            },
            {
                "block_type": 27,
                "image": {
                    "token": file_token
                }
            }
        ],
        "index": -1
    }
    
    auth_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    auth_res = requests.post(auth_url, json={"app_id": os.getenv("FEISHU_APP_ID"), "app_secret": os.getenv("FEISHU_APP_SECRET")})
    tenant_access_token = auth_res.json().get("tenant_access_token")
    
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json"
    }
    
    raw_res = requests.post(url, headers=headers, json=payload, params={"document_revision_id": -1})
    print("Raw response:", raw_res.status_code, raw_res.text)
        
    # print("Payload dict:", json.dumps(obj_to_dict(children_req_body), indent=2))
        
    # children_req = CreateDocumentBlockChildrenRequest.builder() \
    #     .document_id(doc_id) \
    #     .block_id(doc_id) \
    #     .request_body(children_req_body) \
    #     .document_revision_id(-1) \
    #     .build()
        
    # res = client.docx.v1.document_block_children.create(children_req)
    # if not res.success():
    #     print("Block create failed:", res.code, res.msg, res.error)
    # else:
    #     print("Block created successfully")

if __name__ == '__main__':
    run()
