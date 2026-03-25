/**
 * Service Worker - 智能缺陷报告生成器
 * 负责调用 Dify API 和 TAPD API
 */

// 优先级映射
const PRIORITY_MAP = {
  'P0 (紧急)': 'urgent',
  'P1 (高)': 'high',
  'P2 (中)': 'medium',
  'P3 (低)': 'low'
};

// 严重程度映射
const SEVERITY_MAP = {
  '致命': 'fatal',
  '严重': 'serious',
  '一般': 'normal',
  '轻微': 'slight'
};

/**
 * 调用 Dify Streaming API 生成 Bug 报告
 */
async function callDifyAPI(prompt, config) {
  const url = `${config.difyApiBase}/chat-messages`;
  const headers = {
    'Authorization': `Bearer ${config.difyApiKey}`,
    'Content-Type': 'application/json'
  };

  const payload = {
    inputs: {},
    query: prompt,
    response_mode: 'streaming',
    conversation_id: '',
    user: config.difyUserId || 'bug_reporter_chrome'
  };

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error(`Dify API 请求失败: ${response.status}`);
  }

  // 处理 SSE 流式响应
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let fullAnswer = '';
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    // 保留最后一行（可能不完整）
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.event === 'agent_message' || data.event === 'message') {
            fullAnswer += data.answer || '';
          } else if (data.event === 'error') {
            let errMsg = JSON.stringify(data);
            if (errMsg.includes('429') || errMsg.includes('RESOURCE_EXHAUSTED')) {
              throw new Error(`AI 服务当前请求过多已触发频率限制 (429 RESOURCE_EXHAUSTED)，请稍等一分钟后再试。`);
            }
            throw new Error(`Dify 流式错误: ${errMsg}`);
          }
        } catch (e) {
          if (e.message.startsWith('AI 服务') || e.message.startsWith('Dify')) throw e;
          // JSON 解析失败，跳过
        }
      }
    }
  }

  return fullAnswer.trim();
}

/**
 * 构建 Bug 生成 Prompt
 */
function buildPrompt(userInput) {
  return `
你是一个专业的 QA 测试工程师。请将用户提供的 Bug 描述转换为标准的 TAPD JSON 格式。

**用户描述**:
${userInput}

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
{
    "title": "标题内容",
    "description": "HTML 格式的描述内容",
    "module": "所属模块(如登录,首页,播放页)",
    "severity": "致命/严重/一般/轻微",
    "priority": "P0 (紧急)/P1 (高)/P2 (中)/P3 (低)",
    "handler": "处理人姓名(推断或留空)",
    "developer": "开发人员姓名(推断或留空)",
    "discovery_phase": "环境/开发/测试",
    "tester": "创建人"
}`;
}

/**
 * 调用 TAPD API 创建缺陷
 */
async function createTAPDBug(bugData, config) {
  const url = 'https://api.tapd.cn/bugs';
  // TAPD 使用 HTTP Basic Auth
  const auth = btoa(`${config.tapdApiUser}:${config.tapdApiPassword}`);

  const formData = new URLSearchParams();
  formData.append('workspace_id', config.tapdWorkspaceId);
  formData.append('title', bugData.title);
  formData.append('description', bugData.description.replace(/\n/g, '<br/>'));

  if (bugData.priority) formData.append('priority', PRIORITY_MAP[bugData.priority] || 'medium');
  if (bugData.severity) formData.append('severity', SEVERITY_MAP[bugData.severity] || 'normal');
  if (bugData.reporter) formData.append('reporter', bugData.reporter);
  if (bugData.current_owner) formData.append('current_owner', bugData.current_owner);
  if (bugData.module) formData.append('module', bugData.module);
  if (bugData.storyId) formData.append('related_story_id', bugData.storyId);

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Basic ${auth}`,
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: formData.toString()
  });

  const result = await response.json();

  if (response.ok && result.status === 1) {
    const bugId = result.data?.Bug?.id;
    return {
      success: true,
      bugId,
      url: `https://www.tapd.cn/${config.tapdWorkspaceId}/bugtrace/bugs/view?bug_id=${bugId}`
    };
  } else {
    throw new Error(result.info || '未知错误');
  }
}

/**
 * 上传附件到 TAPD (单个文件)
 */
