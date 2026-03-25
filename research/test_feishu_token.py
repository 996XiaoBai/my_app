import os
import sys
from dotenv import load_dotenv

sys.path.append("/Users/linkb/PycharmProjects/my_app")
from ai_news_bot.feishu_publisher import FeishuPublisher

def main():
    load_dotenv("/Users/linkb/PycharmProjects/my_app/.env")
    app_id = os.getenv("FEISHU_APP_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")
    
    if not app_id or not app_secret:
        print("Missing credentials in .env")
        return
        
    print(f"Testing Feishu credentials: App ID={app_id}, Secret={app_secret[:5]}...")
    publisher = FeishuPublisher(app_id, app_secret)
    token = publisher._get_tenant_access_token()
    
    if token:
        print(f"Success! Tenant Access Token: {token[:15]}...")
        doc_info = publisher.create_document("测试文档 - AI News Bot 授权验证")
        if doc_info:
            doc_id = doc_info["document_id"]
            url = publisher.get_document_url(doc_id)
            print(f"Success! Document created at: {url}")
        else:
            print("Failed to create document.")
    else:
        print("Failed to get token!")

if __name__ == "__main__":
    main()
