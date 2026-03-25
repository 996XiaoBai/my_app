import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  parseApiTestPayload,
  parseFlowchartPayload,
  parseRequirementAnalysisPayload,
  parseTestCaseReviewPayload,
  parseTestDataPayload,
} from './structuredResultParsers.ts'

test('parseRequirementAnalysisPayload returns structured payload when markdown exists', () => {
  const payload = parseRequirementAnalysisPayload(JSON.stringify({
    summary: 'done',
    markdown: '# 智能需求分析\n\n内容',
    items: [
      {
        module: '发布页',
        summary: '模块摘要',
        actors: ['用户'],
        business_rules: ['图片最多 9 张'],
      }
    ]
  }))

  assert.equal(payload?.items[0].module, '发布页')
  assert.equal(payload?.markdown, '# 智能需求分析\n\n内容')
})

test('parseTestCaseReviewPayload returns structured payload when revised suite exists', () => {
  const payload = parseTestCaseReviewPayload(JSON.stringify({
    summary: '已评审 2 条测试用例，识别 1 项问题。',
    findings: [
      {
        risk_level: 'H',
        category: '需求偏离',
        related_case_ids: ['case-login-2'],
        related_requirement_points: ['连续失败 5 次锁定 30 分钟'],
        description: '未覆盖锁定恢复规则。',
        suggestion: '补充锁定中登录与锁定恢复场景。',
      }
    ],
    reviewed_cases: [
      {
        case_id: 'case-login-1',
        title: '账号密码登录成功',
        module: '登录',
        verdict: 'pass',
        consistency: 'aligned',
        issues: [],
        suggestions: [],
      }
    ],
    revised_suite: {
      summary: '修订建议版测试用例，共 2 条。',
      items: [
        {
          id: 'case-login-1',
          priority: 'P1',
          module: '登录',
          title: '账号密码登录成功',
          steps: [
            { action: '输入正确账号密码', expected: '账号密码输入成功' },
          ],
        }
      ],
    },
    markdown: '# 测试用例评审报告',
  }))

  assert.equal(payload?.findings[0].category, '需求偏离')
  assert.equal(payload?.reviewed_cases[0].case_id, 'case-login-1')
  assert.equal(payload?.revised_suite.items[0].title, '账号密码登录成功')
})

test('parseFlowchartPayload returns mermaid items', () => {
  const payload = parseFlowchartPayload(JSON.stringify({
    summary: 'done',
    markdown: '# 业务流程图',
    items: [
      {
        module: '发布页',
        title: '图文发布',
        mermaid: 'flowchart TD\nA --> B',
      }
    ]
  }))

  assert.equal(payload?.items[0].mermaid, 'flowchart TD\nA --> B')
})

test('parseFlowchartPayload extracts mermaid code from json-like mermaid field', () => {
  const payload = parseFlowchartPayload(JSON.stringify({
    summary: 'done',
    markdown: '# 业务流程图',
    items: [
      {
        module: '埋点',
        title: '埋点事件设计',
        mermaid: JSON.stringify({
          module: '埋点',
          title: '埋点事件设计',
          mermaid: 'flowchart TD\nA[开始] --> B[设计]\nB --> C[上报]',
        }),
      }
    ]
  }))

  assert.equal(payload?.items[0].mermaid, 'flowchart TD\nA[开始] --> B[设计]\nB --> C[上报]')
})

test('parseFlowchartPayload extracts mermaid code from pseudo json with unescaped quotes', () => {
  const payload = parseFlowchartPayload(JSON.stringify({
    summary: 'done',
    markdown: '# 业务流程图',
    items: [
      {
        module: '埋点',
        title: '埋点事件设计',
        mermaid: `{
  "module": "埋点",
  "title": "埋点事件设计",
  "summary": "联合产品事件设计",
  "mermaid": "flowchart TD\\nStart[\\"开始\\"] --> DocEvent["事件设计表(xlsx)"]\\nDocEvent --> End[\\"完成\\"]",
  "warnings": ["字段待确认"]
}`,
      }
    ]
  }))

  assert.equal(
    payload?.items[0].mermaid,
    'flowchart TD\nStart["开始"] --> DocEvent["事件设计表(xlsx)"]\nDocEvent --> End["完成"]'
  )
})

