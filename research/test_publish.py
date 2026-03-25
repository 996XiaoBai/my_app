import sys
import logging
sys.path.append('.')
from ai_news_bot.main_news_bot import NewsBot

logging.basicConfig(level=logging.INFO)

class MockItem:
    def __init__(self, title, summary, highlights, source, link, published, cover_image_url=""):
        self.title = title
        self.summary = summary
        self.highlights = highlights
        self.source = source
        self.link = link
        self.published = published
        self.cover_image_url = cover_image_url

items = [
    MockItem(
        title="字节跳动发布 Seedream5.0Lite: 具备“视觉推理”与“实时联网”能力的图像创作新标杆",
        summary="字节跳动Seed团队退出了Seedream5.0Lite智能图像创作模型，该模型通过多模态统一架构实现了从执行指令到深度理解意图的跨越，具有更强的视觉推理和实时联网能力，提升了图像生成的专业性和准确性。",
        highlights="* 🧠 **多步视觉推理**：模型能够理解物理规律并生成合理结果。\n* 🌐 **实时检索增强 (RAG)**：引入联网能力，精准生成时效性内容。\n* 📊 **深厚的世界知识**：内置多领域知识库，提升专业信息图谱的准确性。",
        source="AIBase", link="https://example.com/1", published="2月13日",
        cover_image_url="https://images.unsplash.com/photo-1677442136019-21780ecad995?q=80&w=600" # 测试用 AI 概念图
    ),
    MockItem(
        title="重拳治理 AI 假脸! 小红书: AI 合成内容须显著标识, 违规将扣除流量",
        summary="小红书针对AI技术滥用乱象，要求创作者对AI生成及合成内容进行主动标识，以维护社区内容的真实性与合规性。",
        highlights="* ⚖️ **强制标识AI生成内容**：以确保透明度和真实性。\n* 🔍 **平台将通过算法检测AI内容**，并对未声明的内容进行限流处理。\n* 🚫 **严厉打击制作虚假信息**、恶意“魔改”作品等行为，维护社区信任。",
        source="AIBase", link="https://example.com/2", published="2月13日",
        cover_image_url="https://images.unsplash.com/photo-1684469335607-1c3906a4b3bf?q=80&w=600"
    )
]

def run_test():
    bot = NewsBot()
    bot._publish_to_feishu(items)

if __name__ == '__main__':
    run_test()
