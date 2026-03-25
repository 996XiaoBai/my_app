import requests
import json
import time

def fetch_testerhome():
    print("----- Fetching TesterHome -----")
    # https://testerhome.com/api/v3/topics.json?limit=10&type=excellent
    url = "https://testerhome.com/api/v3/topics.json?limit=15&type=excellent"
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        for topic in data.get('topics', []):
            title = topic.get('title')
            topic_id = topic.get('id')
            link = f"https://testerhome.com/topics/{topic_id}"
            print(f"- [TesterHome] {title}\n  {link}")
    except Exception as e:
        print(f"Error fetching TesterHome: {e}")

def fetch_juejin():
    print("\n----- Fetching Juejin (Testing/QA) -----")
    url = "https://api.juejin.cn/search_api/v1/search"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    payload = {
        "key_word": "接口自动化测试",
        "id_type": 0,
        "cursor": "0",
        "limit": 10,
        "search_type": 0,
        "sort_type": 2 # 2=按最新
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        data = resp.json()
        results = data.get('data', [])
        for item in results:
            result_model = item.get('result_model', {})
            article = result_model.get('article_info', {})
            if not article:
                continue
            title = article.get('title', '')
            article_id = article.get('article_id', '')
            brief = article.get('brief_content', '')
            link = f"https://juejin.cn/post/{article_id}"
            print(f"- [Juejin] {title}\n  {brief[:50]}...\n  {link}")
    except Exception as e:
        print(f"Error fetching Juejin: {e}")

if __name__ == "__main__":
    fetch_testerhome()
    fetch_juejin()
