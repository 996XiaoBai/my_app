import requests
from bs4 import BeautifulSoup

def search_feishu_docs():
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get("https://open.feishu.cn/document/server-docs/docs/drive-v1/media/upload_all", headers=headers)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    text = soup.get_text(separator=' ', strip=True)
    
    # Print the neighborhood
    for term in ["docx_image", "parent_node"]:
        idx = text.find(term)
        if idx != -1:
            print(f"--- MATCH for {term} ---")
            print(text[max(0, idx-500):idx+500])
            print("\n")

if __name__ == "__main__":
    search_feishu_docs()
