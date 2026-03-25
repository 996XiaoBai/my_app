import requests
import json
import time

API_URL = "http://127.0.0.1:8000/run"
REQUIREMENT_TEXT = "用户登录功能：输入框包含手机号和验证码。点击获取验证码会收到短信。如果不合法则报错。"

MODES_TO_TEST = [
    "review",
    "req_analysis",
    "test_plan",
    "api_test_gen",
    "test_point",
    "flowchart"
]

ROLES = ["Senior QA Expert"]

def run_test():
    success_count = 0
    fail_count = 0
    
    for mode in MODES_TO_TEST:
        print(f"\\n[{'='*10} Testing Mode: {mode} {'='*10}]")
        data = {
            "mode": mode,
            "requirement": REQUIREMENT_TEXT,
            "extra_prompt": "",
            "roles": json.dumps(ROLES)
        }
        
        try:
            start_time = time.time()
            response = requests.post(API_URL, data=data, timeout=60)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("success"):
                    print(f"✅ SUCCESS: {mode} (Time: {elapsed:.2f}s)")
                    # 打印前 100 个字符预览
                    result_text = str(res_json.get("result", ""))
                    print(f"   Preview: {result_text[:100]}...")
                    success_count += 1
                else:
                    print(f"❌ FAILED (API Success=False): {mode}")
                    print(f"   Error: {res_json.get('error')}")
                    fail_count += 1
            else:
                print(f"❌ FAILED (HTTP {response.status_code}): {mode}")
                fail_count += 1
        except Exception as e:
            print(f"❌ ERROR connecting to {mode}: {e}")
            fail_count += 1
            
    print(f"\\n[{'='*10} Test Summary {'='*10}]")
    print(f"Total: {len(MODES_TO_TEST)}, Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    run_test()
