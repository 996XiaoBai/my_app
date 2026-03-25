# my_app

这是一个面向测试工作流的本地工具仓库，当前主要包含两类能力：

1. `test_platform`：测试平台，提供 Streamlit UI、FastAPI 接口和 Next.js Web 工作台。
2. `ai_news_bot`：AI / QA 资讯聚合与推送机器人，支持手动运行和定时调度。

这个 README 以“本地快速上手”为目标，优先说明怎么把项目跑起来，再说明目录和模块关系。

## 核心模块

### 1. 测试平台 `test_platform`

适合做需求评审、测试用例生成、流程图生成、测试数据准备、接口测试等能力验证。

- Streamlit 入口：`test_platform/app.py`
- FastAPI 入口：`test_platform/api_server.py`
- Next.js 前端：`test_platform/web`

### 2. AI 资讯机器人 `ai_news_bot`

用于抓取、整理并推送 AI / QA 资讯，可按一次性任务运行，也可以按定时任务运行。

- 一次性运行：`make news`
- 定时调度：`make schedule`
- 详细说明：`ai_news_bot/README_news_bot.md`

## 目录结构

```text
my_app/
├── ai_news_bot/              AI / QA 资讯机器人
├── docs/                     设计文档与补充资料
├── frontend/                 浏览器插件等前端资源
├── scripts/                  辅助脚本
├── services/                 通用服务代码
├── test_platform/            测试平台主代码
│   ├── api/                  FastAPI 路由与运行时
│   ├── core/                 核心业务服务
│   ├── ui/                   Streamlit UI
│   ├── web/                  Next.js Web 工作台
│   └── docs/                 平台相关文档
├── tests/                    Python 测试
├── cli.py                    顶层命令入口
├── start.sh                  启动 FastAPI + Next.js
├── start_web_ui.sh           启动 Streamlit UI
└── docker-compose.yml        Streamlit 容器启动配置
```

## 环境要求

- 操作系统：推荐 `macOS`，`Linux` 也可
- Python：`3.11+`
- Node.js：建议 `20+`
- npm：建议和当前 Node.js 配套

仓库已经固定了 Python 基线：

- 根目录 [.python-version](./.python-version) 为 `3.11`
- [test_platform/scripts/resolve_python.sh](./test_platform/scripts/resolve_python.sh) 会优先寻找 `3.11+` 的解释器

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/996XiaoBai/my_app.git
cd my_app
```

### 2. 准备环境变量

```bash
cp .env.example .env
```

如果你只想先体验测试平台，最少需要把 `.env` 里的 Dify 相关配置补齐；如果你要跑资讯机器人，还需要补企业微信 / 微信公众号相关配置。

## 本地安装

### 1. 安装测试平台 Python 依赖

推荐为测试平台单独创建虚拟环境：

```bash
python3 -m venv test_platform/.venv
source test_platform/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r test_platform/requirements.txt
```

### 2. 安装 Web 前端依赖

```bash
cd test_platform/web
npm install
cd ../..
```

### 3. 安装资讯机器人依赖

`ai_news_bot` 自带独立虚拟环境初始化脚本：

```bash
bash ai_news_bot/scripts/setup_venv.sh
```

这个脚本会自动：

- 选择满足要求的 Python 解释器
- 创建 `ai_news_bot/.venv`
- 安装 [ai_news_bot/requirements.txt](./ai_news_bot/requirements.txt) 里的依赖

## 常用启动方式

### 1. 启动 Streamlit 测试平台

```bash
make ui
```

或者：

```bash
bash start_web_ui.sh
```

默认端口：

- Streamlit：`8501`

如果需要改端口，可以设置环境变量：

```bash
export TEST_PLATFORM_STREAMLIT_PORT=8502
```

### 2. 启动 FastAPI + Next.js 工作台

```bash
./start.sh
```

这个脚本会自动：

1. 启动 FastAPI 服务，端口 `8000`
2. 启动 Next.js 前端，端口 `3000`
3. 自动打开浏览器
4. 在退出前端时回收后端进程

相关访问地址：

- 前端工作台：`http://localhost:3000`
- 后端健康检查：`http://localhost:8000/health`

