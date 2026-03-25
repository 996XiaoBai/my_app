import sys

file_path = "/Users/linkb/ai_news_bot/main_news_bot.py"
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip_mode = False
for line in lines:
    # 匹配 if img_url: 及其内部块
    if "if img_url:" in line and "img_url = getattr" not in line:
        skip_mode = True
        continue
    
    if skip_mode:
        # 如果是缩进的行或者是相关的注释/代码，继续跳过
        if line.strip() == "" or line.startswith("                    "):
            continue
        else:
            skip_mode = False
    
    new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Fix applied successfully.")
