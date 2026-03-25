import os

import streamlit as st
import json
import tempfile

from test_platform.core.services.document_service import DocumentService
from test_platform.core.services.review_service import ReviewService
from test_platform.core.document_processing.vision_analyzer import DifyVisionAnalyzer
from test_platform.infrastructure.tapd_client import TAPDClient
from test_platform.core.data_generators.test_case_exporter import (
    parse_test_cases_from_text, export_to_excel, export_to_xmind
)
from test_platform.config import AgentConfig

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="兴趣岛需求评审助手",
    page_icon="🕵️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 注入自定义 CSS：顶级暗黑极客主题 (Linear / Untitled UI Vibe)
# ============================================================
st.markdown("""
<style>
    /* ===== 全局导入极客字体 ===== */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

    /* ===== 全局极简暗黑背景 (Linear Vibe) ===== */
    .stApp {
        background-color: #0A0A0A !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #F2F2F2 !important;
    }

    /* ===== 侧边栏精密仪表盘风 (Untitled UI Vibe) ===== */
    section[data-testid="stSidebar"] {
        background-color: #14151A !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    section[data-testid="stSidebar"] * {
        color: #A1A1AA !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* 侧边栏选中态 */
    .stRadio > div {
        background: transparent;
        gap: 4px;
    }
    .stRadio label {
        padding: 8px 12px;
        border-radius: 6px;
        transition: all 0.2s ease;
    }
    .stRadio label:hover {
        background: rgba(255,255,255,0.04);
        color: #F2F2F2 !important;
    }

    /* ===== 极客标题 (Dropbox Tech Vibe) ===== */
    .hero-title {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 2.5rem !important;
        font-weight: 900 !important;
        text-align: left;
        color: #FFFFFF;
        letter-spacing: -1px;
        margin-bottom: 0.2rem;
        text-shadow: 0 0 15px rgba(255, 255, 255, 0.2);
    }
    .hero-title::after {
        content: '_';
        animation: blink 1.2s step-end infinite;
        color: #34d399; /* 翡翠绿光标 */
        text-shadow: 0 0 12px #34d399;
    }
    @keyframes blink { 50% { opacity: 0; } }

    .hero-subtitle {
        text-align: left;
        color: #8b949e;
        font-size: 0.95rem;
        margin-bottom: 2.5rem;
        letter-spacing: 0.5px;
        font-family: 'JetBrains Mono', monospace;
    }

    /* ===== 极简质感卡片 (Game UI Hollow) ===== */
    .glass-card {
        background: transparent !important;
        border: 2px solid #333333 !important;
        border-radius: 24px !important;
        padding: 24px !important;
        margin-bottom: 16px !important;
        transition: all 0.3s ease !important;
    }
    .glass-card:hover {
        border-color: #FFB800 !important; /* 黄金边框 */
        box-shadow: 0 0 15px rgba(255, 184, 0, 0.15), inset 0 0 10px rgba(255, 184, 0, 0.05) !important;
        transform: translateY(-2px) !important;
    }

    /* ===== 状态指示灯 (Hollow Neon) ===== */
    .status-dot {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
        border: 2px solid currentColor;
        background: transparent;
        box-shadow: 0 0 8px currentColor, inset 0 0 4px currentColor;
    }
    .status-green { color: #00FF66; }
    .status-red { color: #FF0033; }
    .status-orange { color: #FFB800; }

    /* ===== 高级主按钮 (Neon Gold / Hollow Pill) ===== */
    .stButton > button[kind="primary"] {
        background: transparent !important;
        color: #FFB800 !important;
        border: 2px solid #FFB800 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        padding: 0.6rem 2rem !important;
        border-radius: 50px !important; /* 极致圆角 */
        transition: all 0.2s ease !important;
        box-shadow: 0 0 12px rgba(255, 184, 0, 0.25), inset 0 0 8px rgba(255, 184, 0, 0.15) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: rgba(255, 184, 0, 0.1) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 0 20px rgba(255, 184, 0, 0.5), inset 0 0 12px rgba(255, 184, 0, 0.3) !important;
        text-shadow: 0 0 8px rgba(255, 184, 0, 0.6);
    }

    /* 次级按钮 (Hollow Grey Pill) */
    .stButton > button[kind="secondary"], .stDownloadButton > button {
        background: transparent !important;
        border: 2px solid #444444 !important;
        color: #CCCCCC !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        border-radius: 50px !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="secondary"]:hover, .stDownloadButton > button:hover {
        border-color: #FFFFFF !important;
        color: #FFFFFF !important;
        box-shadow: 0 0 12px rgba(255, 255, 255, 0.2), inset 0 0 8px rgba(255, 255, 255, 0.1) !important;
        text-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
    }

    /* ===== 输入框与区域 (Hollow Inputs) ===== */
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        background: transparent !important;
        border: 2px solid #333333 !important;
        border-radius: 50px !important; /* 输入框全圆角 */
        color: #FFFFFF !important;
        font-family: 'JetBrains Mono', monospace !important;
        transition: all 0.2s ease;
        padding-left: 16px !important;
    }
    .stTextArea > div > div > textarea {
        border-radius: 16px !important; /* 文本域保留微圆角防变形 */
    }
    .stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
        border-color: #FFB800 !important; /* 黄金光标焦点 */
        box-shadow: 0 0 10px rgba(255, 184, 0, 0.3), inset 0 0 5px rgba(255, 184, 0, 0.1) !important;
    }

    /* ===== 文件上传区域 (Hollow Dashed) ===== */
    .stFileUploader > div {
        border: 2px dashed #444444 !important;
        border-radius: 20px !important;
        background: transparent !important;
        transition: all 0.2s ease !important;
    }
    .stFileUploader > div:hover {
        border-color: #FFB800 !important;
        box-shadow: 0 0 15px rgba(255, 184, 0, 0.15) !important;
    }

    /* ===== Markdown / 文本框等排版 ===== */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        color: #FFFFFF !important;
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.1);
        letter-spacing: -0.5px !important;
    }
    code {
        font-family: 'JetBrains Mono', monospace !important;
        background: transparent !important;
        border: 1px solid #FFB800 !important;
        padding: 0.2em 0.5em !important;
        border-radius: 8px !important;
        font-size: 0.85em !important;
        color: #FFB800 !important;
        box-shadow: 0 0 5px rgba(255, 184, 0, 0.2);
    }

    /* ===== 评审报告容器 (Hollow Box) ===== */
    .report-wrapper {
        background: transparent;
        border: 2px solid #333333;
        border-radius: 24px;
        padding: 32px;
        margin-top: 16px;
    }

    /* ===== 侧边栏标题装饰 (Neon glowing text) ===== */
    .sidebar-section-title {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 3px;
        color: #FFB800;
        text-shadow: 0 0 8px rgba(255, 184, 0, 0.4);
        margin-top: 16px;
        margin-bottom: 12px;
    }

    /* ===== Tab 美化 (Hollow glow active tabs) ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
        border-bottom: 2px solid #333333;
        padding: 0px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 20px 20px 0 0 !important;
        color: #777777 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        padding: 12px 24px !important;
        border: 2px solid transparent !important;
        border-bottom: none !important;
        margin-right: 4px !important;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(255, 184, 0, 0.05) !important;
        color: #FFB800 !important;
        border: 2px solid #FFB800 !important;
        border-bottom: none !important;
        box-shadow: 0 -4px 10px rgba(255, 184, 0, 0.15), inset 0 4px 10px rgba(255, 184, 0, 0.05) !important;
    }

    /* ===== Slider ===== */
    .stSlider > div > div > div > div {
        background: #FFB800 !important;
        box-shadow: 0 0 10px rgba(255, 184, 0, 0.6);
    }
    
    /* ===== Radio (Hollow Pills) ===== */
    .stRadio > div {
        background: transparent;
        gap: 8px;
    }
    .stRadio label {
        padding: 10px 16px;
        border-radius: 50px;
        border: 2px solid #333333;
        transition: all 0.2s ease;
    }
    .stRadio label:hover {
        border-color: #FFB800;
        color: #FFB800 !important;
        box-shadow: 0 0 10px rgba(255, 184, 0, 0.2);
    }

    /* ===== Alert / Info Boxes ===== */
    .stAlert {
        background: transparent !important;
        border-radius: 16px !important;
        border: 2px dashed #555555 !important;
        color: #FFFFFF !important;
    }

    /* ===== 隐藏 Streamlit 默认页脚 ===== */
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 键盘快捷键：Ctrl+Enter 触发主按钮
# ============================================================
import streamlit.components.v1 as components
components.html("""
<script>
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        // 查找 Streamlit 主按钮（primary 类型）
        const buttons = window.parent.document.querySelectorAll('button[kind="primary"]');
        if (buttons.length > 0) {
            buttons[0].click();
        }
    }
});
</script>
""", height=0, width=0)

# ============================================================
# 初始化 Agent（缓存）
# ============================================================
from test_platform.utils.history_manager import HistoryManager

# ============================================================
# 初始化 Agent（缓存）
# ============================================================
@st.cache_resource
def get_services():
    review_service = ReviewService()
    # P1 解耦：注入 Dify 专用的视觉适配器
    vision_analyzer = DifyVisionAnalyzer(
        client=review_service.client, 
        user_id=review_service.config.DIFY_USER_ID
    )
    document_service = DocumentService(vision_analyzer=vision_analyzer)
    return document_service, review_service

@st.cache_resource
def get_history_manager():
    return HistoryManager()

from test_platform.core.services.weekly_report_service import WeeklyReportService
from test_platform.infrastructure.feishu_client import FeishuClient

document_service, review_service = get_services()
history_manager = get_history_manager()

@st.cache_resource
def get_weekly_report_service():
    feishu_client = FeishuClient(
        app_id=AgentConfig.FEISHU_APP_ID,
        app_secret=AgentConfig.FEISHU_APP_SECRET,
        folder_token=AgentConfig.FEISHU_FOLDER_TOKEN
    )
    return WeeklyReportService(review_service.client, feishu_client, AgentConfig)

weekly_report_service = get_weekly_report_service()



# ============================================================
# 页面标题（带动画渐变）
# ============================================================
st.markdown("<div class='hero-title'>兴趣岛 智能评审与测开基建</div>", unsafe_allow_html=True)
st.markdown("<div class='hero-subtitle'>面向未来的高阶需求诊断与自动化平台</div>", unsafe_allow_html=True)

# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ 控制面板")
    
    st.markdown("<div class='sidebar-section-title'>功能模式</div>", unsafe_allow_html=True)
    mode_options = ["review", "test_case", "req_analysis", "test_point", "log_diagnosis", "test_data", "impact_analysis", "test_plan", "flowchart", "api_test_gen", "api_perf_test_gen", "auto_script_gen", "weekly_report"]
    
    # 查找当前模式在选项中的索引
    current_mode_val = st.session_state.get('curr_review_mode', 'review')
    try:
        default_index = mode_options.index(current_mode_val)
    except ValueError:
        default_index = 0

    review_mode = st.radio(
        "功能模式",
        options=mode_options,
        format_func=lambda x: {
            "review": "📝 需求评审",
            "test_case": "🧪 生成测试用例",
            "req_analysis": "🔬 需求结构化分析",
            "test_point": "🎯 测试点提取",
            "log_diagnosis": "🔍 缺陷日志诊断",
            "test_data": "🏗️ 测试数据准备",
            "impact_analysis": "⚡ 需求影响面分析",
            "test_plan": "📅 制定测试方案",
            "flowchart": "📊 业务流程导图",
            "api_test_gen": "🔌 接口测试生成",
            "api_perf_test_gen": "🚀 接口性能压测",
            "auto_script_gen": "🤖 UI 自动化脚本",
            "weekly_report": "🗓️ 智能周报生成"
        }.get(x, x),
        index=default_index,
        label_visibility="collapsed"
    )
    # 同步到业务变量
    st.session_state['curr_review_mode'] = review_mode
    
    # 检测模式切换，清除输出缓存但保留已解析的文档结构（避免重复解析）
    if st.session_state.get('_last_review_mode') != review_mode:
        for key in ['review_result', 'result_title', 'review_mode',
                     'mermaid_edit_codes']:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state['_last_review_mode'] = review_mode
    
    selected_roles = []
    
    if review_mode == "review":
        st.caption("资深专家独立视角评审，支持多角色并行")
        st.markdown("<div class='sidebar-section-title'>评审视角</div>", unsafe_allow_html=True)
        
        # 复选框垂直排列，避免 st.columns 在侧边栏的 DOM 不稳定性
        if st.checkbox("📋 产品视角", value=True, key="role_product", help="逻辑闭环、多端协同"): selected_roles.append("product")
        if st.checkbox("💻 技术视角", value=True, key="role_tech", help="架构设计、并发安全"): selected_roles.append("tech")
        if st.checkbox("🎨 设计视角", value=False, key="role_design", help="交互体验、视觉规范"): selected_roles.append("design")
        if st.checkbox("🧪 测试视角", value=True, key="role_test", help="边界条件、异常场景"): selected_roles.append("test")
        if st.checkbox("🔒 安全视角", value=True, key="role_security", help="数据合规、越权风险"): selected_roles.append("security")
            
        if not selected_roles:
            st.warning("⚠️ 请至少勾选一个视角")
    
    elif review_mode == "test_case":
        st.caption("基于四步法专家思维，一键智能生成包含正向、异常、并发安全等多维度的结构化用例")
    elif review_mode == "req_analysis":
        st.caption("五步法深度拆解需求：业务流程、数据逻辑、交互规则、隐性需求一网打尽")
    elif review_mode == "test_point":
        st.caption("九维全景分析：功能/边界/异常/性能/安全/兼容性等维度提取测试点")
    elif review_mode == "log_diagnosis":
        st.caption("粘贴崩溃日志或业务日志，AI 将自动分析报错位置、原因并提供修复建议")
    elif review_mode == "test_data":
        st.caption("根据描述生成 SQL、JSON 或虚拟用户信息，缩短环境准备时间")
    elif review_mode == "impact_analysis":
        st.caption("对比两个版本的需求文档，提取变更点并评估对现有功能的影响面")
    elif review_mode == "test_plan":
        st.caption("从项目目标、资源、策略、风险等多维度自动生成标准测试方案")
    elif review_mode == "flowchart":
        st.caption("自动提取需求中的业务逻辑节点，生成高颜值的 Mermaid 业务流程图")
    elif review_mode == "api_test_gen":
        st.caption("上传 Swagger/Text 接口文档，自动生成覆盖正向/异常/边界场景的 Pytest 脚本")
    elif review_mode == "api_perf_test_gen":
        st.caption("上传接口文档，自动转换并生成可高并发执行的 Locust 压测脚本，含断言与请求参数。")
    elif review_mode == "auto_script_gen":
        st.caption("上传测试用例描述或页面 HTML 代码，自动生成 Python + Playwright 自动化脚本")
    elif review_mode == "weekly_report":
        st.caption("粘贴企业微信讨论多行复制内容，并上传 TAPD 任务截图，AI 自动清洗总结并写入飞书文档")
    
    # 输出模版选择（始终渲染，非测试用例模式时禁用）
    st.markdown("<div class='sidebar-section-title'>输出模版</div>", unsafe_allow_html=True)
    case_template = st.radio(
        "输出模版",
        options=["excel", "xmind"],
        format_func=lambda x: "📊 Excel（TAPD 导入格式）" if x == "excel" else "🧠 XMind（思维导图格式）",
        index=1,
        label_visibility="collapsed",
        disabled=(review_mode != "test_case"),
        key="case_template_radio"
    )
    if review_mode != "test_case":
        st.caption("💡 选择「生成测试用例」模式后可选模版")
    


    
    st.markdown("<div class='sidebar-section-title'>接口状态</div>", unsafe_allow_html=True)
    
    # Dify 状态
    if review_service.config.DIFY_API_KEY:
        st.markdown("<span class='status-dot status-green'></span> Dify API 已连接", unsafe_allow_html=True)
    else:
        st.markdown("<span class='status-dot status-red'></span> Dify API 密钥缺失", unsafe_allow_html=True)
    
    # TAPD 状态
    if review_service.tapd_client:
        st.markdown("<span class='status-dot status-green'></span> TAPD API 已连接", unsafe_allow_html=True)
    else:
        st.markdown("<span class='status-dot status-orange'></span> TAPD 凭据未配置", unsafe_allow_html=True)
        
    st.markdown("---")
    st.markdown("<div class='sidebar-section-title'>📜 历史记录</div>", unsafe_allow_html=True)
    
    # 模式筛选
    mode_label_map = {
        "全部": None, "评审": "review", "用例": "test_case", "分析": "req_analysis",
        "测试点": "test_point", "方案": "test_plan", "流程图": "flowchart",
        "日志": "log_diagnosis", "数据": "test_data", "影响面": "impact_analysis",
        "周报": "weekly_report"
    }
    filter_mode = st.selectbox("筛选模式", options=list(mode_label_map.keys()),
                               index=0, label_visibility="collapsed", key="history_filter")
    filter_val = mode_label_map[filter_mode]
    
    # 获取最近 20 条记录
    recent_reports = history_manager.list_reports(limit=20)
    if filter_val:
        recent_reports = [r for r in recent_reports if r.get('type') == filter_val]
    
    if recent_reports:
        selected_report_id = st.selectbox(
            "选择历史报告",
            options=[r['id'] for r in recent_reports],
            format_func=lambda x: next((f"{r['timestamp'][5:10]} {r['filename'][:10]}..." for r in recent_reports if r['id'] == x), x),
            index=None,
            placeholder="查看历史...",
            label_visibility="collapsed"
        )
        
        if selected_report_id:
            cols_hist = st.columns(2)
            with cols_hist[0]:
                if st.button("📂 加载", use_container_width=True):
                    report_path = next((r['file_path'] for r in recent_reports if r['id'] == selected_report_id), None)
                    if report_path:
                        loaded_data = history_manager.load_report(report_path)
                        if loaded_data:
                            mode = loaded_data.get('type', 'review')
                            st.session_state['review_result'] = loaded_data['content']
                            st.session_state['result_title'] = {
                                "review": "📝 评审报告",
                                "test_case": "🧪 测试用例",
                                "req_analysis": "🔬 需求结构化分析",
                                "test_point": "🎯 测试点分析报告",
                                "log_diagnosis": "🔍 日志诊断报告",
                                "test_data": "🏗️ 测试数据准备结果",
                                "impact_analysis": "⚡ 影响面评估报告",
                                "test_plan": "📅 标准测试方案",
                                "flowchart": "📊 业务流程图",
                                "api_test_gen": "🔌 接口测试脚本",
                                "api_perf_test_gen": "🚀 性能压测脚本",
                                "auto_script_gen": "🤖 UI 测试脚本",
                                "weekly_report": "🗓️ 飞书周报"
                            }.get(mode, "📝 历史报告")
                            st.session_state['review_mode'] = mode
                            st.session_state['download_name'] = loaded_data.get('filename', 'report') + ".md"
                            st.success("✅ 已加载！")
                            st.rerun()
            with cols_hist[1]:
                if st.button("📊 对比", use_container_width=True, help="加载后再选另一条进行对比"):
                    report_path = next((r['file_path'] for r in recent_reports if r['id'] == selected_report_id), None)
                    if report_path:
                        loaded_data = history_manager.load_report(report_path)
                        if loaded_data:
                            st.session_state['compare_result'] = loaded_data['content']
                            st.session_state['compare_title'] = f"{loaded_data['filename'][:15]} ({loaded_data['type']})"
                            st.success("✅ 已加入对比栏！")
    else:
        st.caption("暂无历史记录")

    st.markdown("---")
    st.markdown(
        "<div style='text-align:center; color: rgba(255,255,255,0.2); font-size:0.75rem; margin-top:20px;'>"
        "v2.0 · Built with Streamlit + Dify"
        "</div>", 
        unsafe_allow_html=True
    )

# ============================================================
# 主要内容区
# ============================================================

# ============================================================
# ****** 周报模式：独立 UI 流程，不走通用评审管线 ******
# ============================================================
if review_mode == "weekly_report":
    st.markdown("""
    <div class='glass-card'>
        <p style='margin:0; color: rgba(255,255,255,0.7); font-size: 0.95rem;'>
        📌 <strong>使用方式</strong>：将企业微信本周关键讨论内容复制粘贴到下方文本框，再上传 TAPD 工作任务截图（支持多张），点击生成后 AI 会自动清洗总结并写入飞书文档。
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # 输入区 1：企业微信讨论内容
    st.markdown("### 💬 企业微信关键讨论")
    wecom_text = st.text_area(
        "粘贴本周企业微信群聊中的关键讨论内容",
        height=250,
        placeholder="将企业微信的讨论记录复制粘贴到这里...\n\n支持多行文本，AI 会自动过滤闲聊、提取核心技术讨论。",
        label_visibility="collapsed",
        key="wecom_text_input"
    )
    if wecom_text:
        st.info(f"💡 已就绪：{len(wecom_text)} 字符")
    
    # 输入区 2：TAPD 截图上传
    st.markdown("### 📸 TAPD 工作任务截图")
    tapd_screenshots = st.file_uploader(
        "上传 TAPD 截图（支持多张）",
        type=["png", "jpg", "jpeg", "bmp", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key="tapd_screenshot_uploader"
    )
    if tapd_screenshots:
        cols_preview = st.columns(min(len(tapd_screenshots), 4))
        for i, img_file in enumerate(tapd_screenshots):
            with cols_preview[i % 4]:
                st.image(img_file, caption=img_file.name, use_container_width=True)
        st.success(f"✅ 已上传 {len(tapd_screenshots)} 张截图")
    
    # 附加指令
    extra_prompt_wr = st.text_input(
        "📌 附加指令（可选）",
        placeholder="例如：重点突出性能优化相关工作、侧重 Bug 修复进展…",
        help="在此输入额外的总结要求",
        key="weekly_report_extra_prompt"
    )
    
    st.markdown("<br/>", unsafe_allow_html=True)
    
    # 生成按钮
    if st.button("🗓️ 生成飞书周报", type="primary", use_container_width=True):
        if not wecom_text and not tapd_screenshots:
            st.warning("⚠️ 请至少提供企业微信讨论内容或 TAPD 截图")
        else:
            with st.status("🤖 正在清洗总结本周关键讨论并生成飞书周报……", expanded=True) as status:
                try:
                    from test_platform.infrastructure.feishu_client import FeishuClient
                    from test_platform.core.services.weekly_report_service import WeeklyReportService
                    from test_platform.config import AgentConfig
                    import datetime
                    
                    config = AgentConfig
                    
                    status.update(label="📡 正在初始化飞书和 Dify 服务……")
                    st.write("📡 正在初始化服务……")
                    
                    # 初始化飞书客户端（使用周报专用的知识库节点 Token）
                    feishu_client = FeishuClient(
                        app_id=config.FEISHU_APP_ID,
                        app_secret=config.FEISHU_APP_SECRET,
                        folder_token=config.FEISHU_WEEKLY_REPORT_FOLDER_TOKEN or config.FEISHU_FOLDER_TOKEN
                    )
                    
                    # 初始化周报服务
                    weekly_report_svc = WeeklyReportService(
                        dify_client=review_service.client,
                        feishu_client=feishu_client,
                        config=config
                    )
                    
                    # 保存截图到临时文件
                    image_paths = []
                    if tapd_screenshots:
                        status.update(label=f"🖼️ 正在处理 {len(tapd_screenshots)} 张截图……")
                        st.write(f"🖼️ 正在处理 {len(tapd_screenshots)} 张截图……")
                        for img_file in tapd_screenshots:
                            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{img_file.name.split('.')[-1]}") as tmp:
                                tmp.write(img_file.getvalue())
                                image_paths.append(tmp.name)
                    
                    # 1. 调用 Dify 总结
                    combined_wecom = wecom_text or ""
                    if extra_prompt_wr:
                        combined_wecom += f"\n\n【附加要求】{extra_prompt_wr}"
                    
                    status.update(label="🧠 AI 正在清洗和总结内容……")
                    st.write("🧠 AI 正在清洗和总结内容……")
                    summary_md = weekly_report_svc.summarize_report(combined_wecom, image_paths)
                    
                    if not summary_md:
                        st.error("❌ AI 总结失败，请检查 Dify API 连接或重试。")
                    else:
                        # 保存总结到 session
                        st.session_state['review_result'] = summary_md
                        st.session_state['result_title'] = "🗓️ 飞书周报预览"
                        st.session_state['review_mode'] = 'weekly_report'
                        st.session_state['download_name'] = '周报摘要.md'
                        
                        # 2. 导出到飞书
                        status.update(label="📝 正在写入飞书文档……")
                        st.write("📝 正在写入飞书文档……")
                        today = datetime.date.today()
                        week_start = today - datetime.timedelta(days=today.weekday())
                        week_end = week_start + datetime.timedelta(days=4)
                        title = f"软件测试周报 {week_start.strftime('%Y-%m-%d')} — {week_end.strftime('%Y-%m-%d')}"
                        
                        doc_url = weekly_report_svc.export_to_feishu(title, summary_md)
                        
                        if doc_url:
                            st.session_state['feishu_doc_url'] = doc_url
                            status.update(label="✅ 周报已生成并成功写入飞书！", state="complete", expanded=False)
                            st.success(f"✅ 飞书文档已创建！")
                            st.markdown(f"🔗 [点击查看飞书文档]({doc_url})", unsafe_allow_html=True)
                        else:
                            status.update(label="⚠️ 总结完成但飞书写入失败", state="error")
                            st.warning("⚠️ AI 总结已完成，但写入飞书文档失败。请检查飞书应用凭证。下方可预览和下载总结内容。")
                        
                        # 自动保存到历史记录
                        try:
                            history_manager.save_report(
                                content=summary_md,
                                filename=f"周报_{week_start.strftime('%m%d')}-{week_end.strftime('%m%d')}",
                                report_type='weekly_report'
                            )
                        except Exception as e:
                            st.warning(f"⚠️ 自动保存历史失败: {e}")
                    
                    # 清理临时截图文件
                    for p in image_paths:
                        if os.path.exists(p):
                            os.remove(p)
                            
                except Exception as e:
                    st.error(f"❌ 周报生成失败: {e}")
                    import traceback
                    st.code(traceback.format_exc(), language="text")
    
    # 显示飞书链接（如果之前已经生成过）
    if 'feishu_doc_url' in st.session_state and 'review_result' in st.session_state:
        st.markdown("---")
        st.markdown(f"🔗 **上次生成的飞书文档**：[点击查看]({st.session_state['feishu_doc_url']})")

# ============================================================
# 以下为通用评审管线（非 weekly_report 模式使用）
# ============================================================
if review_mode == "weekly_report":
    # 周报模式的结果展示区域
    if 'review_result' in st.session_state and st.session_state.get('review_mode') == 'weekly_report':
        st.markdown("---")
        col_title, col_clear = st.columns([4, 1])
        with col_title:
            st.markdown(f"## {st.session_state.get('result_title', '🗓️ 飞书周报预览')}")
        with col_clear:
            if st.button("🗑️ 清除结果"):
                for key in ['review_result', 'feishu_doc_url']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
        
        st.markdown(st.session_state['review_result'], unsafe_allow_html=True)
        
        st.markdown("---")
        st.download_button(
            label="📥 下载周报（Markdown）",
            data=st.session_state['review_result'],
            file_name=st.session_state.get('download_name', '周报摘要.md'),
            mime="text/markdown",
            use_container_width=True
        )
    st.stop()  # 终止此处，不进入下方通用管线

tab_file, tab_text, tab_tapd = st.tabs(["📂 文件上传", "📝 文本粘贴", "🔗 TAPD 需求"])

req_context = ""
pasted_text = ""
file_path_to_process = None

with tab_file:

    uploader_label = "上传需求文档"
    if review_mode == "log_diagnosis":
        uploader_label = "上传日志文件（可选）"
    elif review_mode == "impact_analysis":
        uploader_label = "上传旧版本 (V1.0) 文档"
    elif review_mode in ["api_test_gen", "api_perf_test_gen"]:
        uploader_label = "上传接口文档 (Swagger/JSON/YAML/Txt)"
    elif review_mode == "auto_script_gen":
        uploader_label = "上传测试用例/页面代码 (Txt/HTML)"
    
    uploaded_file = st.file_uploader(uploader_label, 
        type=["pdf", "docx", "doc", "xlsx", "xls", "txt", "md", "html", "htm", "csv", "rtf", "log", "json", "yaml", "yml", "xml"],
        label_visibility="collapsed")
    
    if uploaded_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            file_path_to_process = tmp_file.name
        st.success(f"✅ 文件已上传：{uploaded_file.name}")
        
        # PDF 预览区域
        if uploaded_file.name.lower().endswith('.pdf'):
            with st.expander("📄 PDF 预览", expanded=False):
                try:
                    from pdf2image import convert_from_bytes
                    images = convert_from_bytes(uploaded_file.getvalue(), first_page=1, last_page=20, dpi=100)
                    for i, img in enumerate(images):
                        st.image(img, caption=f"第 {i+1} 页", use_container_width=True)
                except ImportError:
                    st.info(f"📄 文件大小：{len(uploaded_file.getvalue()) / 1024:.1f} KB（安装 pdf2image 可启用缩略图预览）")
                except Exception as e:
                    st.info(f"📄 文件大小：{len(uploaded_file.getvalue()) / 1024:.1f} KB")

    # 对于影响面分析，增加第二个文件上传
    if review_mode == "impact_analysis":
        st.markdown("<br/>", unsafe_allow_html=True)
        uploaded_file_new = st.file_uploader("上传新版本 (V2.0) 文档", 
            type=["pdf", "docx", "doc", "xlsx", "xls", "txt", "md", "html", "htm", "csv", "rtf"],
            key="uploader_v2")
        
        if uploaded_file_new:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file_new.name.split('.')[-1]}") as tmp_file_n:
                tmp_file_n.write(uploaded_file_new.getvalue())
                st.session_state['file_v2'] = tmp_file_n.name
            st.success(f"✅ 新版本文件已上传：{uploaded_file_new.name}")