### 3. 运行 AI 资讯机器人

立即执行一次资讯任务：

```bash
make news
```

启动定时调度：

```bash
make schedule
```

`Makefile` 当前提供的命令如下：

```bash
make help
make news
make ui
make schedule
```

## 环境变量说明

根目录 [.env.example](./.env.example) 已经给出示例。常用变量如下：

### 测试平台

- `TEST_PLATFORM_DIFY_API_KEY`：测试平台调用 Dify 的 Key
- `TEST_PLATFORM_DIFY_USER_ID`：测试平台调用 Dify 的用户标识
- `TEST_PLATFORM_STREAMLIT_PORT`：Streamlit 端口，默认 `8501`

### 通用大模型与 Dify

- `DIFY_API_BASE`：Dify 服务地址
- `DIFY_API_KEY`：通用 Dify Key
- `DIFY_USER_ID`：通用 Dify 用户标识
- `LLM_CONTEXT_WINDOW_TOKENS`：上下文窗口预算
- `LLM_RESERVED_OUTPUT_TOKENS`：保留输出 Token
- `LLM_MAX_PROMPT_INPUT_TOKENS`：输入 Token 上限

### 企业微信 / 微信公众号

- `WECHAT_APP_ID`
- `WECHAT_APP_SECRET`
- `WECOM_WEBHOOK_URL`
- `WECOM_QA_BOT_WEBHOOK_URL`

如果这些变量没配全，最常见的结果是：

- 测试平台请求 Dify 时报鉴权或配置错误
- 资讯机器人抓取成功但无法推送到企业微信

## Docker 启动

根目录 [docker-compose.yml](./docker-compose.yml) 当前用于启动 Streamlit 版本的测试平台：

```bash
docker compose up --build
```

默认映射端口：

- `8501:8501`

当前会挂载以下目录：

- `./history`
- `./logs`
- `./.env`

注意：

- 这个 Compose 配置当前不是完整的 FastAPI + Next.js 工作台
- 如果你想体验新版 Web 工作台，仍然建议使用 `./start.sh`

## 测试与校验

### Python 测试

```bash
source test_platform/.venv/bin/activate
python3 -m pytest tests/platform_tests -q
```

### 前端检查

```bash
cd test_platform/web
npm run lint
npm test
npm run build
```

## 常见问题

### 1. `python3` 版本不对

先检查版本：

```bash
python3 -V
```

如果不是 `3.11+`，建议先切到正确解释器，再重新创建 `test_platform/.venv`。

### 2. `make ui` 或 `./start.sh` 启动失败

优先检查这几项：

1. `.env` 是否存在且关键变量已配置
2. `test_platform/.venv` 是否已安装依赖
3. `test_platform/web` 是否已执行过 `npm install`

### 3. 端口占用

[start.sh](./start.sh) 会自动尝试清理 `8000` 和 `3000` 的残留进程，但如果你是手动启动服务，仍然建议先自行检查端口占用。

### 4. 资讯机器人推送失败

优先检查：

1. `WECOM_WEBHOOK_URL` 或 `WECOM_QA_BOT_WEBHOOK_URL` 是否已配置
2. `ai_news_bot/.venv` 是否安装成功
3. 详细日志可参考 [ai_news_bot/README_news_bot.md](./ai_news_bot/README_news_bot.md)

## 相关文档

- [test_platform/docs/本地开发指南.md](./test_platform/docs/本地开发指南.md)
- [test_platform/docs/测试平台技术文档.md](./test_platform/docs/测试平台技术文档.md)
- [test_platform/web/README.md](./test_platform/web/README.md)
- [ai_news_bot/README_news_bot.md](./ai_news_bot/README_news_bot.md)
