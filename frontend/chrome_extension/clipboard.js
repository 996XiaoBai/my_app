/**
 * 缺陷报告复制工具
 */

const BLACK_TEXT_STYLE = 'color: #000000;';
const BLOCK_TAG_CLOSE_PATTERN = /<\/(p|div|li|section|article|blockquote|h[1-6]|tr|table|ul|ol)>/gi;
const LINE_BREAK_TAG_PATTERN = /<br\s*\/?>/gi;
const LIST_ITEM_OPEN_PATTERN = /<li\b[^>]*>/gi;
const STYLE_ATTRIBUTE_PATTERN = /\sstyle\s*=\s*(["'])([\s\S]*?)\1/i;
const OPEN_TAG_PATTERN = /<([a-zA-Z][\w:-]*)(\s[^<>]*?)?>/g;
const HTML_TAG_PATTERN = /<[^>]+>/g;

function normalizeStyleValue(styleValue) {
    const withoutColor = String(styleValue || '')
        .replace(/(^|;)\s*color\s*:\s*[^;]+;?/gi, '$1')
        .replace(/;;+/g, ';')
        .trim()
        .replace(/^;|;$/g, '')
        .trim();

    return withoutColor ? `${withoutColor}; ${BLACK_TEXT_STYLE}` : BLACK_TEXT_STYLE;
}

function forceBlackTextHtml(html) {
    const safeHtml = String(html || '').trim();

    if (!safeHtml) {
        return `<div style="${BLACK_TEXT_STYLE}"></div>`;
    }

    const styledHtml = safeHtml.replace(OPEN_TAG_PATTERN, (match, tagName, rawAttrs = '') => {
        if (/^(br|hr)$/i.test(tagName) || match.startsWith('</')) {
            return match;
        }

        const attrs = rawAttrs || '';
        const styleMatch = attrs.match(STYLE_ATTRIBUTE_PATTERN);

        if (styleMatch) {
            const nextStyle = normalizeStyleValue(styleMatch[2]);
            return `<${tagName}${attrs.replace(STYLE_ATTRIBUTE_PATTERN, ` style="${nextStyle}"`)}>`;
        }

        return `<${tagName}${attrs} style="${BLACK_TEXT_STYLE}">`;
    });

    return `<div style="${BLACK_TEXT_STYLE}">${styledHtml}</div>`;
}

function decodeHtmlEntities(text) {
    return String(text || '')
        .replace(/&nbsp;/gi, ' ')
        .replace(/&amp;/gi, '&')
        .replace(/&lt;/gi, '<')
        .replace(/&gt;/gi, '>')
        .replace(/&quot;/gi, '"')
        .replace(/&#39;/gi, "'");
}

function htmlToPlainText(html) {
    const normalized = String(html || '')
        .replace(/\r/g, '')
        .replace(LINE_BREAK_TAG_PATTERN, '\n')
        .replace(LIST_ITEM_OPEN_PATTERN, '')
        .replace(BLOCK_TAG_CLOSE_PATTERN, '\n')
        .replace(HTML_TAG_PATTERN, '');

    return decodeHtmlEntities(normalized)
        .replace(/[ \t]+\n/g, '\n')
        .replace(/\n{2,}/g, '\n')
        .trim();
}

function buildClipboardPayload(html) {
    return {
        html: forceBlackTextHtml(html),
        text: htmlToPlainText(html)
    };
}

if (typeof window !== 'undefined') {
    window.bugReportClipboard = {
        buildClipboardPayload
    };
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        buildClipboardPayload,
        forceBlackTextHtml,
        htmlToPlainText
    };
}
