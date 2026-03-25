import os
import sys
import requests
from dotenv import load_dotenv

sys.path.append('.')
from ai_news_bot.feishu_publisher import FeishuPublisher

load_dotenv()

def run_test():
    pub = FeishuPublisher(os.getenv("FEISHU_APP_ID"), os.getenv("FEISHU_APP_SECRET"), os.getenv("FEISHU_FOLDER_TOKEN"))
    token = pub._get_tenant_access_token()
    
    # Let's search for a document in the folder to read its blocks, or just creating a new doc block with only token.
    # Actually, is it possible to upload using the old multipart request WITHOUT size?
    url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
    headers = {"Authorization": f"Bearer {token}"}
    
    # 找一张简单的网络小图
    img_resp = requests.get("https://www.baidu.com/img/flexible/logo/pc/result.png")
    image_bytes = img_resp.content

    print("Trying alternative parent_type: 'explorer'")
    data = {
        "file_name": "image.png",
        "parent_type": "explorer",
        "size": len(image_bytes),
        "parent_node": "" # empty for explorer sometimes? or folder token?
    }
    files = {
        "file": ("image.png", image_bytes, "image/png")
    }
    res = requests.post(url, headers=headers, data=data, files=files)
    print("Explorer upload:", res.json())
    
    doc = pub.create_document("Image Test Doc 2")
    doc_id = doc["document_id"]
    
    # Try parent_type: doc_image instead of docx_image
    data2 = {
        "file_name": "image.png",
        "parent_type": "docx_image",
        "size": len(image_bytes),
        "parent_node": doc_id
    }
    res2 = requests.post(url, headers=headers, data=data2, files=files)
    print("Docx_image upload:", res2.json())
    file_token = res2.json().get("data", {}).get("file_token")
    
    if file_token:
        # try without index
        block_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children"
        payload = {
            "children": [{"block_type": 27, "image": {"token": file_token}}]
        }
        res3 = requests.post(block_url, headers=headers, json=payload, params={"document_revision_id": "-1"})
        print("Write block 1:", res3.json())
        
        # What if block_type is 27 but we need to supply width and height?
        # Let's try supplying arbitrary width and height? No, standard is just token.

if __name__ == '__main__':
    run_test()