test('parseFlowchartPayload parses persisted flowchart markdown history', () => {
  const payload = parseFlowchartPayload(`
# 业务流程图

> 已完成 1 个模块的业务流程提取。

## 域名白名单申请流程

申请并配置域名，完成白名单登记。

\`\`\`mermaid
flowchart TD
A[申请域名] --> B[配置白名单]
\`\`\`

### 风险提示
- 白名单登记时效待确认
  `.trim())

  assert.equal(payload?.summary, '已完成 1 个模块的业务流程提取。')
  assert.equal(payload?.items[0].title, '域名白名单申请流程')
  assert.equal(payload?.items[0].summary, '申请并配置域名，完成白名单登记。')
  assert.equal(payload?.items[0].mermaid, 'flowchart TD\nA[申请域名] --> B[配置白名单]')
  assert.deepEqual(payload?.items[0].warnings, ['白名单登记时效待确认'])
})

test('parseFlowchartPayload parses pseudo json mermaid wrapped by markdown code block', () => {
  const payload = parseFlowchartPayload(`
# 业务流程图

> 已完成 1 个模块的业务流程提取。

## 埋点事件设计

与联合产品对齐事件口径。

\`\`\`mermaid
{
  "module": "埋点",
  "title": "埋点事件设计",
  "summary": "联合产品事件设计",
  "mermaid": "flowchart TD\\nStart[\\"开始\\"] --> DocEvent["事件设计表(xlsx)"]\\nDocEvent --> End[\\"完成\\"]",
  "warnings": ["字段待确认"]
}
\`\`\`

### 风险提示
- 字段待确认
  `.trim())

  assert.equal(
    payload?.items[0].mermaid,
    'flowchart TD\nStart["开始"] --> DocEvent["事件设计表(xlsx)"]\nDocEvent --> End["完成"]'
  )
})

test('parseFlowchartPayload repairs malformed mermaid in persisted history markdown', () => {
  const payload = parseFlowchartPayload(`
# 业务流程图

> 已完成 1 个模块的业务流程提取。

## 课程库内容审核快捷操作与审核详情查看流程

根据课程库内容的审核状态动态展示快捷按钮。

\`\`\`mermaid
flowchart TD
Start("进入课程库列表"):::start --> User("运营/内容管理员"):::role
User --> ViewList["查看内容条目"):::process
ViewList --> GetStatus["读取审核状态"):::process
\`\`\`
  `.trim())

  assert.equal(
    payload?.items[0].mermaid,
    'flowchart TD\nStart("进入课程库列表"):::start --> User("运营/内容管理员"):::role\nUser --> ViewList["查看内容条目"]:::process\nViewList --> GetStatus["读取审核状态"]:::process'
  )
})

test('parseFlowchartPayload repairs slash-wrapped data node labels', () => {
  const payload = parseFlowchartPayload(`
# 业务流程图

> 已完成 1 个模块的业务流程提取。

## 审核详情查看

审核详情节点需要兼容历史坏样本。

\`\`\`mermaid
flowchart TD
subgraph DataLayer["数据产物"]
  AuditDetail[\\/"审核详情: 结果/原因/时间/审核人"\\/]:::data
end
\`\`\`
  `.trim())

  assert.equal(
    payload?.items[0].mermaid,
    'flowchart TD\nsubgraph DataLayer["数据产物"]\n  AuditDetail["审核详情: 结果/原因/时间/审核人"]:::data\nend'
  )
})

test('parseFlowchartPayload repairs subgraph labels with parentheses', () => {
  const payload = parseFlowchartPayload(`
# 业务流程图

> 已完成 1 个模块的业务流程提取。

## 内容分类字段选择与落库

下游子流程标题包含括号。

\`\`\`mermaid
flowchart TD
subgraph Downstream[后续送审链路(引用)]
  UseInSubmit["送审/重送审携带分类"]:::highlight
end
\`\`\`
  `.trim())

  assert.equal(
    payload?.items[0].mermaid,
    'flowchart TD\nsubgraph Downstream["后续送审链路(引用)"]\n  UseInSubmit["送审/重送审携带分类"]:::highlight\nend'
  )
})

