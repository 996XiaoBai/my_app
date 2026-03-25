import streamlit as st
import os
import sys
from dotenv import load_dotenv

# 确保项目根目录在导入路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from test_platform.services.dify_client import DifyClient
from test_platform.infrastructure.tapd_client import TAPDClient
from test_platform.config import (
    get_test_platform_dify_api_base,
    get_test_platform_dify_api_key,
    get_test_platform_dify_user_id,
)


def get_dify_client():
    load_dotenv()
    api_base = get_test_platform_dify_api_base()
    api_key = get_test_platform_dify_api_key()
    user_id = get_test_platform_dify_user_id("bug_reporter_ui")

    if not api_base or not api_key:
        st.error("请在 .env 文件中配置 DIFY_API_BASE 和 TEST_PLATFORM_DIFY_API_KEY（或回退使用 DIFY_API_KEY）")
        return None

    return DifyClient(api_base, api_key, user_id)


import json
import datetime


def generate_report_data(client, user_input, version, submitter, attached_files):
    current_date = datetime.date.today().strftime("%m月%d日")

    # 格式化附件信息，补充进提示词
    files_str = ", ".join([f.name for f in attached_files]) if attached_files else "无"

    prompt = f"""
你是一个专业的 QA 测试工程师。请将用户提供的 Bug 描述转换为标准的 TAPD JSON 格式。

**用户描述**:
{user_input}

**输出要求**:
1. 仅输出 JSON，不要包含 Markdown 标记。
2. **标题 (title)** 格式严格执行：【模块名】+ 简短操作 + 实际结果 (例如：【用户中心】修改头像后，页面弹出 500 错误)
3. **描述 (description)** 格式采用 HTML (用于 TAPD 富文本)，包含以下红色加粗标题：
   * 前置条件：
   * 重现步骤：
   * 预期结果：
   * 实际结果：
   * 截图或其他补充材料

**JSON 结构**:
{{
    "title": "标题内容",
    "description": "HTML 格式的描述内容",
    "module": "所属模块(如登录,首页,播放页)",
    "severity": "致命/严重/一般/轻微",
    "priority": "P0 (紧急)/P1 (高)/P2 (中)/P3 (低)",
    "handler": "处理人姓名(推断或留空)",
    "developer": "开发人员姓名(推断或留空)",
    "discovery_phase": "环境/开发/测试",
    "tester": "创建人"
}}
"""
    response = client.generate_completion(prompt)
    if not response:
        return None

    # 清理模型可能返回的 Markdown 包裹
    clean_json = response.strip()
    if clean_json.startswith("```json"):
        clean_json = clean_json[7:]
    if clean_json.endswith("```"):
        clean_json = clean_json[:-3]

    try:
        data = json.loads(clean_json.strip())
        # 注入上下文字段
        data['version'] = version
        data['submitter'] = submitter
        data['submit_time'] = current_date

        # 附件字段兜底补齐
        if attached_files and (not data.get('attachments') or data.get('attachments') == "无"):
            data['attachments'] = files_str

        return data
    except json.JSONDecodeError:
        return {"error": "JSON解析失败", "raw": response}


# Streamlit 界面
st.set_page_config(page_title="AI Bug Report Generator", page_icon="🐞", layout="wide")

st.title("🐞 智能缺陷报告生成器")
st.markdown("输入口语化的 Bug 描述，自动生成标准的测试报告（支持 Excel 粘贴格式）。")

