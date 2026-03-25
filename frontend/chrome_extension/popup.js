/**
 * Popup 主逻辑 - 智能缺陷报告生成器
 */

// DOM 元素引用
const elements = {
    // 阶段容器
    phaseInput: document.getElementById('phase-input'),
    phasePreview: document.getElementById('phase-preview'),
    phaseSuccess: document.getElementById('phase-success'),
    // 状态栏
    statusBar: document.getElementById('status-bar'),
    // 输入区
    version: document.getElementById('version'),
    submitter: document.getElementById('submitter'),
    bugInput: document.getElementById('bug-input'),
    btnGenerate: document.getElementById('btn-generate'),
    // 文件上传
    uploadArea: document.getElementById('upload-area'),
    fileInput: document.getElementById('file-input'),
    uploadPlaceholder: document.getElementById('upload-placeholder'),
    fileList: document.getElementById('file-list'),
    // 预览区
    bugTitle: document.getElementById('bug-title'),
    storySearch: document.getElementById('story-search'),
    bugStory: document.getElementById('bug-story'),
    btnRefreshStories: document.getElementById('btn-refresh-stories'),
    bugDescriptionPreview: document.getElementById('bug-description-preview'),
    bugDescription: document.getElementById('bug-description'),
    btnCopyDescription: document.getElementById('btn-copy-description'),
    btnToggleSource: document.getElementById('btn-toggle-source'),
    bugHandler: document.getElementById('bug-handler'),
    bugDeveloper: document.getElementById('bug-developer'),
    bugPriority: document.getElementById('bug-priority'),
    bugSeverity: document.getElementById('bug-severity'),
    bugPhase: document.getElementById('bug-phase'),
    bugModule: document.getElementById('bug-module'),
    btnSubmit: document.getElementById('btn-submit'),
    btnBack: document.getElementById('btn-back'),
    // 成功区
    successLink: document.getElementById('success-link'),
    btnNew: document.getElementById('btn-new'),
    // 按钮
    btnSettings: document.getElementById('btn-settings')
};

// 已选择的文件列表
let selectedFiles = [];
// 缓存的需求列表数据
let cachedStories = [];

// ======== 初始化 ========
document.addEventListener('DOMContentLoaded', () => {
    restoreState();
    bindEvents();
});

/**
 * 从 chrome.storage 恢复上次的状态
 */
function restoreState() {
    chrome.storage.local.get([
        'defaultSubmitter', 'defaultVersion',
        'popupState' // 保存的弹窗状态
    ], (config) => {
        // 加载默认值
        if (config.defaultSubmitter) elements.submitter.value = config.defaultSubmitter;
        if (config.defaultVersion) elements.version.value = config.defaultVersion;

        // 恢复上次的表单状态
        const state = config.popupState;
        if (state) {
            // 输入区
            if (state.bugInput) elements.bugInput.value = state.bugInput;
            if (state.version) elements.version.value = state.version;
            if (state.submitter) elements.submitter.value = state.submitter;

            // 如果上次在预览阶段，恢复预览数据
            if (state.phase === 'preview' && state.preview) {
                const p = state.preview;
                elements.bugTitle.value = p.title || '';
                elements.bugDescription.value = p.description || '';
                elements.bugDescriptionPreview.innerHTML = p.description || '';
                elements.bugDescriptionPreview.classList.remove('hidden');
                elements.bugDescription.classList.add('hidden');
                elements.bugHandler.value = p.handler || '';
                elements.bugDeveloper.value = p.developer || '';
                elements.bugModule.value = p.module || '';
                if (p.priority) elements.bugPriority.value = p.priority;
                if (p.severity) elements.bugSeverity.value = p.severity;
                if (p.phase) elements.bugPhase.value = p.phase;
                showPhase('preview', true); // true = 不触发保存
            }
        }
    });
}

/**
 * 绑定事件
 */