with tab_text:
    paste_label = "粘贴内容"
    pasted_text = st.session_state.get('pasted_content', "")
    
    # 快速示例模版
    cols_tpl = st.columns(3)
    if review_mode == "log_diagnosis":
        with cols_tpl[0]:
            if st.button(" örnek 堆栈日志", key="tpl_log_1"):
                 st.session_state['pasted_content'] = "java.lang.NullPointerException\n  at com.example.MyClass.doSomething(MyClass.java:42)\n  at com.example.Main.main(Main.java:10)"
        with cols_tpl[1]:
            if st.button(" örnek 接口报错", key="tpl_log_2"):
                 st.session_state['pasted_content'] = "ERROR 2024-02-15 10:00:00 [Req-123] - Failed to fetch user profile\nResponse: 504 Gateway Timeout\nURL: /api/v1/user/123"
    elif review_mode == "test_data":
        with cols_tpl[0]:
            if st.button(" örnek 用户数据", key="tpl_data_1"):
                 st.session_state['pasted_content'] = "生成10条用户数据，包含：姓名、手机号（脱敏）、模拟身份证号、余额（10-500随机）"
        with cols_tpl[1]:
             if st.button(" örnek 嵌套JSON", key="tpl_data_2"):
                  st.session_state['pasted_content'] = "构造一个复杂的电商订单 JSON，包含：订单号、商品列表（含SKU和属性）、收货人地址、分期支付计划"
    elif review_mode == "req_analysis":
        with cols_tpl[0]:
            if st.button(" örnek 报名活动", key="tpl_req_1"):
                 st.session_state['pasted_content'] = "需求：用户可以在小程序内报名活动，填写姓名、手机号、人数，支付费用后生成报名码。支持取消报名和退款。"
    elif review_mode == "test_point":
        with cols_tpl[0]:
            if st.button(" örnek 登录功能", key="tpl_tp_1"):
                 st.session_state['pasted_content'] = "需求：用户可以通过手机号+验证码或账号+密码登录，支持微信三方登录，登录失败超过5次锁定账号30分钟。"
    elif review_mode == "test_plan":
        with cols_tpl[0]:
            if st.button(" örnek 营销活动方案", key="tpl_plan_1"):
                 st.session_state['pasted_content'] = "需求：新用户注册送100元满减券，需要支持H5和App端，涉及风控校验。请制定测试方案。"
    elif review_mode == "flowchart":
        with cols_tpl[0]:
            if st.button(" örnek 订单流转逻辑", key="tpl_flow_1"):
                 st.session_state['pasted_content'] = "业务逻辑：用户下单 -> 支付校验 -> 支付成功扣库存并通知发货 -> 支付失败进入待支付列表（30分钟自动取消）。"
    
    pasted_text = st.text_area(paste_label, value=st.session_state.get('pasted_content', ""), height=300, label_visibility="collapsed")
    st.session_state['pasted_content'] = pasted_text
    
    if pasted_text:
        st.info(f"💡 已就绪：{len(pasted_text)} 字符")

