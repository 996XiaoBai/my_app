import sys

file_path = 'main_news_bot.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 找到原本写在一起的企业微信和公众号逻辑块
target_block = """                # 4. 企业微信转发
                if self.wecom_webhook_url:
                    logger.info("正在发送企业微信通知...")
                    notifier = WeComBotNotifier(self.wecom_webhook_url)
                    notifier.notify_feishu_doc(doc_title, doc_url, news_items)
                    
                # 5. 微信公众号同步 (仅在配置存在时运行) - 目前根据用户排期取消调用
                if self.wechat_app_id and self.wechat_app_secret:
                    logger.info("正在同步至微信公众号草稿箱...")
                    wechat_pub = WeChatOAPublisher(self.wechat_app_id, self.wechat_app_secret)
                    wechat_pub.push_to_draft(doc_title, doc_url, news_items)"""

# 替换为互相独立的 Try-Except 块
new_block = """                # 4. 企业微信转发 (独立运行块)
                if self.wecom_webhook_url:
                    try:
                        logger.info("👉 [任务分支] 开始发送企业微信通知...")
                        notifier = WeComBotNotifier(self.wecom_webhook_url)
                        notifier.notify_feishu_doc(doc_title, doc_url, news_items)
                        logger.info("✅ 企业微信通知发送成功！")
                    except Exception as e:
                        logger.error(f"❌ 企业微信通知发送失败，但不影响其他渠道: {e}")
                    
                # 5. 微信公众号同步 (独立运行块)
                if self.wechat_app_id and self.wechat_app_secret:
                    try:
                        logger.info("👉 [任务分支] 开始同步至微信公众号草稿箱...")
                        wechat_pub = WeChatOAPublisher(self.wechat_app_id, self.wechat_app_secret)
                        wechat_pub.push_to_draft(doc_title, doc_url, news_items)
                        logger.info("✅ 微信公众号草稿写入成功！")
                    except Exception as e:
                        logger.error(f"❌ 微信公众号同步失败(可能是IP白名单拦截)，但不影响其他渠道: {e}")"""

if target_block in content:
    content = content.replace(target_block, new_block)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("代码修改成功！")
else:
    print("未找到需要替换的目标代码块，请确认文件是否已被修改。")
