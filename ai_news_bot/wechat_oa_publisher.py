import requests
import time
import os
import json
from dataclasses import dataclass
from typing import List, Optional, Any

@dataclass
class Article:
    title: str
    author: str
    digest: str
    content: str
    content_source_url: str
    thumb_media_id: str
    need_open_comment: int = 1
    only_fans_can_comment: int = 0

class WeChatOAPublisher:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token = None
        self.token_expires_at = 0

    def _get_access_token(self) -> str:
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token

        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        try:
            resp = requests.get(url, timeout=10)
            data = resp.json()
            if "access_token" in data:
                self.access_token = data["access_token"]
                self.token_expires_at = time.time() + data["expires_in"] - 200 # 缓冲时间
                print("Successfully refreshed WeChat Access Token")
                return self.access_token
            else:
                raise Exception(f"Failed to get access token: {data}")
        except Exception as e:
            print(f"Error getting access token: {e}")
            raise

    def add_draft(self, articles: List[Article]) -> Optional[str]:
        """
        上传文章作为草稿。
        如果成功，返回草稿的 media_id。
        """
        token = self._get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
        
        articles_data = []
        for art in articles:
            articles_data.append({
                "title": art.title,
                "author": art.author,
                "digest": art.digest,
                "content": art.content,
                "content_source_url": art.content_source_url,
                "thumb_media_id": art.thumb_media_id,
                "need_open_comment": art.need_open_comment,
                "only_fans_can_comment": art.only_fans_can_comment
            })

        payload = {"articles": articles_data}
        
        try:
            # 微信 API 有时对 unicode escape (\uXXXX) 显示不友好，
            # 强制使用 ensure_ascii=False 发送 UTF-8 字符。
            headers = {"Content-Type": "application/json; charset=utf-8"}
            data_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            resp = requests.post(url, data=data_bytes, headers=headers, timeout=20)
            data = resp.json()
            if "media_id" in data:
                print(f"Draft created successfully: {data['media_id']}")
                return data["media_id"]
            else:
                print(f"Failed to create draft: {data}")
                return None
        except Exception as e:
            print(f"Error creating draft: {e}")
            return None

    def upload_image(self, image_path: str) -> Optional[str]:
        """
        上传图片作为缩略图。
        返回 media_id。
        """
        # 注意：'image' 类型用于永久素材
        token = self._get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
        
        try:
            with open(image_path, 'rb') as f:
                files = {'media': f}
                resp = requests.post(url, files=files, timeout=30)
                data = resp.json()
                if "media_id" in data:
                    return data["media_id"]
                else:
                    print(f"Failed to upload image: {data}")
                    return None
        except Exception as e:
            print(f"Error uploading image: {e}")
            return None

    def upload_image_from_bytes(self, filename: str, image_bytes: bytes, content_type: str) -> Optional[str]:
        """从内存中上传图片素材"""
        token = self._get_access_token()
        url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
        try:
            files = {'media': (filename, image_bytes, content_type)}
            resp = requests.post(url, files=files, timeout=30)
            data = resp.json()
            if "media_id" in data:
                return data["media_id"]
            else:
                print(f"Failed to upload image bytes: {data}")
                return None
        except Exception as e:
            print(f"Error uploading image bytes: {e}")
            return None

    def upload_image_from_url(self, image_url: str) -> Optional[str]:
        """下载公网图片并上传到微信永久素材库获取 media_id"""
        if not image_url:
            return None
        try:
            r = requests.get(image_url, timeout=10)
            if r.status_code == 200:
                image_bytes = r.content
                content_type = r.headers.get('Content-Type', 'image/jpeg')
                ext = content_type.split('/')[-1] if '/' in content_type else 'jpg'
                filename = f"cover.{ext}"
                return self.upload_image_from_bytes(filename, image_bytes, content_type)
            return None
        except Exception as e:
            print(f"Error downloading image from {image_url}: {e}")
            return None

    def generate_html(self, news_items: List[Any]) -> str:
        """根据抓取的新闻数据生成带内联 CSS 排版的微信适配 HTML 源码"""
        from datetime import datetime
        html_parts = []
        html_parts.append("<section style='margin-bottom: 20px; line-height: 1.6; font-size: 15px; color: #333;'>")
        
        # 预插入聚合目录
        html_parts.append(f"<h2 style='font-size: 18px; margin-bottom: 15px; color: #576b95;'>AI 资讯前瞻</h2>")
        html_parts.append("<div style='margin-bottom: 30px; font-size: 15px; color: #444; line-height: 1.8;'>")
        for idx, item in enumerate(news_items, 1):
            title = getattr(item, 'title', '未知标题').replace('**', '') # 清理标题中可能混入的 markdown
            html_parts.append(f"<p style='margin-bottom: 8px;'>{idx}. {title}</p>")
        html_parts.append("</div>")
        html_parts.append("<hr style='border: 0; height: 1px; background-color: #e5e5e5; margin: 30px 0;'>")
        
        for idx, item in enumerate(news_items, 1):
            html_parts.append(f"<h3 style='font-size: 17px; margin-top: 25px; margin-bottom: 12px; color: #1a1a1a;'><strong>{idx}. {item.title}</strong></h3>")
            html_parts.append(f"<p style='font-size: 13px; color: #888; margin-bottom: 12px;'>来源: {item.source}</p>")
            
            # summary
            summary = item.summary.replace("\n", "<br>") if hasattr(item, 'summary') else ""
            html_parts.append(f"<p style='margin-bottom: 15px; text-align: justify;'>{summary}</p>")
            
            # image link (Removed as per user request)
            # highlights
            highlights = getattr(item, 'highlights', None)
            if highlights:
                html_parts.append("<div style='background-color: #f7f7f7; padding: 12px; border-radius: 6px; margin-bottom: 15px;'>")
                html_parts.append("<p style='font-weight: bold; margin-bottom: 8px; color: #333; font-size: 14px;'>亮点提要：</p>")
                html_parts.append("<ul style='padding-left: 20px; margin: 0; font-size: 14px;'>")
                
                hl_list = highlights if isinstance(highlights, list) else [h.strip() for h in highlights.split('\n') if h.strip()]
                for highlight in hl_list:
                    # 去掉可能会跟原生 <li> 冲突的前缀
                    if highlight.startswith("- ") or highlight.startswith("* "):
                        highlight = highlight[2:]
                    html_parts.append(f"<li style='margin-bottom: 5px;'>{highlight}</li>")
                
                html_parts.append("</ul>")
                html_parts.append("</div>")
                
            link = getattr(item, 'link', '')
            if link:
                html_parts.append(f"<p style='font-size: 13px; color: #07c160; margin-bottom: 5px;'>阅读原文链接（请复制到浏览器打开）：<br><span style='word-break: break-all; color: #999;'>{link}</span></p>")
            
            # dividing line
            if idx < len(news_items):
                html_parts.append("<hr style='border: 0; height: 1px; background-color: #e5e5e5; margin: 30px 0;'>")
            
        html_parts.append("</section>")
        
        # 强制替换为微信识别的链接格式，且避开微信编辑器的拦截机制
        final_html = "".join(html_parts)
        # 有些微信后台会在普通 href 前面加拦截，甚至直接让 a 标签无法点击
        return final_html

    def push_to_draft(self, title: str, doc_url: str, news_items: List[Any]) -> Optional[str]:
        """从外部业务调用的封装主入口，处理图片上传、渲染并加入到草稿箱"""
        print(f"Pushing to Wechat Draft: {title}")
        
        import os
        
        # 使用全新生成的高清 AI NEWS 定制封面图
        thumb_media_id = ""
        local_cover_path = os.path.join(os.path.dirname(__file__), 'assets', 'hd_ai_news_brain_cover.png')
        
        print(f"Uploading HD local AI cover image from {local_cover_path}...")
        if os.path.exists(local_cover_path):
            tid = self.upload_image(local_cover_path)
            if tid:
                thumb_media_id = tid
        
        if not thumb_media_id:
            # 极低概率失败时的妥协，去文章里随便抓张图顶替防止发不出
            print("Fallback to extracting from article images due to local cover failure.")
            for item in news_items:
                img_url = getattr(item, 'image_url', getattr(item, 'cover_image_url', None))
                if img_url:
                    tid = self.upload_image_from_url(img_url)
                    if tid:
                        thumb_media_id = tid
                        break
        
        # 生成图文
        content_html = self.generate_html(news_items)
            
        digest = news_items[0].title if news_items else "今日 AI 资讯速递"
        if len(news_items) > 1:
            digest += f" 等共 {len(news_items)} 篇精要内容"
            
        article = Article(
            title=title,
            author="AI速递",
            digest=digest,
            content=content_html,
            content_source_url=doc_url or "",
            thumb_media_id=thumb_media_id,
        )
        return self.add_draft([article])
