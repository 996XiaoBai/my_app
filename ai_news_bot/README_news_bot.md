# 飞书与企业微信资讯机器人 部署与排查手册

这是用于在云端和本地环境运行“AI 资讯聚合推送机器人”的简易操作说明。

### 获取最新修复
当发现企微不推送、或者时区不触发时，可以通过如下命令更新到修复后的分支并重启：
```bash
git checkout main
git pull origin main

# 杀掉僵死进程
ps aux | grep "[r]un_scheduler.py" | awk '{print $2}' | xargs kill -9

# 回到正确工作目录，拉起后台日志记录
cd ai_news_bot
nohup bash run_local.sh >> bot_scheduler.log 2>&1 &
```

### 本地解释器约定

当前脚本不再硬编码 `Python 3.13`，而是统一通过 `ai_news_bot/scripts/resolve_python.sh` 解析满足 `Python 3.10+` 的解释器。

推荐做法：

```bash
cd ai_news_bot
bash scripts/setup_venv.sh
source .venv/bin/activate
```

`bash scripts/setup_venv.sh` 会自动解析满足 `Python 3.10+` 的解释器，创建 `ai_news_bot/.venv`，并安装 `requirements.txt` 里的依赖。

如果你不想手动激活，`run_local.sh` 会先自动执行 `bash scripts/setup_venv.sh`，再使用 `ai_news_bot/.venv/bin/python` 启动调度器；`run_bot_cron.sh` 则会优先使用现成的 `ai_news_bot/.venv`，找不到时再回退到共享解析器候选。

### 强制重发/手动排错
如果你希望在任何时候发一次**包含今天最新资讯**的推送，但程序判定“这是旧闻”拒绝推送，执行以下清空命令强制重查：
```bash
# 进入目录
cd ai_news_bot
# 备份去重记录（不要直接删！）
mv data/sent_articles.json data/sent_articles.json.bak

# 初始化或复用 ai_news_bot/.venv，再立即运行全部步骤
PYTHON_BIN="$(bash scripts/setup_venv.sh "$(pwd)")"
"$PYTHON_BIN" run_scheduler.py --now

# **这步非常重要**：跑完后恢复之前的记录，否则明天它会将以前的老新闻当成新新闻重新推送！
mv data/sent_articles.json.bak data/sent_articles.json
```

现在 `"$PYTHON_BIN" run_scheduler.py --now` 会立即执行一次 QA 日报和 AI 日报，然后直接退出，不再继续常驻。

### 环境变量说明
* `WECOM_WEBHOOK_URL`：通用企业微信机器人地址，AI 日报默认使用它。
* `WECOM_QA_BOT_WEBHOOK_URL`：QA/测试资讯专属企业微信机器人地址，若未配置则降级使用 `WECOM_WEBHOOK_URL`。

### 补发状态文件
* `ai_news_bot/data/publish_records.json`：AI 日报渠道状态记录，企微发送失败会进入待补发队列。
* `ai_news_bot/data/qa_publish_records.json`：QA 日报渠道状态记录。
* 每次新任务开始前，程序会先尝试补发之前失败的企微消息。

### 日常查 Bug 指南
* **查看每天到底抓了哪些新闻（成功与过滤）**：
  `tail -n 200 ai_news_bot/bot_scheduler.log`
* **查看 Webhook 报错**：
  在 `bot_scheduler.log` 里寻找 `Failed to send WeCom notification` 或 `Skipping WeCom notification`，前者代表 URL 错误或企业微信被限频，后者代表服务器下 `.env` 未添加 `WECOM_WEBHOOK_URL` 或 `WECOM_QA_BOT_WEBHOOK_URL` 环境变量配置。
