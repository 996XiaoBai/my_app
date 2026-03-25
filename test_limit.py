import yaml
import os
config_path = "ai_news_bot/config/qa_tools_config.yaml"
with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
filter_config = config.get("filter", {})
limit = filter_config.get("max_count", 15)
print("max_count in yaml:", limit)