with tab_tapd:
    st.markdown("""
    <div class='glass-card'>
        <p style='margin:0; color: rgba(255,255,255,0.6);'>
        输入 TAPD 需求 ID 或完整链接，系统将自动提取并获取需求内容
        </p>
    </div>
    """, unsafe_allow_html=True)
    story_input = st.text_input("TAPD 需求 ID 或链接", placeholder="例：10086 或 https://www.tapd.cn/.../view/10086", label_visibility="collapsed")
    if story_input:
        story_id = TAPDClient.parse_story_id(story_input)
        if story_id:
            if st.button("🌍 从 TAPD 获取", use_container_width=True):
                with st.spinner(f"正在获取需求 #{story_id}..."):
                    tapd_req = review_service.fetch_requirement_from_tapd(story_id)
                    if tapd_req:
                        st.session_state['tapd_req'] = tapd_req
                        st.success("✅ 需求获取成功！")
                        with st.expander("📄 查看内容"):
                            st.text(tapd_req)
                    else:
                        st.error("❌ 获取失败，请检查 ID 或权限。")
        else:
            st.warning("⚠️ 无效的 TAPD ID 或链接")

# ============================================================
# 开始评审/生成
# ============================================================
# 根据模式设置按钮和提示文本
# ============================================================
# 开始评审/生成
# ============================================================
# 根据模式设置按钮和提示文本
button_text = {
    "review": "🚀 开始评审",
    "test_case": "🧪 生成测试用例",
    "req_analysis": "🔬 开始分析",
    "test_point": "🎯 提取测试点",
    "log_diagnosis": "🔍 诊断日志",
    "test_data": "🏗️ 生成测试数据 SQL",
    "impact_analysis": "⚡ 分析影响面",
    "test_plan": "📅 生成方案",
    "flowchart": "📊 生成流程图",
    "api_test_gen": "🔌 生成测试脚本",
    "api_perf_test_gen": "🚀 生成压测脚本",
    "auto_script_gen": "🤖 生成自动脚本",
    "weekly_report": "🗓️ 生成飞书周报"
}[review_mode]

