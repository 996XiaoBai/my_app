import os
import requests
from dotenv import load_dotenv

load_dotenv()

def fetch_doc_blocks(doc_id):
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
    token = res.json().get("tenant_access_token")
    
    blocks_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks"
    headers = {"Authorization": f"Bearer {token}"}
    
    res = requests.get(blocks_url, headers=headers)
    import json
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))

if __name__ == '__main__':
    # We will use this script to fetch blocks from a doc ID provided.
    import sys
    if len(sys.argv) > 1:
        fetch_doc_blocks(sys.argv[1])
    else:
        print("Please provide a doc ID")