function bindEvents() {
    elements.btnGenerate.addEventListener('click', handleGenerate);
    elements.btnSubmit.addEventListener('click', handleSubmit);
    elements.btnBack.addEventListener('click', () => showPhase('input'));
    elements.btnNew.addEventListener('click', () => {
        elements.bugInput.value = '';
        selectedFiles = [];
        renderFileList();
        // 清除保存的状态
        chrome.storage.local.remove('popupState');
        showPhase('input');
    });
    elements.btnSettings.addEventListener('click', () => {
        chrome.runtime.openOptionsPage();
    });
    // 描述区：预览/源码切换
    elements.btnCopyDescription.addEventListener('click', handleCopyDescription);
    elements.btnToggleSource.addEventListener('click', toggleDescriptionMode);
    // 刷新需求列表
    elements.btnRefreshStories.addEventListener('click', () => loadStories(true));
    // 搜索过滤需求
    elements.storySearch.addEventListener('input', filterStories);
    // 记住上次选择
    elements.bugStory.addEventListener('change', () => {
        chrome.storage.local.set({ lastStoryId: elements.bugStory.value });
    });
    // 文件上传事件
    elements.uploadArea.addEventListener('click', () => elements.fileInput.click());
    elements.fileInput.addEventListener('change', (e) => {
        addFiles(e.target.files);
        e.target.value = ''; // 允许重复选择同一文件
    });
    // 拖拽事件
    elements.uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.uploadArea.classList.add('dragover');
    });
    elements.uploadArea.addEventListener('dragleave', () => {
        elements.uploadArea.classList.remove('dragover');
    });
    elements.uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.uploadArea.classList.remove('dragover');
        addFiles(e.dataTransfer.files);
    });
}

// ======== 阶段切换 ========
function showPhase(phase, skipSave = false) {
    elements.phaseInput.classList.toggle('hidden', phase !== 'input');
    elements.phasePreview.classList.toggle('hidden', phase !== 'preview');
    elements.phaseSuccess.classList.toggle('hidden', phase !== 'success');
    hideStatus();
    // 进入预览阶段时加载需求列表
    if (phase === 'preview') {
        loadStories();
    }
    // 保存当前阶段
    if (!skipSave) {
        saveFormState(phase);
    }
}

/**
 * 保存当前表单状态到 chrome.storage
 */
function saveFormState(phase) {
    const state = {
        phase: phase || 'input',
        bugInput: elements.bugInput.value,
        version: elements.version.value,
        submitter: elements.submitter.value
    };

    // 如果在预览阶段，保存预览数据
    if (phase === 'preview') {
        state.preview = {
            title: elements.bugTitle.value,
            description: elements.bugDescription.value,
            handler: elements.bugHandler.value,
            developer: elements.bugDeveloper.value,
            priority: elements.bugPriority.value,
            severity: elements.bugSeverity.value,
            phase: elements.bugPhase.value,
            module: elements.bugModule.value
        };
    }

    chrome.storage.local.set({ popupState: state });
}

// ======== 状态栏 ========
function showStatus(message, type = 'info') {
    elements.statusBar.textContent = message;
    elements.statusBar.className = `status-bar ${type}`;
}

function hideStatus() {
    elements.statusBar.className = 'status-bar hidden';
}

// ======== 按钮状态 ========
function setButtonLoading(btn, loading) {
    const textEl = btn.querySelector('.btn-text');
    const loadingEl = btn.querySelector('.btn-loading');
    if (loading) {
        textEl.classList.add('hidden');
        loadingEl.classList.remove('hidden');
        btn.disabled = true;
    } else {
        textEl.classList.remove('hidden');
        loadingEl.classList.add('hidden');
        btn.disabled = false;
    }
}

// ======== 生成报告 ========
async function handleGenerate() {
    const userInput = elements.bugInput.value.trim();
    if (!userInput) {
        showStatus('请输入 Bug 描述', 'error');
        return;
    }

    // 保存输入阶段的数据（防止关闭丢失）
    saveFormState('input');
    setButtonLoading(elements.btnGenerate, true);
    showStatus('🤖 AI 正在分析并生成报告...', 'info');

    try {
        const response = await chrome.runtime.sendMessage({
            action: 'generateReport',
            userInput: userInput
        });

        if (response.success) {
            populatePreview(response.data);
            showPhase('preview');
            showStatus('✅ AI 生成完成，请确认/修改后提交', 'success');
        } else {
            showStatus(`❌ 生成失败: ${response.error}`, 'error');
        }
    } catch (err) {
        showStatus(`❌ 通信错误: ${err.message}`, 'error');
    } finally {
        setButtonLoading(elements.btnGenerate, false);
    }
}

/**
 * 将 AI 返回的数据填充到预览表单
 */
function populatePreview(data) {
    elements.bugTitle.value = data.title || '';
    // 保存原始 HTML 到 textarea，渲染到预览 div
    elements.bugDescription.value = data.description || '';
    elements.bugDescriptionPreview.innerHTML = data.description || '';
    // 默认显示预览模式
    elements.bugDescriptionPreview.classList.remove('hidden');
    elements.bugDescription.classList.add('hidden');
    elements.btnToggleSource.textContent = '📝 编辑源码';

    elements.bugHandler.value = data.handler || '';
    elements.bugDeveloper.value = data.developer || '';
    elements.bugModule.value = data.module || '';

    // 设置优先级下拉框
    const priorities = ['P0 (紧急)', 'P1 (高)', 'P2 (中)', 'P3 (低)'];
    const pIdx = priorities.indexOf(data.priority);
    if (pIdx >= 0) elements.bugPriority.selectedIndex = pIdx;

    // 设置严重程度下拉框
    const severities = ['致命', '严重', '一般', '轻微'];
    const sIdx = severities.indexOf(data.severity);
    if (sIdx >= 0) elements.bugSeverity.selectedIndex = sIdx;
}

