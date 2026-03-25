FROM python:3.10-slim

WORKDIR /app

# 设置时区
ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装依赖
COPY test_platform/ai_news_bot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
# 注意：这里假设构建上下文是项目根目录
COPY test_platform /app/test_platform
COPY .env .

# 设置 PYTHONPATH
ENV PYTHONPATH=/app

# 运行调度器
CMD ["python", "test_platform/ai_news_bot/run_scheduler.py"]
