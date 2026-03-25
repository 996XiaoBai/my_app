import os
import requests
from dotenv import load_dotenv

load_dotenv()

def run():
    auth_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    auth_res = requests.post(auth_url, json={"app_id": os.getenv("FEISHU_APP_ID"), "app_secret": os.getenv("FEISHU_APP_SECRET")})
    tenant_access_token = auth_res.json().get("tenant_access_token")

    # 1. Create a doc
    url_create = "https://open.feishu.cn/open-apis/docx/v1/documents"
    headers = {
        "Authorization": f"Bearer {tenant_access_token}",
        "Content-Type": "application/json"
    }
    create_payload = {"title": "Brute Force Test"}
    res_create = requests.post(url_create, headers=headers, json=create_payload)
    doc_id = res_create.json().get("data", {}).get("document", {}).get("document_id")
    print("Doc created:", doc_id)

    # 2. Upload image
    img_resp = requests.get("https://www.baidu.com/img/flexible/logo/pc/result.png")
    upload_url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
    files = {
        "file": ("image.png", img_resp.content, "image/png")
    }
    data = {"file_name": "image.png", "parent_type": "docx_image", "size": len(img_resp.content), "parent_node": doc_id}
    upload_res = requests.post(upload_url, headers={"Authorization": f"Bearer {tenant_access_token}"}, files=files, data=data)
    file_token = upload_res.json().get("data", {}).get("file_token")
    print("File uploaded, token:", file_token)

    if not file_token:
        print("Upload failed:", upload_res.json())
        return

    # 3. Brute force payload
    candidates = [
        {"token": file_token},
        {"image_key": file_token},
        {"file_token": file_token},
        {"token": file_token, "width": 202, "height": 66},
        {"token": file_token, "width": 202, "height": 66, "align": 1},
        {"file_token": file_token, "width": 202, "height": 66},
        {"key": file_token},
        {"id": file_token}
    ]

    url_blocks = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"

    for cand in candidates:
        payload = {
            "children": [
                {
                    "block_type": 27,
                    "image": cand
                }
            ],
            "index": -1
        }
        res = requests.post(url_blocks, headers=headers, json=payload, params={"document_revision_id": -1})
        resp_json = res.json()
        print(f"Cand: {cand} => Code: {resp_json.get('code')} msg: {resp_json.get('msg')}")
        if resp_json.get('code') == 0:
            print("SUCCESS!!!!")
            break

if __name__ == '__main__':
    run()