/**
 * 切换描述区域的预览/源码模式
 */
function toggleDescriptionMode() {
    const isPreviewVisible = !elements.bugDescriptionPreview.classList.contains('hidden');
    if (isPreviewVisible) {
        // 切换到源码编辑模式
        elements.bugDescriptionPreview.classList.add('hidden');
        elements.bugDescription.classList.remove('hidden');
        elements.btnToggleSource.textContent = '👁️ 预览';
    } else {
        // 切换回预览模式（先将 textarea 的内容同步到预览）
        elements.bugDescriptionPreview.innerHTML = elements.bugDescription.value;
        elements.bugDescriptionPreview.classList.remove('hidden');
        elements.bugDescription.classList.add('hidden');
        elements.btnToggleSource.textContent = '📝 编辑源码';
    }
}

/**
 * 获取当前可复制的描述 HTML
 */
function getDescriptionHtmlForCopy() {
    return (elements.bugDescription.value || elements.bugDescriptionPreview.innerHTML || '').trim();
}

/**
 * 复制生成结果，优先写入黑色富文本，同时回退纯文本
 */
async function handleCopyDescription() {
    const descriptionHtml = getDescriptionHtmlForCopy();
    if (!descriptionHtml) {
        showStatus('❌ 当前没有可复制的生成内容', 'error');
        return;
    }

    const clipboardHelper = window.bugReportClipboard;
    const payload = clipboardHelper
        ? clipboardHelper.buildClipboardPayload(descriptionHtml)
        : { html: descriptionHtml, text: descriptionHtml };

    try {
        if (typeof navigator.clipboard?.write === 'function' && window.ClipboardItem) {
            const clipboardItem = new ClipboardItem({
                'text/html': new Blob([payload.html], { type: 'text/html' }),
                'text/plain': new Blob([payload.text], { type: 'text/plain' })
            });
            await navigator.clipboard.write([clipboardItem]);
        } else if (typeof navigator.clipboard?.writeText === 'function') {
            await navigator.clipboard.writeText(payload.text);
        } else {
            throw new Error('当前环境不支持剪贴板写入');
        }

        showStatus('✅ 已复制生成结果，粘贴内容为黑色文本', 'success');
    } catch (err) {
        showStatus(`❌ 复制失败: ${err.message}`, 'error');
    }
}

/**
 * 加载需求列表到下拉框
 * @param {boolean} forceRefresh - 是否强制刷新（忽略缓存）
 */
async function loadStories(forceRefresh = false) {
    const select = elements.bugStory;

    // 如果有缓存且不强制刷新，直接用缓存
    if (!forceRefresh && cachedStories.length > 0) {
        renderStoryOptions(cachedStories);
        return;
    }

    select.innerHTML = '<option value="">-- 加载中... --</option>';
    elements.storySearch.value = '';

    try {
        const response = await chrome.runtime.sendMessage({ action: 'fetchStories' });

        if (response.success && response.data.length > 0) {
            cachedStories = response.data;
            renderStoryOptions(cachedStories);
        } else if (response.success) {
            cachedStories = [];
            select.innerHTML = '<option value="">-- 没有找到需求 --</option>';
        } else {
            select.innerHTML = '<option value="">-- 加载失败，请检查配置 --</option>';
        }
    } catch (err) {
        select.innerHTML = '<option value="">-- 加载失败 --</option>';
    }
}

/**
 * 渲染需求选项并恢复上次选择
 */
function renderStoryOptions(stories) {
    const select = elements.bugStory;
    select.innerHTML = '<option value="">-- 不关联需求 --</option>';

    stories.forEach(story => {
        const opt = document.createElement('option');
        opt.value = story.id;
        opt.textContent = story.name;
        select.appendChild(opt);
    });

    // 恢复上次选择
    chrome.storage.local.get(['lastStoryId'], (config) => {
        if (config.lastStoryId) {
            select.value = config.lastStoryId;
        }
    });
}

/**
 * 搜索过滤需求列表
 */