test('parseFlowchartPayload repairs malformed mermaid in persisted history fixture', () => {
  const historyFixturePath = new URL(
    '../../../../history/20260320_183559_674492_兴趣岛TV-APP内容风控审核接入.pdf_flowchart_2f3304ca.json',
    import.meta.url,
  )
  const historyRecord = JSON.parse(readFileSync(historyFixturePath, 'utf8')) as {
    content?: string
  }

  const payload = parseFlowchartPayload(historyRecord.content ?? '')
  const auditDetailModule = payload?.items.find((item) => item.title === '课程库内容审核快捷操作与审核详情查看流程')
  const categoryModule = payload?.items.find((item) => item.title === '课程库新增/编辑弹窗：内容分类字段选择与落库')

  assert.ok(payload)
  assert.equal(payload?.summary, '已完成 17 个模块的业务流程提取。')
  assert.equal(
    auditDetailModule?.mermaid.includes('AuditDetail["审核详情: 结果/原因/时间/审核人"]:::data'),
    true
  )
  assert.equal(
    auditDetailModule?.mermaid.includes('AuditDetail[\\/"审核详情: 结果/原因/时间/审核人"\\/]'),
    false
  )
  assert.equal(
    categoryModule?.mermaid.includes('subgraph Downstream["后续送审链路(引用)"]'),
    true
  )
  assert.equal(
    categoryModule?.mermaid.includes('subgraph Downstream[后续送审链路(引用)]'),
    false
  )
})

test('parseApiTestPayload returns structured payload and keeps markdown output', () => {
  const payload = parseApiTestPayload(JSON.stringify({
    summary: '已生成接口测试资产。',
    markdown: '# 接口测试资产\n\n## 用例清单\n- platformGoods_add_success\n',
    spec: {
      title: '默认模块',
      openapi_version: '3.0.1',
    },
    cases: [
      {
        case_id: 'platformGoods_add_success',
        title: '新增平台带货成功',
      },
    ],
    scenes: [
      {
        scene_id: 'platformGoods_crud_flow',
        title: '平台带货管理 CRUD 主链路',
      },
    ],
    link_plan: {
      ordered_case_ids: ['platformGoods_add_success'],
      standalone_case_ids: ['platformGoods_add_success'],
      scene_orders: [],
    },
    suite: {
      suite_id: 'api_suite_platform_goods',
      suite_version: 2,
    },
    report: {
      status: 'passed',
      headline: '默认模块：执行通过',
    },
    execution: {
      status: 'passed',
      summary: '执行 1 条 pytest 用例，全部通过。',
    },
  }))

  assert.equal(payload?.spec.title, '默认模块')
  assert.equal(payload?.cases[0].case_id, 'platformGoods_add_success')
  assert.equal(payload?.scenes[0].scene_id, 'platformGoods_crud_flow')
  assert.equal(payload?.link_plan?.ordered_case_ids[0], 'platformGoods_add_success')
  assert.equal(payload?.suite?.suite_version, 2)
  assert.equal(payload?.report?.headline, '默认模块：执行通过')
  assert.equal(payload?.execution?.status, 'passed')
  assert.equal(payload?.markdown, '# 接口测试资产\n\n## 用例清单\n- platformGoods_add_success\n')
})

