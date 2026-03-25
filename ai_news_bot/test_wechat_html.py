from typing import List, Any
class NewsItem:
    def __init__(self, title, summary, link, source, highlights):
        self.title = title
        self.summary = summary
        self.link = link
        self.source = source
        self.highlights = highlights

def generate_html(news_items: List[Any]) -> str:
    html_parts = []
    html_parts.append("<section style='margin-bottom: 20px; line-height: 1.6; font-size: 15px; color: #333;'>")
    
    html_parts.append(f"<h2 style='font-size: 18px; margin-bottom: 15px; color: #576b95;'>AI 资讯前瞻</h2>")
    html_parts.append("<div style='margin-bottom: 30px; font-size: 15px; color: #444; line-height: 1.8;'>")
    for idx, item in enumerate(news_items, 1):
        title = getattr(item, 'title', '未知标题').replace('**', '') 
        html_parts.append(f"<p style='margin-bottom: 8px;'>{idx}. {title}</p>")
    html_parts.append("</div>")
    html_parts.append("<hr style='border: 0; height: 1px; background-color: #e5e5e5; margin: 30px 0;'>")
    
    for idx, item in enumerate(news_items, 1):
        html_parts.append(f"<h3 style='font-size: 17px; margin-top: 25px; margin-bottom: 12px; color: #1a1a1a;'><strong>{idx}. {item.title}</strong></h3>")
        html_parts.append(f"<p style='font-size: 13px; color: #888; margin-bottom: 12px;'>来源: {item.source}</p>")
        
        summary = item.summary.replace("\n", "<br>") if hasattr(item, 'summary') else ""
        html_parts.append(f"<p style='margin-bottom: 15px; text-align: justify;'>{summary}</p>")
        
        # image link (Removed as per user request)
        
        highlights = getattr(item, 'highlights', None)
        if highlights:
            html_parts.append("<div style='background-color: #f7f7f7; padding: 12px; border-radius: 6px; margin-bottom: 15px;'>")
            html_parts.append("<p style='font-weight: bold; margin-bottom: 8px; color: #333; font-size: 14px;'>亮点提要：</p>")
            html_parts.append("<ul style='padding-left: 20px; margin: 0; font-size: 14px;'>")
            
            hl_list = highlights if isinstance(highlights, list) else [h.strip() for h in highlights.split('\n') if h.strip()]
            for highlight in hl_list:
                if highlight.startswith("- ") or highlight.startswith("* "):
                    highlight = highlight[2:]
                html_parts.append(f"<li style='margin-bottom: 5px;'>{highlight}</li>")
            
            html_parts.append("</ul>")
            html_parts.append("</div>")
            
        link = getattr(item, 'link', '')
        if link:
            html_parts.append(f"<p style='font-size: 13px; color: #07c160; margin-bottom: 5px;'>阅读原文链接（请复制到浏览器打开）：<br><span style='word-break: break-all; color: #999;'>{link}</span></p>")
        
        if idx < len(news_items):
            html_parts.append("<hr style='border: 0; height: 1px; background-color: #e5e5e5; margin: 30px 0;'>")
            
    html_parts.append("</section>")
    return "".join(html_parts)

item = NewsItem(
    title="测试标题",
    summary="测试摘要...",
    link="https://test.com",
    source="Test Source",
    highlights="* 亮点 1"
)

html_out = generate_html([item])

if "查看文章原图" in html_out or "原图" in html_out or "🖼️" in html_out:
    print("WARNING: FOUND IMAGE LINK OR ICON IN HTML")
else:
    print("SUCCESS: NO IMAGE LINKS OR ICONS FOUND IN WECHAT HTML")

with open("wechat_preview.html", "w") as f:
    f.write(html_out)