spinner_text = {
    "review": "🤖 AI 专家团正在评审……",
    "test_case": "🤖 正在根据需求文档生成测试用例……",
    "req_analysis": "🤖 正在深度拆解需求结构，识别业务流与数据逻辑……",
    "test_point": "🤖 正在进行九维全景测试点分析……",
    "log_diagnosis": "🤖 正在深入分析日志细节并定位风险……",
    "test_data": "🤖 正在根据技术文档准备测试数据 SQL……",
    "impact_analysis": "🤖 正在对比双版本需求并评估波及范围……",
    "test_plan": "🤖 正在全力为您拆解需求并制定测试方案……",
    "flowchart": "🤖 正在梳理业务逻辑并绘制高颜值流程图……",
    "api_test_gen": "🤖 正在分析接口数据并生成 Pytest 脚本……",
    "api_perf_test_gen": "🤖 正在转换为 Locust 框架格式压测脚本……",
    "auto_script_gen": "🤖 正在生成 Playwright 自动化测试脚本……",
    "weekly_report": "🤖 正在清洗总结本周关键讨论并生成飞书周报……"
}[review_mode]

success_text = "✅ 任务执行完成！"
result_title = {
    "review": "📝 评审报告",
    "test_case": "🧪 测试用例",
    "req_analysis": "🔬 需求结构化分析",
    "test_point": "🎯 测试点分析报告",
    "log_diagnosis": "🔍 日志诊断报告",
    "test_data": "🏗️ 测试数据准备结果",
    "impact_analysis": "⚡ 影响面评估报告",
    "test_plan": "📅 标准测试方案",
    "flowchart": "📊 业务流程图",
    "api_test_gen": "🔌 接口测试脚本",
    "api_perf_test_gen": "🚀 性能压测脚本",
    "auto_script_gen": "🤖 UI 测试脚本",
    "weekly_report": "🗓️ 飞书周报预览"
}[review_mode]

