const test = require('node:test');
const assert = require('node:assert/strict');

const { buildClipboardPayload } = require('./clipboard.js');

test('buildClipboardPayload 会将富文本中的颜色统一为黑色', () => {
    const payload = buildClipboardPayload('<p style="font-weight: 700; color: #ffffff;">标题</p><a href="https://example.com">链接</a>');

    assert.equal(payload.html.includes('color: #000000;'), true);
    assert.equal(payload.html.includes('#ffffff'), false);
    assert.match(payload.html, /<a [^>]*style="[^"]*color: #000000;[^"]*"/);
});

test('buildClipboardPayload 会输出适合回填的纯文本', () => {
    const payload = buildClipboardPayload('<p>第一步</p><ul><li>打开页面</li><li>点击提交</li></ul><p>实际结果：无响应</p>');

    assert.equal(payload.text, '第一步\n打开页面\n点击提交\n实际结果：无响应');
});
