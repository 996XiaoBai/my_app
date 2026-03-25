import argparse
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from test_platform.core.agents.requirement_review_agent import RequirementReviewAgent
from test_platform.infrastructure.tapd_client import TAPDClient

def main():
    parser = argparse.ArgumentParser(description="Requirement Review Agent Demo")
    parser.add_argument("--file", help="Path to requirement file (PDF or Text)", required=False)
    parser.add_argument("--story_id", help="TAPD Story ID to fetch requirement from", required=False)
    parser.add_argument("--mode", help="Review Mode: 'single' (Default) or 'round_table' (Multi-Persona)", default="single", choices=["single", "round_table"])
    parser.add_argument("--pages", help="Max pages to read from PDF (Default: 10, Set 0 for all)", type=int, default=10)
    args = parser.parse_args()

    # Initialize Agent
    agent = RequirementReviewAgent()
    
    # Context
    req_context = ""
    
    # 1. Try fetching from TAPD
    if args.story_id:
        story_id = TAPDClient.parse_story_id(args.story_id)
        print(f"🌍 Fetching Story #{story_id} from TAPD...")
        tapd_req = agent.fetch_requirement_from_tapd(story_id)
        if tapd_req:
            req_context = tapd_req
            print("✅ Successfully fetched requirement from TAPD.")
        else:
            print("❌ Failed to fetch from TAPD. Please check ID and permissions.")
            return

    # 2. Try reading local file
    elif not args.file and not req_context:
         # Default Sample if no file and no story_id
        req_context = """
    【需求标题】用户活动报名功能
    【需求描述】
    1. 用户在活动详情页点击“立即报名”按钮。
    2. 如果用户未登录，跳转并在登录成功后返回当前页。
    3. 只有状态为“报名中”的活动可以报名。
    4. 报名成功后扣除用户积分 50 分，并发送短信通知。
    5. 每个用户对同一活动只能报名一次。
    """

    # Run Review
    print(f"🚀 Starting Review Agent (Mode: {args.mode})...")
    
    try:
        if args.file:
            # File mode (PDF usage)
            result = agent.run_review(file_path=args.file, requirement=req_context, mode=args.mode, max_pages=args.pages)
        else:
            # Text/TAPD mode
             result = agent.run_review(file_path=None, requirement=req_context, mode=args.mode)
        
        if result:
            print("\n" + "="*50)
            print("📝 Review Report:")
            print("="*50 + "\n")
            print(result)
            
            # Save output
            output_file = "requirement_review_output.md"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"\n[Result saved to {output_file}]")
        else:
            print("❌ Review failed. Check logs for details.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