download_name = {
    "review": "需求评审报告.md",
    "test_case": "测试用例.md",
    "req_analysis": "需求结构化分析.md",
    "test_point": "测试点分析.md",
    "log_diagnosis": "日志诊断报告.md",
    "test_data": "测试数据准备.md",
    "impact_analysis": "影响面分析报告.md",
    "test_plan": "测试方案.md",
    "flowchart": "业务流程图.md",
    "api_test_gen": "接口自动化脚本.py",
    "api_perf_test_gen": "Locust性能压测脚本.py",
    "auto_script_gen": "UI自动化脚本.py",
    "weekly_report": "周报摘要.md"
}[review_mode]

st.markdown("<br/>", unsafe_allow_html=True)

# ============================================================
# 附加指令（自定义 Prompt 注入）
# ============================================================
extra_prompt = st.text_input(
    "📌 附加指令（可选）",
    placeholder="例如：重点关注支付模块的异常场景、只分析领队端功能…",
    help="在此输入额外的分析要求，AI 会在处理时优先关注这些方面"
)

# 准备输入
final_req = ""
final_path = None
if pasted_text:
    final_req = pasted_text
elif file_path_to_process:
    final_path = file_path_to_process
elif 'tapd_req' in st.session_state and st.session_state['tapd_req']:
    final_req = st.session_state['tapd_req']

# 步骤 1: 解析目录（如果尚未解析）
# 步骤 1: 解析目录（如果尚未解析）
if final_path or final_req:
    # 修复：使用 file_id 或文件元数据作为 hash，而不是每次都变的 temp path
    if uploaded_file:
         # 组合文件名和大小作为唯一标识
         input_identifier = f"{uploaded_file.name}_{uploaded_file.size}"
    else:
         input_identifier = final_req

    current_input_hash = hash(input_identifier)
    
    if st.session_state.get('last_input_hash') != current_input_hash:
        if 'parsed_data' in st.session_state:
            del st.session_state['parsed_data']
            st.session_state['last_input_hash'] = current_input_hash

    if 'parsed_data' not in st.session_state:
        # 一键执行模式判断：
        # - 纯文本工具型模式（日志诊断、数据构造、影响面分析）始终走一键路径
        # - 文档分析型模式（测试方案、流程图、需求分析、测试点）仅当纯文本输入时走一键路径
        #   当有 PDF 文件上传时，必须走两步模式以确保文件内容被完整提取
        always_onekey_modes = ["log_diagnosis", "test_data", "impact_analysis", "api_test_gen", "api_perf_test_gen", "auto_script_gen"]
        text_onekey_modes = ["test_plan", "flowchart", "req_analysis", "test_point"]
        is_onekey = review_mode in always_onekey_modes or (review_mode in text_onekey_modes and not uploaded_file)
        if is_onekey:
            if st.button(button_text, type="primary", use_container_width=True):
                with st.status(spinner_text, expanded=True) as status:
                    def status_update(msg):
                        status.update(label=msg)
                        st.write(msg)
                    
                    try:
                        # 构造临时 preparsed_data
                        temp_parsed = {
                            "modules": [{"name": "全文", "pages": [], "description": "分析完整内容"}],
                            "context": {
                                "combined_text": "",
                                "vision_files_map": {},
                                "pages": [],
                                "file_basename": uploaded_file.name if uploaded_file else "Input",
                                "requirement": final_req
                            },
                            "v2_file_path": st.session_state.get('file_v2') # 仅 impact_analysis 用
                        }
                        result = review_service.run_review(
                            mode=review_mode,
                            preparsed_data=temp_parsed,
                            status_callback=status_update,
                            file_path=final_path,
                            extra_prompt=extra_prompt
                        )
                        
                        if result:
                            st.session_state['review_result'] = result
                            st.session_state['result_title'] = result_title
                            st.session_state['review_mode'] = review_mode
                            st.rerun()
                    except Exception as e:
                        st.error(f"执行失败: {e}")
        elif review_mode == "weekly_report":
            if st.button(button_text, type="primary", use_container_width=True):
                # 收集图片路径
                image_paths = []
                if file_path_to_process:
                    image_paths.append(file_path_to_process)
                
                with st.status(spinner_text, expanded=True) as status:
                    try:
                        status.update(label="🤖 正在获取 Dify 总结内容...")
                        summary = weekly_report_service.summarize_report(final_req, image_paths)
                        if summary:
                            status.update(label="🚀 正在同步至飞书文档...")
                            # 提取标题
                            title = f"【周报】测试团队 - {datetime.date.today().strftime('%Y-%m-%d')}"
                            for line in summary.split('\n'):
                                if line.startswith('# '):
                                    title = line[2:].strip()
                                    break
                            
                            feishu_url = weekly_report_service.export_to_feishu(title, summary)
                            if feishu_url:
                                status.update(label="✅ 周报已发布至飞书！", state="complete")
                                st.session_state['review_result'] = summary
                                st.session_state['feishu_url'] = feishu_url
                                st.session_state['result_title'] = result_title
                                st.session_state['review_mode'] = review_mode
                                st.rerun()
                            else:
                                st.error("❌ 导出飞书失败，请检查配置或网络。")
                        else:
                            st.error("❌ AI 总结失败，请检查 Dify 接口。")
                    except Exception as e:
                        st.error(f"❌ 执行异常: {e}")
        else:
            if st.button("🔍 解析目录结构（第一步）", use_container_width=True):
                with st.spinner("正在分析文档结构与功能模块..."):
                    try:
                        parse_res = {}
                        if final_path:
                            # 1. 提取文档内容
                            combined_text, vision_files_map, pages = document_service.process_file(final_path, max_pages=0)
                            
                            # 组合给 parse_requirement 的上下文
                            req_context = {
                                "combined_text": combined_text,
                                "vision_files_map": vision_files_map,
                                "pages": pages,
                                "file_basename": os.path.basename(final_path),
                                "requirement": final_req
                            }
                            # 2. 调用 review_service 识别模块
                            modules = review_service._identify_modules(combined_text, os.path.basename(final_path))
                            parse_res = {"modules": modules or [{"name": "全文", "pages": [], "description": "完整需求文档"}], "context": req_context}
                        else:
                            modules = review_service._identify_modules(final_req, "Input")
                            parse_res = {"modules": modules or [{"name": "全文", "pages": [], "description": "完整需求文档"}], "context": {"combined_text": "", "requirement": final_req}}
                            
                        if "error" in parse_res:
                            st.error(f"解析失败: {parse_res['error']}")
                        else:
                            st.session_state['parsed_data'] = parse_res
                            st.session_state['last_input_hash'] = current_input_hash
                            st.rerun()
                    except Exception as e:
                        st.error(f"解析异常: {e}")

