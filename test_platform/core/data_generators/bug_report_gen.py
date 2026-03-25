
import os
import sys
import argparse
from dotenv import load_dotenv

# 确保项目根目录已加入导入路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from test_platform.ai_news_bot.dify_client import DifyClient
from test_platform.config import (
    get_test_platform_dify_api_base,
    get_test_platform_dify_api_key,
    get_test_platform_dify_user_id,
)

def generate_bug_report(user_input):
    load_dotenv()
    
    api_base = get_test_platform_dify_api_base()
    api_key = get_test_platform_dify_api_key()
    user_id = get_test_platform_dify_user_id("bug_reporter")
    
    if not api_base or not api_key:
        print("Error: DIFY_API_BASE or TEST_PLATFORM_DIFY_API_KEY/DIFY_API_KEY not found in .env")
        return

    client = DifyClient(api_base, api_key, user_id)
    
    prompt = f"""
你是一个专业的 QA 测试工程师，负责整理 TV 端 App 的 Bug 报告。
请根据用户提供的非结构化描述，将其转换为标准的 Markdown Bug 报告格式。

**用户描述**:
{user_input}

**输出要求**:
1.  **Strict Markdown Format**: 不要包含其他无关的对话内容，直接输出 Markdown 内容。
2.  **Fields**:
    *   **标题 (Title)**: [模块][设备] 简短描述问题核心
    *   **前置条件 (Pre-condition)**: 推断可能的网络或账号状态 (如未知则写"待确认")
    *   **测试环境 (Environment)**:
        *   设备型号: (从描述中提取，"海信电视"，若无则标记 "需补充")
        *   系统版本: (若无则标记 "需补充")
        *   App 版本: (标记 "待确认")
    *   **复现步骤 (Steps to Reproduce)**: 将描述拆解为 1. 2. 3. 步骤，包含遥控器按键操作 (如 "按【OK】键", "按【返回】键")
    *   **预期结果 (Expected Result)**: 根据常识推断
    *   **实际结果 (Actual Result)**: 描述中的异常现象
    *   **优先级 (Priority)**: High/Medium/Low (根据严重程度判断)

**示例输出**:
# [播放器][小米电视] 视频播放中按返回键无法退出

**前置条件**: 
登录状态，播放任意视频

**测试环境**:
*   设备型号: Xiaomi TV 5
*   系统版本: Android 9
*   App 版本: 待确认

**复现步骤**:
1.  进入视频详情页，点击【播放】。
2.  在视频播放过程中，按遥控器【返回】键。

**预期结果**:
退出全屏播放，返回详情页。

**实际结果**:
无响应，视频继续播放。

**优先级**: High
"""
    
    print("Generating Bug Report... Please wait.")
    report = client.generate_completion(prompt)
    
    if report:
        print("\n" + "="*20 + " GENERATED BUG REPORT " + "="*20 + "\n")
        print(report)
        print("\n" + "="*60 + "\n")
    else:
        print("Failed to generate report.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate TV Bug Report from description")
    parser.add_argument("description", nargs="?", help="Bug description in quotes")
    args = parser.parse_args()
    
    if args.description:
        desc = args.description
    else:
        print("请输入 Bug 描述 (按 Ctrl+D 结束):")
        desc = sys.stdin.read()
        
    if desc.strip():
        generate_bug_report(desc)
    else:
        print("Empty description.")
