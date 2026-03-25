import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

def run():
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    folder_token = os.getenv("FEISHU_FOLDER_TOKEN") # 应该是 wik...
    
    # 1. Auth
    auth_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    auth_res = requests.post(auth_url, json={"app_id": app_id, "app_secret": app_secret})
    token = auth_res.json().get("tenant_access_token")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 2. Create wiki node
    space_id = folder_token  # Assuming folder_token is actually a workspace ID or something. Wait, no.
    # We should look at FeishuPublisher to see how it creates wiki nodes.
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from ai_news_bot.feishu_publisher import FeishuPublisher

    pub = FeishuPublisher(app_id, app_secret, folder_token)
    doc_info = pub.create_document("Wiki Image Test")
    doc_id = doc_info["document_id"]
    is_wiki = doc_info["is_wiki"]
    print(f"Doc created: ID={doc_id}, IsWiki={is_wiki}")

    # 3. Download a standard image
    img_url = "https://www.baidu.com/img/flexible/logo/pc/result.png"
    img_resp = requests.get(img_url)
    
    # 4. Upload with different parent_type and parent_node configurations to see what works
    configs = [
        {"desc": "standard docx_image + obj_token", "p_type": "docx_image", "p_node": doc_id},
        {"desc": "standard doc_image + obj_token", "p_type": "doc_image", "p_node": doc_id},
    ]
    
    blocks = []
    
    for conf in configs:
        url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        upload_headers = {"Authorization": f"Bearer {token}"}
        content_type = img_resp.headers.get('Content-Type', 'image/png')
        file_name_val = "test.png"
        
        data = {
            "file_name": file_name_val,
            "parent_type": conf["p_type"],
            "size": len(img_resp.content),
            "parent_node": conf["p_node"]
        }
        files = {
            "file": (file_name_val, img_resp.content, content_type)
        }
        res = requests.post(url, headers=upload_headers, data=data, files=files)
        res_data = res.json()
        
        if res_data.get("code") == 0:
            file_token = res_data.get("data", {}).get("file_token")
            print(f"[{conf['desc']}] Upload success, token: {file_token}")
            blocks.append({
                "block_type": 2,
                "text": {"elements": [{"text_run": {"content": conf['desc']}}]}
            })
            blocks.append({
                "block_type": 27,
                "image": {"image_key": file_token}
            })
        else:
            print(f"[{conf['desc']}] Upload failed: {res_data}")
            
    # 5. insert blocks
    from ai_news_bot.feishu_publisher import FeishuBlockBuilder
    success = pub.write_blocks(doc_id, blocks)
    url = pub.get_document_url(doc_id, is_wiki)
    print(f"Blocks written? {success}, check document: {url}")

if __name__ == '__main__':
    run()