# 步骤 2: 确认与生成
if 'parsed_data' in st.session_state:
    st.info("✅ 目录解析完成，请确认需要评审的模块：")
    
    # 使用 Data Editor 让用户编辑模块
    modules = st.session_state['parsed_data']['modules']
    
    # 转换为适合编辑的格式
    module_list_for_edit = [
        {"启用": True, "模块名称": m['name'], "描述": m['description'], "页码": str(m.get('pages', []))} 
        for m in modules
    ]
    
    edited_df = st.data_editor(
        module_list_for_edit, 
        column_config={
            "启用": st.column_config.CheckboxColumn("启用", help="是否评审此模块", default=True),
            "模块名称": st.column_config.TextColumn("模块名称", width="medium"),
            "描述": st.column_config.TextColumn("功能描述", width="large"),
            "页码": st.column_config.TextColumn("页码范围", disabled=True)
        },
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic"
    )
    
    # 重新组装选中的模块
    confirmed_modules = []
    for idx, row in enumerate(edited_df):
        if row.get("启用", True):
            # 尝试找回原始页码，如果是新增行则为空
            original_pages = []
            if idx < len(modules):
                original_pages = modules[idx]['pages']
            
            confirmed_modules.append({
                "name": row["模块名称"],
                "description": row["描述"],
                "pages": original_pages # 新增模块无法自动关联页码，但这不影响纯文本理解
            })
            
    if not confirmed_modules:
        st.warning("⚠️ 请至少启用一个模块")
    
    # 生成按钮
    if st.button(button_text, type="primary", use_container_width=True, disabled=not confirmed_modules):
        # 更新 parsed_data 中的 modules
        st.session_state['parsed_data']['modules'] = confirmed_modules
        
        # 使用 st.status 替代 st.spinner，支持实时日志
        with st.status(spinner_text, expanded=True) as status:
            progress_bar = st.progress(0, text="准备中...")
            total_mods = len(confirmed_modules)
            
            def status_update(msg):
                status.update(label=msg)
                st.write(msg)
                # 解析“[3/10]”格式更新进度条
                import re as _re
                m = _re.search(r'\[(\d+)/(\d+)\]', msg)
                if m:
                    cur, tot = int(m.group(1)), int(m.group(2))
                    pct = min(cur / max(tot, 1), 1.0)
                    progress_bar.progress(pct, text=f"模块 {cur}/{tot}")
            
            try:
                # 影响面分析：自动注入 v2 路径
                pre_data = st.session_state['parsed_data']
                if review_mode == "impact_analysis":
                    pre_data["v2_file_path"] = st.session_state.get('file_v2')

                result = review_service.run_review(
                    mode=review_mode,
                    roles=selected_roles,
                    preparsed_data=pre_data,
                    status_callback=status_update,
                    extra_prompt=extra_prompt
                )
                
                status.update(label=success_text, state="complete", expanded=False)
                
                if result:
                    st.session_state['review_result'] = result
                    st.session_state['result_title'] = result_title
                    st.session_state['download_name'] = download_name
                    st.session_state['review_mode'] = review_mode
                    st.session_state['case_template'] = case_template
                    
                    # 测试用例模式：解析 JSON 并导出文件
                    if review_mode == "test_case":
                        all_cases = parse_test_cases_from_text(result)
                        if all_cases:
                            # 提取原始文件名（去掉后缀），作为导出测试用例的前缀名
                            raw_name = "测试用例"
                            if file_path_to_process:
                                raw_name = os.path.splitext(os.path.basename(file_path_to_process))[0]
                            elif final_req and len(final_req) > 5:
                                # 如果是纯文本需求，取前 10 个字当名字
                                raw_name = final_req.split('\n')[0][:10].strip() or "测试用例"
                                
                            export_dir = tempfile.mkdtemp()
                            if case_template == "excel":
                                export_path = os.path.join(export_dir, f"{raw_name}_测试用例.xlsx")
                                export_to_excel(all_cases, export_path)
                            else:
                                export_path = os.path.join(export_dir, f"{raw_name}_测试用例.xmind")
                                export_to_xmind(all_cases, export_path)
                            st.session_state['export_file'] = export_path
                            st.session_state['case_count'] = len(all_cases)
                            st.success(f"✅ 已成功使用「{raw_name}」为名称导出 {len(all_cases)} 条测试用例！")
                        else:
                            st.warning("⚠️ 用例生成完成，但未能解析为结构化数据。可下载原始文本。")
                            st.success(success_text)
                    else:
                        st.success(success_text)
                    
                    # 自动保存到历史记录
                    try:
                        save_name = (uploaded_file.name if uploaded_file else "TAPD_Req")
                        history_manager.save_report(
                            content=result,
                            filename=save_name,
                            report_type=review_mode
                        )
                    except Exception as e:
                        st.warning(f"⚠️ 自动保存失败: {e}")
                        
                else:
                    st.error("❌ 处理失败，请查看日志。")
            except Exception as e:
                st.error(f"❌ 错误：{e}")
            finally:
                if final_path and os.path.exists(final_path):
                    os.remove(final_path)

# Fallback specifically for empty state (no file, no tapd) to show logic
elif not file_path_to_process and not final_req:
     if st.button("🚀 使用示例需求演示", use_container_width=True):
        st.session_state['tapd_req'] = """
        【需求标题】用户活动报名功能（示例）
        1. 用户点击报名，扣除积分 50 分。
        2. 未登录跳转登录页。
        """
        st.rerun()

