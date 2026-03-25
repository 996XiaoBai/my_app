/**
 * Options 页面逻辑 - 配置管理
 */

// DOM 元素
const fields = {
    difyBase: document.getElementById('dify-base'),
    difyKey: document.getElementById('dify-key'),
    difyUser: document.getElementById('dify-user'),
    tapdWorkspace: document.getElementById('tapd-workspace'),
    tapdUser: document.getElementById('tapd-user'),
    tapdPassword: document.getElementById('tapd-password'),
    defaultSubmitter: document.getElementById('default-submitter'),
    defaultVersion: document.getElementById('default-version')
};

const statusEl = document.getElementById('status-message');
const btnSave = document.getElementById('btn-save');
const btnTest = document.getElementById('btn-test');

// ======== 初始化：加载已保存的配置 ========
document.addEventListener('DOMContentLoaded', () => {
    chrome.storage.local.get([
        'difyApiBase', 'difyApiKey', 'difyUserId',
        'tapdWorkspaceId', 'tapdApiUser', 'tapdApiPassword',
        'defaultSubmitter', 'defaultVersion'
    ], (config) => {
        fields.difyBase.value = config.difyApiBase || '';
        fields.difyKey.value = config.difyApiKey || '';
        fields.difyUser.value = config.difyUserId || '';
        fields.tapdWorkspace.value = config.tapdWorkspaceId || '';
        fields.tapdUser.value = config.tapdApiUser || '';
        fields.tapdPassword.value = config.tapdApiPassword || '';
        fields.defaultSubmitter.value = config.defaultSubmitter || '';
        fields.defaultVersion.value = config.defaultVersion || '';
    });
});

// ======== 保存配置 ========
btnSave.addEventListener('click', () => {
    const config = {
        difyApiBase: fields.difyBase.value.trim(),
        difyApiKey: fields.difyKey.value.trim(),
        difyUserId: fields.difyUser.value.trim(),
        tapdWorkspaceId: fields.tapdWorkspace.value.trim(),
        tapdApiUser: fields.tapdUser.value.trim(),
        tapdApiPassword: fields.tapdPassword.value.trim(),
        defaultSubmitter: fields.defaultSubmitter.value.trim(),
        defaultVersion: fields.defaultVersion.value.trim()
    };

    chrome.storage.local.set(config, () => {
        showStatus('✅ 设置已保存成功！', 'success');
    });
});

// ======== 测试连接 ========
btnTest.addEventListener('click', async () => {
    const difyBase = fields.difyBase.value.trim();
    const difyKey = fields.difyKey.value.trim();

    if (!difyBase || !difyKey) {
        showStatus('⚠️ 请先填写 Dify API 配置', 'error');
        return;
    }

    showStatus('🔄 正在测试 Dify API 连接...', 'info');

    try {
        // 发送一个简单的测试请求
        const response = await fetch(`${difyBase}/parameters`, {
            headers: {
                'Authorization': `Bearer ${difyKey}`
            }
        });

        if (response.ok) {
            showStatus('✅ Dify API 连接成功！', 'success');
        } else {
            showStatus(`❌ Dify API 连接失败 (状态码: ${response.status})`, 'error');
        }
    } catch (err) {
        showStatus(`❌ 网络错误: ${err.message}`, 'error');
    }
});

// ======== 显示状态消息 ========
function showStatus(message, type) {
    statusEl.textContent = message;
    statusEl.className = `status ${type}`;

    // 5秒后自动隐藏
    setTimeout(() => {
        statusEl.className = 'status hidden';
    }, 5000);
}