function filterStories() {
    const keyword = elements.storySearch.value.trim().toLowerCase();
    const select = elements.bugStory;
    select.innerHTML = '<option value="">-- 不关联需求 --</option>';

    const filtered = keyword
        ? cachedStories.filter(s => s.name.toLowerCase().includes(keyword))
        : cachedStories;

    filtered.forEach(story => {
        const opt = document.createElement('option');
        opt.value = story.id;
        opt.textContent = story.name;
        select.appendChild(opt);
    });
}

// ======== 提交到 TAPD ========
async function handleSubmit() {
    setButtonLoading(elements.btnSubmit, true);
    showStatus('📡 正在提交到 TAPD...', 'info');

    const bugData = {
        title: elements.bugTitle.value,
        description: elements.bugDescription.value,
        handler: elements.bugHandler.value,
        developer: elements.bugDeveloper.value,
        priority: elements.bugPriority.value,
        severity: elements.bugSeverity.value,
        module: elements.bugModule.value,
        reporter: elements.submitter.value,
        current_owner: elements.bugHandler.value,
        storyId: elements.bugStory.value || ''
    };

    try {
        const response = await chrome.runtime.sendMessage({
            action: 'submitToTAPD',
            bugData: bugData
        });

        if (response.success) {
            // 提交成功后上传附件
            if (selectedFiles.length > 0 && response.data.bugId) {
                showStatus(`📎 正在上传 ${selectedFiles.length} 个附件...`, 'info');
                const filesData = await prepareFilesForUpload();
                const uploadResult = await chrome.runtime.sendMessage({
                    action: 'uploadAttachments',
                    bugId: response.data.bugId,
                    files: filesData
                });
                if (!uploadResult.success) {
                    showStatus(`⚠️ Bug 已提交，但附件上传失败: ${uploadResult.error}`, 'error');
                    // 仍然跳转到成功页
                }
            }
            elements.successLink.href = response.data.url;
            // 提交成功，清除保存的状态
            chrome.storage.local.remove('popupState');
            showPhase('success');
            hideStatus();
        } else {
            showStatus(`❌ 提交失败: ${response.error}`, 'error');
        }
    } catch (err) {
        showStatus(`❌ 通信错误: ${err.message}`, 'error');
    } finally {
        setButtonLoading(elements.btnSubmit, false);
    }
}

// ======== 文件管理 ========

/**
 * 添加文件到列表
 */
function addFiles(fileListObj) {
    for (const file of fileListObj) {
        // 避免重复添加
        if (!selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
            selectedFiles.push(file);
        }
    }
    renderFileList();
}

/**
 * 移除文件
 */
function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFileList();
}

/**
 * 渲染文件列表
 */
function renderFileList() {
    const listEl = elements.fileList;
    listEl.innerHTML = '';

    if (selectedFiles.length === 0) {
        elements.uploadPlaceholder.classList.remove('hidden');
        return;
    }

    elements.uploadPlaceholder.classList.add('hidden');

    selectedFiles.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'file-item';

        // 缩略图
        if (file.type.startsWith('image/')) {
            const thumb = document.createElement('img');
            thumb.className = 'file-thumb';
            thumb.src = URL.createObjectURL(file);
            item.appendChild(thumb);
        } else {
            const icon = document.createElement('div');
            icon.className = 'file-thumb-icon';
            icon.textContent = getFileIcon(file.type);
            item.appendChild(icon);
        }

        // 文件信息
        const info = document.createElement('div');
        info.className = 'file-info';
        info.innerHTML = `<div class="file-name">${file.name}</div><div class="file-size">${formatSize(file.size)}</div>`;
        item.appendChild(info);

        // 删除按钮
        const removeBtn = document.createElement('button');
        removeBtn.className = 'file-remove';
        removeBtn.textContent = '✕';
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeFile(index);
        });
        item.appendChild(removeBtn);

        listEl.appendChild(item);
    });
}

/**
 * 获取文件类型图标
 */
function getFileIcon(mimeType) {
    if (mimeType.startsWith('video/')) return '🎬';
    if (mimeType.startsWith('image/')) return '🖼️';
    if (mimeType.includes('pdf')) return '📄';
    if (mimeType.includes('zip') || mimeType.includes('rar')) return '📦';
    return '📎';
}

/**
 * 格式化文件大小
 */
function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * 将文件转为 base64 以便通过 message 传递给 Service Worker
 */
async function prepareFilesForUpload() {
    const results = [];
    for (const file of selectedFiles) {
        const base64 = await fileToBase64(file);
        results.push({
            name: file.name,
            type: file.type,
            base64: base64
        });
    }
    return results;
}

function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(',')[1]); // 去掉 data:xxx;base64, 前缀
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}