test('parseTestDataPayload parses fixed markdown hierarchy into structured sections', () => {
  const payload = parseTestDataPayload(`
# 识别摘要

- 文档名称：直播提效.doc
- 处理摘要：已识别 2 张表
- 识别表数量：2
- 生成场景数量：2

## 表清单
- \`xqd_platform_goods\`：5 个字段

## 场景清单
- 查询与插入直播商品：xqd_platform_goods

# 按表 SQL

## 直播商品表 (\`xqd_platform_goods\`)

### 字段摘要

| 字段 | 类型 | 主键 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| id | bigint | 是 | 否 | 主键 |

### SELECT

\`\`\`sql
SELECT \`id\`
FROM \`xqd_platform_goods\`
LIMIT 20;
\`\`\`

### INSERT

\`\`\`sql
INSERT INTO \`xqd_platform_goods\` (\`id\`) VALUES (10001);
\`\`\`

# 按场景 SQL

## 查询与插入直播商品

### 依赖表

- \`xqd_platform_goods\`

### SELECT

\`\`\`sql
SELECT \`id\`
FROM \`xqd_platform_goods\`
LIMIT 20;
\`\`\`

### INSERT

\`\`\`sql
INSERT INTO \`xqd_platform_goods\` (\`id\`) VALUES (10001);
\`\`\`

# 识别告警

- 未发现明显告警。
  `.trim())

  assert.equal(payload?.metrics[0].label, '文档名称')
  assert.equal(payload?.tables[0].title, '直播商品表 (`xqd_platform_goods`)')
  assert.equal(payload?.tables[0].selectSql, 'SELECT `id`\nFROM `xqd_platform_goods`\nLIMIT 20;')
  assert.equal(payload?.scenarios[0].title, '查询与插入直播商品')
  assert.equal(payload?.warningsMarkdown, '- 未发现明显告警。')
})

test('parseTestDataPayload prefers json payload and keeps update delete sql with sql file content', () => {
  const payload = parseTestDataPayload(JSON.stringify({
    document_name: '直播提效.doc',
    summary: '已生成测试数据 SQL。',
    markdown: '# 识别摘要\n\n- 文档名称：直播提效.doc\n- 处理摘要：已生成测试数据 SQL。\n- 识别表数量：1\n- 生成场景数量：1\n',
    sql_file_content: '-- 识别摘要\n-- 文档名称：直播提效.doc\n',
    tables: [
      {
        name: 'xqd_platform_goods',
        display_name: '直播商品表',
        description: '商品信息',
        columns: [
          { name: 'id', sql_type: 'bigint', description: '主键', primary_key: true, required: true },
        ],
        select_sql: 'SELECT `id` FROM `xqd_platform_goods` WHERE `id` = 10001 LIMIT 20;',
        insert_sql: 'INSERT INTO `xqd_platform_goods` (`id`) VALUES (10001);',
        update_sql: 'UPDATE `xqd_platform_goods` SET `id` = 10001 WHERE `id` = 10001;',
        delete_sql: 'DELETE FROM `xqd_platform_goods` WHERE `id` = 10001;',
      },
    ],
    scenarios: [
      {
        name: '直播商品修正',
        tables: ['xqd_platform_goods'],
        select_sql: 'SELECT `id` FROM `xqd_platform_goods` WHERE `id` = 10001 LIMIT 20;',
        insert_sql: 'INSERT INTO `xqd_platform_goods` (`id`) VALUES (10001);',
        update_sql: 'UPDATE `xqd_platform_goods` SET `id` = 10001 WHERE `id` = 10001;',
        delete_sql: 'DELETE FROM `xqd_platform_goods` WHERE `id` = 10001;',
      },
    ],
    warnings: ['字段默认值依赖人工确认'],
  }))

  assert.equal(payload?.metrics[0].label, '文档名称')
  assert.equal(payload?.tables[0].updateSql, 'UPDATE `xqd_platform_goods` SET `id` = 10001 WHERE `id` = 10001;')
  assert.equal(payload?.tables[0].deleteSql, 'DELETE FROM `xqd_platform_goods` WHERE `id` = 10001;')
  assert.equal(payload?.scenarios[0].updateSql, 'UPDATE `xqd_platform_goods` SET `id` = 10001 WHERE `id` = 10001;')
  assert.equal(payload?.sqlFileContent, '-- 识别摘要\n-- 文档名称：直播提效.doc\n')
  assert.equal(payload?.documentName, '直播提效.doc')
})