# ============================================================
# 显示评审结果
# ============================================================
if 'review_result' in st.session_state:
    st.markdown("---")
    
    col_title, col_clear = st.columns([4, 1])
    with col_title:
        st.markdown(f"## {st.session_state.get('result_title', '📝 评审报告')}")
    with col_clear:
        if st.button("🗑️ 清除结果"):
            if 'pasted_content' in st.session_state:
                del st.session_state['pasted_content']
            del st.session_state['review_result']
            st.rerun()
    
    result_text = st.session_state['review_result']
    
    # 针对不同模式的渲染优化
    cur_mode = st.session_state.get('review_mode', 'review')
    
    if cur_mode == "log_diagnosis":
        # 如果是日志诊断，分栏显示
        c1, c2 = st.columns([1, 1.5])
        with c1:
            st.markdown("🔍 **原始日志片段**")
            st.code(st.session_state.get('pasted_content', "暂无记录").strip(), language="text", line_numbers=True)
            st.info("💡 建议：分析完成后，可根据下方方案在 IDE 中修复代码。")
        with c2:
            st.markdown("🧠 **AI 诊断方案**")
            st.markdown(result_text, unsafe_allow_html=True)
            if st.button("📝 一键生成 TAPD 缺陷描述"):
                st.toast("已根据诊断结果提取摘要，前往 TAPD 粘贴即可")
                st.session_state['tapd_bug_body'] = f"【缺陷来源】日志诊断\n【根本原因】{result_text[:200]}..."
    
    elif cur_mode == "test_data":
        st.markdown("### 🏗️ 构造结果")
        if "```" in result_text:
             st.markdown(result_text, unsafe_allow_html=True)
        else:
             st.code(result_text, language="python")
        st.success("✅ 脚本已生成！您可以将其复制到本地 Python 环境运行。")
    
    elif cur_mode == "test_plan":
        st.markdown("### 📅 标准测试方案")
        st.markdown(result_text, unsafe_allow_html=True)
        st.info("💡 建议：您可以基于此方案进一步细化 TDD 或自动化回归策略。")
        
    elif cur_mode == "flowchart":
        st.markdown("### 📊 业务流程导图")
        
        import re
        import base64
        import streamlit.components.v1 as components
        
        def _sanitize_mermaid(code: str) -> str:
            """清洗 Mermaid 代码，修复 AI 生成的常见语法兼容性问题。"""
            lines = code.split("\n")
            cleaned = []
            for line in lines:
                # 1. 去除 classDef 行内的 %% 注释（Mermaid v10 不支持行内注释）
                if line.strip().startswith("classDef"):
                    line = re.sub(r'\s+%%.*$', '', line)
                # 2. 将独立的 %% 注释行保留（这些通常没问题，但以防万一也去掉）
                elif line.strip().startswith("%%"):
                    continue
                # 3. 将 [/"..."/] 斜杠语法转为 ["..."] 矩形
                line = re.sub(r'\[/"([^"]*?)"/\]', r'["\1"]', line)
                # 4. 将 {/"..."/} 斜杠语法转为 {"..."} 菱形（或矩形）
                line = re.sub(r'\{/"([^"]*?)"/\}', r'["\1"]', line)
                cleaned.append(line)
            return "\n".join(cleaned)
        
        # 提取所有 Mermaid 代码块及其前面的标题
        sections = re.split(r'(###\s+[^\n]+)', result_text)
        
        mermaid_items = []  # [(标题, 代码), ...]
        current_title = ""
        
        for part in sections:
            part = part.strip()
            if not part:
                continue
            if part.startswith("### "):
                current_title = part.lstrip("#").strip()
            else:
                blocks = re.findall(r'```mermaid\s*\n(.*?)```', part, re.DOTALL)
                for block in blocks:
                    code = block.strip()
                    if code:
                        mermaid_items.append((current_title, code))
                        current_title = ""
        
        # 如果没有 ``` 包裹，尝试直接提取
        if not mermaid_items:
            if "graph " in result_text or "flowchart " in result_text:
                lines = result_text.strip().split("\n")
                capture = False
                captured_lines = []
                for line in lines:
                    if line.strip().startswith(("graph ", "flowchart ")):
                        capture = True
                    if capture:
                        if line.strip().startswith("#") and captured_lines:
                            break
                        captured_lines.append(line)
                code = "\n".join(captured_lines).strip()
                if code:
                    mermaid_items.append(("", code))
        
        if mermaid_items:
            # 初始化 session_state 中的可编辑代码
            if 'mermaid_edit_codes' not in st.session_state:
                st.session_state['mermaid_edit_codes'] = {i: code for i, (_, code) in enumerate(mermaid_items)}
            
            for idx, (title, original_code) in enumerate(mermaid_items):
                if title:
                    st.markdown(f"#### {title}")
                
                # 使用 session_state 中的代码（可能已被用户编辑过）
                current_code = st.session_state.get('mermaid_edit_codes', {}).get(idx, original_code)
                
                # 清洗 Mermaid 代码，修复常见的 AI 生成语法问题
                current_code = _sanitize_mermaid(current_code)
                
                code_b64 = base64.b64encode(current_code.encode('utf-8')).decode('ascii')
                chart_filename = f"flowchart_{title or f'module_{idx+1}'}"
                
                mermaid_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
                    <style>
                        body {{ margin: 0; padding: 0; background: #fff; font-family: sans-serif; }}
                        #output {{ padding: 16px; display: flex; justify-content: center; position: relative; }}
                        #output svg {{ max-width: 100%; height: auto; }}
                        .toolbar {{
                            position: absolute; top: 8px; right: 8px; display: flex; gap: 6px; z-index: 10;
                        }}
                        .toolbar button {{
                            padding: 6px 14px; border: 1px solid #ddd; border-radius: 6px;
                            background: #f8f9fa; cursor: pointer; font-size: 13px;
                            transition: all 0.2s;
                        }}
                        .toolbar button:hover {{ background: #e3e8ef; border-color: #aab; }}
                        .toolbar button.primary {{ background: #4361ee; color: #fff; border-color: #4361ee; }}
                        .toolbar button.primary:hover {{ background: #3a56d4; }}
                        .err {{ color: #c62828; padding: 12px; background: #ffebee;
                                border-radius: 8px; margin: 8px; font-size: 13px; }}
                        .err pre {{ white-space: pre-wrap; word-break: break-all; margin: 8px 0 0; }}
                    </style>
                </head>
                <body>
                    <div id="output">正在渲染...</div>
                    <script>
                        const code = decodeURIComponent(escape(atob("{code_b64}")));
                        const filename = "{chart_filename}";
                        
                        mermaid.initialize({{
                            startOnLoad: false, theme: 'default',
                            flowchart: {{ useMaxWidth: true, htmlLabels: true, curve: 'basis' }},
                            securityLevel: 'loose'
                        }});
                        
                        mermaid.render('g{idx}', code)
                            .then(({{ svg }}) => {{
                                // 渲染 SVG
                                const container = document.getElementById('output');
                                container.innerHTML = svg;
                                
                                // 添加工具栏
                                const toolbar = document.createElement('div');
                                toolbar.className = 'toolbar';
                                toolbar.innerHTML = `
                                    <button onclick="downloadSVG()" title="导出矢量图">📥 SVG</button>
                                    <button class="primary" onclick="downloadPNG()" title="导出高清图片">🖼️ PNG</button>
                                `;
                                container.appendChild(toolbar);
                                
                                // 自适应高度
                                const h = container.scrollHeight + 20;
                                window.parent.postMessage({{ type: 'streamlit:setFrameHeight', height: h }}, '*');
                            }})
                            .catch((err) => {{
                                document.getElementById('output').innerHTML =
                                    '<div class="err"><strong>⚠️ 渲染失败</strong>' +
                                    '<pre>' + err.message + '</pre></div>';
                            }});
                        
                        // 下载 SVG
                        function downloadSVG() {{
                            const svg = document.querySelector('#output svg');
                            if (!svg) return;
                            const svgData = new XMLSerializer().serializeToString(svg);
                            const blob = new Blob([svgData], {{ type: 'image/svg+xml;charset=utf-8' }});
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url; a.download = filename + '.svg'; a.click();
                            URL.revokeObjectURL(url);
                        }}
                        
                        // 下载 PNG（高清 2x）
                        function downloadPNG() {{
                            const svg = document.querySelector('#output svg');
                            if (!svg) return;
                            const svgData = new XMLSerializer().serializeToString(svg);
                            const canvas = document.createElement('canvas');
                            const ctx = canvas.getContext('2d');
                            const img = new Image();
                            const scale = 2;  // 2倍高清
                            
                            img.onload = function() {{
                                canvas.width = img.width * scale;
                                canvas.height = img.height * scale;
                                ctx.fillStyle = '#ffffff';
                                ctx.fillRect(0, 0, canvas.width, canvas.height);
                                ctx.scale(scale, scale);
                                ctx.drawImage(img, 0, 0);
                                const a = document.createElement('a');
                                a.href = canvas.toDataURL('image/png');
                                a.download = filename + '.png';
                                a.click();
                            }};
                            img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
                        }}
                    </script>
                </body>
                </html>
                """
                components.html(mermaid_html, height=500, scrolling=True)
            
            # ===== 在线编辑区 =====
            st.markdown("---")
            with st.expander("✏️ 编辑 Mermaid 代码（修改后点击重新渲染）", expanded=False):
                for idx, (title, original_code) in enumerate(mermaid_items):
                    label = title if title else f"模块 {idx + 1}"
                    current_code = st.session_state.get('mermaid_edit_codes', {}).get(idx, original_code)
                    edited = st.text_area(
                        f"📝 {label}",
                        value=current_code,
                        height=250,
                        key=f"mermaid_editor_{idx}"
                    )
                    # 保存编辑后的代码
                    if 'mermaid_edit_codes' not in st.session_state:
                        st.session_state['mermaid_edit_codes'] = {}
                    st.session_state['mermaid_edit_codes'][idx] = edited
                
                if st.button("🔄 重新渲染", type="primary", use_container_width=True):
                    st.rerun()
        else:
            st.markdown(result_text, unsafe_allow_html=True)
        
        st.info("💡 点击图表右上角的 **PNG** / **SVG** 按钮可直接导出图片；展开下方编辑区可修改代码后重新渲染。")
        
    elif cur_mode == "req_analysis":
        st.markdown("### 🔬 需求结构化分析")
        st.markdown(result_text, unsafe_allow_html=True)
        st.info("💡 建议：此分析可作为测试用例设计和测试点提取的输入基础。")
        
    elif cur_mode == "test_point":
        st.markdown("### 🎯 全维度测试点分析")
        st.markdown(result_text, unsafe_allow_html=True)
        st.info("💡 建议：可基于这些测试点直接切换到「生成测试用例」模式，生成可执行的用例。")
        
    elif cur_mode == "test_case":
        st.markdown("### 🧪 生成测试用例")
        # 尝试解析用例为表格
        from test_platform.core.data_generators.test_case_exporter import parse_test_cases_from_text
        import pandas as pd
        
        all_cases = parse_test_cases_from_text(result_text)
        
        if all_cases:
            # 格式化列表为展示表格
            df_cases = pd.DataFrame(all_cases)
            
            # 美化列名展示
            display_columns = {}
            if "module" in df_cases.columns: display_columns["module"] = "所属模块"
            if "name" in df_cases.columns: display_columns["name"] = "用例名称"
            if "tags" in df_cases.columns: display_columns["tags"] = "标签属性"
            if "priority" in df_cases.columns: display_columns["priority"] = "优先级"
            if "precondition" in df_cases.columns: display_columns["precondition"] = "前置条件"
            if "steps" in df_cases.columns: display_columns["steps"] = "操作步骤与预期"
            if "expected" in df_cases.columns: display_columns["expected"] = "最终预期结果"
            if "remark" in df_cases.columns: display_columns["remark"] = "备注"
                
            # 针对步骤列做文字紧凑化展现
            if "steps" in df_cases.columns:
                def format_steps(steps_val):
                    if isinstance(steps_val, list):
                        formatted = []
                        for i, s in enumerate(steps_val):
                            step_desc = s.get("step", "")
                            exp_desc = s.get("expected", "")
                            if exp_desc:
                                formatted.append(f"{i+1}. {step_desc} -> {exp_desc}")
                            else:
                                formatted.append(f"{i+1}. {step_desc}")
                        return "\\n".join(formatted)
                    return str(steps_val)
                df_cases["steps"] = df_cases["steps"].apply(format_steps)
            
            df_cases = df_cases.rename(columns=display_columns)
            
            st.success(f"✅ 成功解析 {len(all_cases)} 条测试用例，可在此直接预览或点击左侧下载。")
            st.dataframe(
                df_cases,
                use_container_width=True,
                height=400,
                hide_index=True
            )
            
            with st.expander("🛠️ 查看解析出的底层字典数据", expanded=False):
                st.json(all_cases)
            with st.expander("📜 查看原生生成的 XMind 层级 Markdown", expanded=True):
                st.markdown(result_text, unsafe_allow_html=True)
        else:
            # Fallback：没能解析出标准结构，直接用 markdown + 代码块包裹（或者直显），但避免长串。
            st.warning("⚠️ 探测到纯文本结构，未能表格化解析。原生文本直接见下：")
            st.markdown(result_text, unsafe_allow_html=True)
        
    else:
        # 默认评审/用例模式：按模块分段渲染
        try:
            sections = [s for s in result_text.split("\n\n---\n\n") if s.strip()]
            
            # 尝试解析是否为多角色 JSON 结果
            is_json_result = False
            if result_text.strip().startswith("{") and result_text.strip().endswith("}"):
                try:
                    role_results = json.loads(result_text)
                    is_json_result = True
                    tabs = st.tabs([r['label'] for r in role_results.values()])
                    for tab, r_data in zip(tabs, role_results.values()):
                        with tab:
                            st.markdown(r_data['content'], unsafe_allow_html=True)
                except Exception:
                    pass
            
            if not is_json_result:
                if len(sections) <= 1:
                    st.markdown(result_text, unsafe_allow_html=True)
                else:
                    tab_names = []
                    tab_bodies = []
                    for section in sections:
                        lines = section.split("\n", 1)
                        title = lines[0].strip().lstrip("#").strip() if lines else "内容"
                        body = lines[1] if len(lines) > 1 else section
                        if section.startswith("# ") and "模块" not in section:
                            st.markdown(lines[0])
                        else:
                            tab_names.append(f"📦 {title[:20]}")
                            tab_bodies.append(body)
                    
                    if tab_names:
                        tabs = st.tabs(tab_names)
                        for tab, body in zip(tabs, tab_bodies):
                            with tab:
                                st.markdown(body, unsafe_allow_html=True)
        except Exception as e:
            st.warning(f"渲染异常，降级为纯文本显示: {e}")
            st.text(result_text)
    
    # ===== 下载区域 =====
    st.markdown("---")
    if st.session_state.get('review_mode') == 'test_case' and 'export_file' in st.session_state:
        export_path = st.session_state['export_file']
        if os.path.exists(export_path):
            file_ext = os.path.splitext(export_path)[1]
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if file_ext == ".xlsx" else "application/octet-stream"
            label = f"📥 下载测试用例（{file_ext.upper().strip('.')} 格式，{st.session_state.get('case_count', 0)} 条）"
            
            with open(export_path, 'rb') as f:
                st.download_button(
                    label=label,
                    data=f.read(),
                    file_name=os.path.basename(export_path),
                    mime=mime_type,
                    use_container_width=True
                )
    else:
        st.download_button(
            label="📥 下载完整报告（Markdown）",
            data=result_text,
            file_name=st.session_state.get('download_name', '需求评审报告.md'),
            mime="text/markdown",
            use_container_width=True
        )
    
    # ===== 智能引导：建议下一步操作 =====
    cur_mode = st.session_state.get('review_mode', 'review')
    next_step_map = {
        "review": ("req_analysis", "🔬 深度解析需求结构", "想更细致地拆解需求？"),
        "req_analysis": ("test_point", "🎯 提取测试点", "需求分析完成，提取全维度测试点？"),
        "test_point": ("test_case", "🧪 生成测试用例", "测试点提取完成，生成可执行用例？"),
        "test_case": ("test_plan", "📅 制定测试方案", "用例就绪，要制定完整测试方案吗？"),
        "flowchart": ("test_point", "🎯 提取测试点", "流程图已梳理，按此提取测试点？"),
        "test_plan": ("test_case", "🧪 生成测试用例", "方案已出，一键生成用例？"),
    }
    
    if cur_mode in next_step_map:
        next_mode, next_label, next_hint = next_step_map[cur_mode]
        st.markdown("")
        cols_guide = st.columns([3, 1])
        with cols_guide[0]:
            st.caption(f"💡 {next_hint}")
        with cols_guide[1]:
            if st.button(next_label, key="next_step_btn"):
                # 切换模式但保留已解析数据
                st.session_state['_last_review_mode'] = next_mode
                st.session_state['curr_review_mode'] = next_mode
                for key in ['review_result', 'result_title', 'mermaid_edit_codes', 'feishu_url']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()
    
    # ===== 飞书链接展示 =====
    if st.session_state.get('feishu_url'):
        st.success(f"🔗 **飞书文档已生成**：[{st.session_state['feishu_url']}]({st.session_state['feishu_url']})")
        st.info("💡 文档已自动开启公开阅读权限并添加协作者。")
    
    # ===== 结果对比视图 =====
    if 'compare_result' in st.session_state:
        st.markdown("---")
        st.markdown("### 📊 结果对比")
        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown(f"**当前结果** — {st.session_state.get('result_title', '')}")
            st.markdown(result_text[:3000] if len(result_text) > 3000 else result_text, unsafe_allow_html=True)
            if len(result_text) > 3000:
                st.caption("（展示前 3000 字，完整内容请下载）")
        with col_right:
            st.markdown(f"**对比结果** — {st.session_state.get('compare_title', '')}")
            compare_text = st.session_state['compare_result']
            st.markdown(compare_text[:3000] if len(compare_text) > 3000 else compare_text, unsafe_allow_html=True)
            if len(compare_text) > 3000:
                st.caption("（展示前 3000 字，完整内容请下载）")
        if st.button("🗑️ 清除对比", key="clear_compare"):
            del st.session_state['compare_result']
            if 'compare_title' in st.session_state:
                del st.session_state['compare_title']
            st.rerun()
