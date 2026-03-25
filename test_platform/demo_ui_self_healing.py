import os
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AISelfHealingEngine:
    """模拟 AI UI 自愈引擎的核心逻辑"""
    
    def __init__(self):
        self.selectors_db = {
            "login_button": "button#login-btn"  # 原始选择器
        }
        
    def get_element(self, page_mock, element_key):
        """尝试获取元素，如果失效则触发 AI 自愈"""
        original_selector = self.selectors_db.get(element_key)
        
        logger.info(f"🔍 尝试定位元素 [{element_key}] 使用选择器: {original_selector}")
        
        # 模拟定位失败
        if page_mock["dom_changed"]:
            logger.warning(f"❌ 定位失败！选择器 {original_selector} 已失效。")
            return self._trigger_ai_healing(page_mock, element_key)
        
        return original_selector

    def _trigger_ai_healing(self, page_mock, element_key):
        """触发 AI 重新定位"""
        logger.info(f"🤖 启动 AI 自愈 Agent，正在分析当前页面结构...")
        
        # 1. 提取当前页面的语义特征（模拟从 DOM 中提取）
        current_dom_snapshot = page_mock["current_dom"]
        semantic_target = "提交登录表单的按钮"
        
        logger.info(f"📝 向 LLM 发送请求：在以下 DOM 中寻找 '{semantic_target}'\nDOM 内容: {current_dom_snapshot}")
        
        # 2. 模拟 LLM 返回新的选择器
        # 在实际系统中，这会调用 Dify/OpenAI 并传入文本/截图
        new_selector = "button.v2-auth-submit-primary" 
        
        logger.info(f"✅ AI 成功定位！新选择器建议: {new_selector}")
        logger.info(f"⚙️ 自动更新本地 PO 缓存并执行操作...")
        
        # 更新缓存
        self.selectors_db[element_key] = new_selector
        return new_selector

def run_demo():
    # 模拟页面状态
    page_state = {
        "dom_changed": True,
        "current_dom": """
        <html>
            <div>
                <input type='text' placeholder='用户名'>
                <button class='v2-auth-submit-primary'>登录系统</button> 
            </div>
        </html>
        """
    }
    
    engine = AISelfHealingEngine()
    
    print("\n" + "="*60)
    print("🚀 兴趣岛 UI 自动化自愈演示 (Self-healing Demo)")
    print("="*60 + "\n")
    
    target_selector = engine.get_element(page_state, "login_button")
    
    print(f"\n🎯 最终执行使用的选择器: {target_selector}")
    print("\n✅ 演示完成：系统已通过语义分析成功通过 AI 找回了变更后的元素。")

if __name__ == "__main__":
    run_demo()