# 调试侧边栏
with st.sidebar:
    st.header("设置与诊断")
    show_debug = st.checkbox("显示调试信息 (Debug Mode)")
    if st.button("测试 API 连接"):
        load_dotenv()
        base = os.getenv("DIFY_API_BASE")
        if base:
            st.info(f"API Base: {base}")
            try:
                # 基础连通性检查
                import requests

                r = requests.get(base, timeout=5)
                st.write(f"Status Code: {r.status_code}")
                st.success("网络连接正常")
            except Exception as e:
                st.error(f"连接失败: {e}")
        else:
            st.error("未找到 DIFY_API_BASE 配置")

    st.divider()
    st.header("TAPD 配置")
    tapd_workspace_id = st.text_input("Workspace ID", value=os.getenv("TAPD_WORKSPACE_ID", ""))
    tapd_api_user = st.text_input("API User", value=os.getenv("TAPD_API_USER", ""))
    tapd_api_password = st.text_input("API Password", value=os.getenv("TAPD_API_PASSWORD", ""), type="password")

    if st.button("保存配置到 .env (临时模拟)"):
        st.info("配置已在当前会话生效")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        app_version = st.text_input("版本/迭代", value="V1.0.0")
    with col2:
        submitter = st.text_input("提交人", value="林康保")

    user_input = st.text_area("Bug 描述", height=150,
                              placeholder="例如：在登录页面输入错误密码后，点击登录按钮，页面没有提示错误信息，而是直接卡死...")

    # 文件上传
    uploaded_files = st.file_uploader("添加截图/日志 (可选)", accept_multiple_files=True,
                                      type=['png', 'jpg', 'jpeg', 'log', 'txt'])

    if st.button("生成报告 (Generate)", type="primary"):
        if not user_input.strip():
            st.warning("请输入描述信息。")
        else:
            client = get_dify_client()
            if client:
                status_box = st.empty()
                with st.spinner("AI 正在思考并整理报告 (超时限制 60s)..."):
                    if show_debug:
                        status_box.info(f"正在请求: {client.api_base}...")

                    data = generate_report_data(client, user_input, app_version, submitter, uploaded_files)

                if data and "error" not in data:
                    status_box.empty()
                    st.success("AI 生成结构化数据完成，请在下方确认/修改：")
                    
                    # 模拟 TAPD 布局
                    st.divider()
                    
                    # 使用 Session State 保存生成的数据，方便用户修改
                    if 'bug_data' not in st.session_state or st.session_state.get('last_input') != user_input:
                        st.session_state['bug_data'] = data
                        st.session_state['last_input'] = user_input

                    curr_data = st.session_state['bug_data']

                    # 双栏布局
                    col_main, col_side = st.columns([3, 1])

                    with col_main:
                        st.markdown("### 📝 缺陷详情")
                        new_title = st.text_input("标题 (Title)", value=curr_data.get('title', ''), 
                                                 placeholder="【模块名】+ 简短操作 + 实际结果")
                        
                        # TAPD 区块模拟：前置条件、重现步骤等
                        new_description = st.text_area("详细描述 (Description)", 
                                                      value=curr_data.get('description', ''), 
                                                      height=300)
                        
                        st.markdown("**附件预览**：" + (", ".join([f.name for f in uploaded_files]) if uploaded_files else "无"))

                    with col_side:
                        st.markdown("### ⚙️ 核心属性")
                        new_handler = st.text_input("处理人", value=curr_data.get('handler', '处理开发'))
                        new_developer = st.text_input("开发人员", value=curr_data.get('developer', '开发人员'))
                        
                        all_priorities = ["P0 (紧急)", "P1 (高)", "P2 (中)", "P3 (低)"]
                        p_index = all_priorities.index(curr_data.get('priority')) if curr_data.get('priority') in all_priorities else 2
                        new_priority = st.selectbox("优先级", options=all_priorities, index=p_index)
                        
                        all_severities = ["致命", "严重", "一般", "轻微"]
                        s_index = all_severities.index(curr_data.get('severity')) if curr_data.get('severity') in all_severities else 2
                        new_severity = st.selectbox("严重程度", options=all_severities, index=s_index)
                        
                        new_phase = st.selectbox("发现阶段", options=["环境", "开发", "测试", "验收"], index=0)
                        new_tester = st.text_input("测试人员", value=submitter)
                        
                        new_module = st.text_input("所属模块", value=curr_data.get('module', ''))

                    # 更新 Session State
                    st.session_state['bug_data'].update({
                        "title": new_title,
                        "description": new_description,
                        "handler": new_handler,
                        "developer": new_developer,
                        "priority": new_priority,
                        "severity": new_severity,
                        "module": new_module
                    })

                    # 3. 同步到 TAPD
                    st.divider()
                    st.subheader("🚀 同步至 TAPD")
                    if not tapd_workspace_id or not tapd_api_user or not tapd_api_password:
                        st.warning("请在侧边栏完善 TAPD 配置后再提交。")
                    else:
                        if st.button("确认一键提单到 TAPD"):
                            with st.spinner("正在提交至 TAPD..."):
                                tapd = TAPDClient(tapd_api_user, tapd_api_password, tapd_workspace_id)
                                
                                success, result = tapd.create_bug(
                                    title=new_title,
                                    description=new_description.replace('\n', '<br/>'),
                                    priority=TAPDClient.map_priority(new_priority),
                                    severity=TAPDClient.map_severity(new_severity),
                                    reporter=new_tester,
                                    current_owner=new_handler,
                                    module=new_module
                                )
                                
                                if success:
                                    bug_url = tapd.get_bug_url(result)
                                    st.success(f"恭喜！Bug 已成功提交到 TAPD。")
                                    st.link_button("点击查看 TAPD 缺陷", bug_url)
                                    st.balloons()
                                else:
                                    st.error(f"提交失败: {result}")

                elif data and "error" in data:
                    st.error(f"解析失败: {data['error']}")
                    st.text(data['raw'])
                else:
                    st.error("生成失败，请检查网络或配置。")

with st.sidebar:
    st.header("关于")
    st.info("此工具使用 Dify (LLM) 将非结构化文本转换为标准 Bug 报告格式，适用于各类软件测试场景。")

if __name__ == "__main__":
    import sys
    from streamlit.web import cli as stcli
    
    # Simulate 'streamlit run file.py'
    # Use a try-except block to handle cases where Runtime might already exist
    # or if we are in a recursive execution context that isn't caught by env vars.
    sys.argv = ["streamlit", "run", __file__]
    try:
        sys.exit(stcli.main())
    except RuntimeError as e:
        # Streamlit throws "Runtime instance already exists" if we try to start it again
        # inside an existing session. This is expected during the recursive call.
        if "already exists" in str(e):
            pass
        else:
            raise e
    except SystemExit:
        pass