async function uploadAttachment(fileData, bugId, config) {
  const url = 'https://api.tapd.cn/bugs/attachment';
  const auth = btoa(`${config.tapdApiUser}:${config.tapdApiPassword}`);

  // 将 base64 转为 Blob
  const byteChars = atob(fileData.base64);
  const byteArray = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) {
    byteArray[i] = byteChars.charCodeAt(i);
  }
  const blob = new Blob([byteArray], { type: fileData.type || 'application/octet-stream' });

  // 构建 multipart/form-data
  const formData = new FormData();
  formData.append('workspace_id', config.tapdWorkspaceId);
  formData.append('bug_id', bugId);
  formData.append('file', blob, fileData.name);

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Basic ${auth}`
    },
    body: formData
  });

  const result = await response.json();
  if (response.ok && result.status === 1) {
    return { success: true };
  } else {
    throw new Error(result.info || '附件上传失败');
  }
}

/**
 * 监听来自 popup 的消息
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'generateReport') {
    handleGenerateReport(request.userInput)
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // 表示异步响应
  }

  if (request.action === 'fetchStories') {
    handleFetchStories()
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === 'submitToTAPD') {
    handleSubmitToTAPD(request.bugData)
      .then(data => sendResponse({ success: true, data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (request.action === 'uploadAttachments') {
    handleUploadAttachments(request.bugId, request.files)
      .then(() => sendResponse({ success: true }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }
});

async function handleGenerateReport(userInput) {
  const config = await getConfig();
  if (!config.difyApiBase || !config.difyApiKey) {
    throw new Error('请先在设置页面配置 Dify API');
  }

  const prompt = buildPrompt(userInput);
  const response = await callDifyAPI(prompt, config);

  // 清理可能的 markdown 包裹
  let cleanJson = response;
  if (cleanJson.startsWith('```json')) cleanJson = cleanJson.slice(7);
  if (cleanJson.startsWith('```')) cleanJson = cleanJson.slice(3);
  if (cleanJson.endsWith('```')) cleanJson = cleanJson.slice(0, -3);

  return JSON.parse(cleanJson.trim());
}

async function handleSubmitToTAPD(bugData) {
  const config = await getConfig();
  if (!config.tapdWorkspaceId || !config.tapdApiUser || !config.tapdApiPassword) {
    throw new Error('请先在设置页面配置 TAPD API');
  }
  return await createTAPDBug(bugData, config);
}

/**
 * 获取 TAPD 需求列表
 */
async function handleFetchStories() {
  const config = await getConfig();
  if (!config.tapdWorkspaceId || !config.tapdApiUser || !config.tapdApiPassword) {
    throw new Error('请先在设置页面配置 TAPD API');
  }

  const url = `https://api.tapd.cn/stories?workspace_id=${config.tapdWorkspaceId}&status=open,progressing,developing,testing&limit=100`;
  const auth = btoa(`${config.tapdApiUser}:${config.tapdApiPassword}`);

  const response = await fetch(url, {
    headers: { 'Authorization': `Basic ${auth}` }
  });

  const result = await response.json();
  if (response.ok && result.status === 1) {
    return (result.data || []).map(item => ({
      id: item.Story.id,
      name: `[${item.Story.id}] ${item.Story.name}`
    }));
  } else {
    throw new Error(result.info || '获取需求列表失败');
  }
}

/**
 * 处理附件上传（逐个上传）
 */
async function handleUploadAttachments(bugId, files) {
  const config = await getConfig();
  if (!config.tapdWorkspaceId || !config.tapdApiUser || !config.tapdApiPassword) {
    throw new Error('请先在设置页面配置 TAPD API');
  }

  let successCount = 0;
  let failedFiles = [];

  for (const file of files) {
    try {
      await uploadAttachment(file, bugId, config);
      successCount++;
    } catch (err) {
      failedFiles.push(`${file.name}: ${err.message}`);
    }
  }

  if (failedFiles.length > 0) {
    throw new Error(`${successCount}个成功，${failedFiles.length}个失败: ${failedFiles.join('; ')}`);
  }
}

/**
 * 从 chrome.storage 获取配置
 */
function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get([
      'difyApiBase', 'difyApiKey', 'difyUserId',
      'tapdWorkspaceId', 'tapdApiUser', 'tapdApiPassword',
      'defaultSubmitter'
    ], resolve);
  });
}
