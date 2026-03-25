# OpenAPI 接口测试闭环平台设计

日期：2026-03-22

## 背景

当前测试平台中的 `api_test_gen` 能力，本质上仍然是“根据接口文档生成一段 Pytest 脚本”的一键生成模式。它已经可以产出基础脚本，但还没有形成完整的接口测试闭环：

- 没有把 OpenAPI 文档沉淀为稳定的接口资产
- 没有把测试用例作为可复用资产长期保存
- 没有稳定的多接口关联编排能力
- 没有统一的执行引擎
- 没有结构化的执行报告与回归沉淀机制

用户的真实目标不是“生成脚本”，而是：

- 根据 API Fox 导出的 OpenAPI/Swagger 标准 JSON 生成接口自动测试用例
- 运行测试
- 输出报告
- 沉淀用例，支持后续复用与回归

结合当前仓库和用户输入，本次设计聚焦于把测试平台中的接口测试模块升级成“接口测试闭环平台”。

## 已确认输入前提

- 用户日常输入来源是 API Fox 导出的接口文档
- 文档格式为 `OpenAPI/Swagger 标准 JSON`
- 文档中通常包含：
  - `servers`
  - `paths`
  - `parameters`
  - `requestBody`
  - `responses`
  - `components.schemas`
  - `security`
- 典型文档会同时包含：
  - 请求头鉴权
  - Cookie 鉴权
  - 示例响应
  - 一组围绕同一资源的 CRUD 接口

这意味着第一阶段不需要先兼容纯文本接口说明，主链路可以围绕 OpenAPI JSON 直接建设。

## 已确认需求

- 目标能力必须覆盖：
  - 接口文档解析
  - 接口自动测试用例生成
  - 测试执行
  - 测试报告输出
  - 用例沉淀
- 平台不能只停留在“脚本生成器”
- 多接口场景需要支持接口关联
- 第一优先输入类型是 OpenAPI/Swagger JSON
- 第一阶段允许通过页面填写环境与鉴权信息执行测试
- 方案需要先落正式设计文档，再进入实现阶段

## 目标与非目标

## 目标

- 将 OpenAPI JSON 解析为统一接口测试资产
- 生成结构化接口测试用例，而不是只生成 Python 脚本
- 识别接口分类与资源归组
- 支持基础多接口关联编排
- 在平台内统一执行 `pytest`
- 输出结构化执行报告
- 将规范、用例、脚本、执行记录、报告一起沉淀
- 为后续回归复用与变更影响分析预留扩展点

## 非目标

- 第一阶段不追求兼容所有纯文本接口文档
- 第一阶段不做复杂签名算法自动逆向
- 第一阶段不接入外部 CI 平台
- 第一阶段不直接覆盖所有非 OpenAPI 导出格式
- 第一阶段不实现可视化拖拽式链路编排器

## 方案选型

本次能力建设有三个备选方向。

### 方案 A：纯 LLM 脚本生成型

- 输入 OpenAPI 文档
- 直接让大模型生成 `pytest` 脚本
- 再由平台执行

优点：

- 接入快
- 前期改动少

缺点：

- 结果漂移大
- 接口关联依赖模型猜测
- 用例难以沉淀和复用
- 文档变更后难以稳定修复

### 方案 B：规范驱动混合型

- 先把 OpenAPI 解析成结构化接口资产
- 再生成结构化测试用例
- 再编译成 `pytest` 脚本执行
- 报告和沉淀都围绕结构化资产展开

优点：

- 稳定
- 可复用
- 易做接口关联
- 易做报告与回归

缺点：

- 初始实现复杂度高于纯脚本生成

### 方案 C：完整测试资产平台型

- 在方案 B 基础上一次性补齐：
  - 资产版本化
  - 定时回归
  - 差异分析
  - 缺陷联动
  - 多环境矩阵

优点：

- 最终形态完整

缺点：

- 一期过重
- 交付风险高

## 结论

采用 **方案 B：规范驱动混合型**，并通过分期建设逐步演进到方案 C。

## 设计原则

### 1. 主资产不是脚本，而是结构化用例

脚本属于派生产物，平台真正要沉淀的是：

- 规范资产
- 资源模型
- 结构化用例
- 关联场景
- 执行结果
- 报告资产

### 2. 接口关联不能依赖模型猜测

接口关联必须优先由规则和结构化信息驱动：

- 文档显式信息
- 路径与方法命名
- 请求体与响应体模型
- 回查规则

必要时再允许用户确认。

### 3. 执行必须可复跑、可审计

每次执行都要形成完整运行目录，保留：

- 运行输入
- 生成脚本
- 日志
- 原始报告
- 结构化摘要

### 4. 平台展示优先于命令行细节

前端应展示：

- 解析理解结果
- 用例清单
- 关联链路
- 执行日志
- 失败明细
- 历史沉淀

而不是只展示一段 Python 代码。

## 总体架构

整体采用“五层闭环架构”：

```text
OpenAPI 文档
  -> 规范解析层
  -> 用例资产层
  -> 关联编排层
  -> 执行与报告层
  -> 沉淀与回归层
```

### 1. 规范解析层

输入 OpenAPI JSON，输出统一接口资产：

- 服务地址
- 鉴权方式
- tag 分组
- operation 清单
- 请求模型
- 响应模型
- 资源归组

### 2. 用例资产层

基于规范资产生成结构化用例：

- 单接口基础用例
- 边界与异常用例
- 协议一致性用例
- 关联场景用例

### 3. 关联编排层

识别接口之间的依赖关系：

- 鉴权上下文依赖
- 对象标识依赖
- CRUD 顺序依赖
- 状态流转依赖

### 4. 执行与报告层

将结构化用例编译成 `pytest` 脚本并执行，产出：

- `JUnit XML`
- `Allure results`
- 平台摘要 JSON
- Markdown 摘要

### 5. 沉淀与回归层

将本次执行沉淀为长期资产：

- 规范版本
- 用例版本
- 报告版本
- 回归基线

## 核心能力设计

## 一、规范解析与接口资产化

建议新增 `OpenApiAssetService`，负责将 OpenAPI JSON 解析成统一模型。

### 输出模型建议

```json
{
  "spec_id": "spec_xxx",
  "title": "默认模块",
  "version": "1.0.0",
  "openapi_version": "3.0.1",
  "servers": [
    {
      "url": "https://edu-admin.dev1.dachensky.com",
      "description": "测试环境dev1"
    }
  ],
  "security_profiles": [],
  "resources": [],
  "operations": []
}
```

### 接口分类

平台需先把每个 operation 归类：

- `auth`
- `list`
- `detail`
- `create`
- `update`
- `delete`
- `status`
- `batch`
- `unknown`

分类依据：

- 路径命名
- 方法
- 请求体 schema
- 响应体 schema
- tag

对于用户样例，识别结果应为：

- `/admin/platformGoods/adminList` -> `list`
- `/admin/platformGoods/add` -> `create`
- `/admin/platformGoods/update` -> `update`
- `/admin/platformGoods/delete` -> `delete`
- `/admin/platformGoods/updateStatus` -> `status`

### 资源归组

需要把同一业务实体的接口归到一个资源组。

归组依据：

- 路径前缀
- tag
- schema 名称

示例归组结果：

```text
资源组：platformGoods
tag：平台带货管理
接口：
- adminList
- add
- update
- delete
- updateStatus
```

### 鉴权识别

平台需要识别并汇总鉴权输入：

- `Authorization`
- `Authorization-User`
- `cookie`
- `userId`
- `securitySchemes`

输出统一的鉴权配置模型，供执行时注入。

## 二、结构化接口测试用例模型

平台的主资产是结构化用例，而不是测试脚本。

### 用例集模型

```json
{
  "suite_id": "platform_goods_admin",
  "suite_name": "平台带货管理",
  "source": {
    "type": "openapi",
    "title": "默认模块",
    "version": "1.0.0",
    "server": "https://edu-admin.dev1.dachensky.com"
  },
  "auth_profile": {
    "required_headers": [
      "Authorization",
      "Authorization-User"
    ],
    "required_cookies": [
      "cookie",
      "userId"
    ]
  },
  "resource_model": {
    "resource_key": "platformGoods",
    "id_field": "id",
    "id_list_field": "ids",
    "lookup_fields": [
      "title",
      "businessId",
      "jumpUrl"
    ]
  },
  "cases": [],
  "scenes": []
}
```

### 单用例模型

```json
{
  "case_id": "platform_goods_add_success",
  "title": "新增平台带货成功",
  "operation_id": "POST /admin/platformGoods/add",
  "category": "create",
  "priority": "P1",
  "tags": ["平台带货管理", "新增", "正向"],
  "preconditions": [],
  "request": {},
  "extract": [],
  "assertions": [],
  "depends_on": [],
  "teardown": []
}
```

### 请求模板模型

请求内容要保留模板能力，支持：

- 环境变量
- 运行时变量
- 动态数据

例如：

```json
{
  "headers": {
    "Authorization": "{{env.Authorization}}",
    "Authorization-User": "{{env.Authorization-User}}"
  },
  "cookies": {
    "cookie": "{{env.cookie}}",
    "userId": "{{env.userId}}"
  },
  "json": {
    "title": "{{runtime.unique_title}}",
    "businessId": "{{faker.int64}}"
  }
}
```

### 断言模型

断言应结构化表示，便于统一编译和报告：

- `status_code`
- `json_path_eq`
- `json_path_exists`
- `json_path_type`
- `array_length_gte`
- `contains`

对于用户样例中的公共返回体，平台默认可沉淀公共断言：

- HTTP 状态码为 `200`
- `state.code == 0`
- `state` 字段存在
- `timestamp` 字段存在
- `data` 字段存在

## 三、接口关联规则设计

接口关联的核心不是“响应必须直接返回 id”，而是“后续接口必须能定位目标对象”。

### 关联优先级

平台按以下优先级定位对象标识：

1. 直接从响应提取
2. 通过查询接口回查
3. 用户人工确认

### 直接提取规则

优先尝试从响应里提取：

- `data.id`
- `id`
- `data.ids[0]`

### 回查定位规则

如果创建接口不返回 `id`，则自动触发回查。

回查策略：

- 优先选择同资源组的 `list` 接口
- 使用创建请求中最稳定的字段进行回查
- 默认优先字段：
  - `title`
  - `businessId`
  - `jumpUrl`

### 样例主链路

对于用户给出的平台带货管理接口，第一版默认生成的主链路应为：

```text
add
  -> adminList 回查新增对象
  -> update
  -> updateStatus
  -> delete
  -> adminList 校验删除结果
```

### 运行时上下文

关联链路执行时，需要维护统一上下文：

- `runtime.created_id`
- `runtime.created_ids`
- `runtime.unique_title`
- `runtime.auth.*`

后续步骤通过变量表达式引用前置结果。

### 降级与人工确认

以下情况不应继续盲跑：

- 回查结果为空
- 回查结果不唯一
- 没有可用的查询接口
- 鉴权参数未配置
- 请求字段不足以唯一定位对象

此时应将用例标记为：

- `关联待确认`

并在前端提示用户补充：

- 唯一键
- 回查条件
- 手工对象标识

## 四、执行引擎设计

建议新增 `ApiExecutionService`，统一管理接口用例执行。

### 执行链路

```text
结构化用例
  -> 编译 pytest 脚本
  -> 创建运行目录
  -> 注入环境与鉴权
  -> 调用 pytest
  -> 收集报告
  -> 聚合结果
```

### 运行目录

每次执行都创建独立目录：

```text
test_platform/runtime/api_runs/<run_id>/
  suite.json
  generated_tests/
  artifacts/
    junit.xml
    report.json
    run.log
    allure-results/
```

### 执行配置

每次运行都要保存配置快照：

```json
{
  "run_id": "api_run_xxx",
  "suite_id": "platform_goods_admin",
  "env_name": "dev1",
  "base_url": "https://edu-admin.dev1.dachensky.com",
  "auth": {
    "Authorization": "...",
    "Authorization-User": "...",
    "cookie": "...",
    "userId": "..."
  },
  "execution_mode": "scene",
  "target": "platform_goods_crud_flow"
}
```

### 执行方式

第一阶段统一基于 `pytest` 执行，不新增自研 runner。

后续官方参考：

- https://docs.pytest.org/en/stable/how-to/usage.html

## 五、报告设计

建议统一产出三类报告：

### 1. JUnit XML

用于程序消费和后续 CI 对接。

### 2. Allure Results

用于生成更细粒度的可视化报告。

后续官方参考：

- https://allurereport.org/docs/pytest/

### 3. 平台摘要 JSON

供前端直接消费：

```json
{
  "run_id": "api_run_xxx",
  "summary": {
    "total": 12,
    "passed": 10,
    "failed": 2,
    "skipped": 0,
    "duration_ms": 18230
  },
  "cases": []
}
```

### 失败明细要求

每条失败用例至少保留：

- 用例名称
- 请求 URL
- 请求头
- 请求体
- 响应状态码
- 响应体片段
- 失败断言
- 前置变量
- 所属场景

## 六、前端交互设计

接口测试页需要从“脚本生成器”升级为“接口测试工作台”。

### 页面阶段

- 导入规范
- 解析资产
- 生成用例
- 执行测试
- 输出沉淀

### 页面布局

建议延续现有三栏工作台：

- 左侧：输入与执行配置
- 中间：用例、执行、报告主视图
- 右侧：资产、环境、历史沉淀

### 导入后应展示的解析结果

用户上传文档后，不应直接只显示代码，而应先展示：

- 服务地址
- 鉴权字段
- 接口数
- 资源组
- 自动识别出的关联链路

### 结果页签建议

- 解析结果
- 用例
- 执行日志
- 报告
- 历史沉淀

## 七、沉淀与回归设计

沉淀对象不应只是“结果文本”，而应形成测试资产。

### 沉淀对象

建议保存四类对象：

1. 规范版本
2. 用例版本
3. 执行版本
4. 报告版本

### 回归资产视图

每个沉淀套件应可查看：

- 套件名称
- 来源文档
- 资源组
- 用例数
- 场景数
- 最近执行时间
- 最近通过率
- 适用环境

### 后续复用入口

沉淀后的套件应支持：

- 直接从历史套件发起执行
- 复制出新版本
- 查看历史结果
- 仅执行失败用例
- 后续扩展到差异回归

## 八、技术实现建议

建议新增或重构以下服务：

- `test_platform/core/services/openapi_asset_service.py`
- `test_platform/core/services/api_case_service.py`
- `test_platform/core/services/api_linking_service.py`
- `test_platform/core/services/api_execution_service.py`
- `test_platform/core/services/api_report_service.py`
- `test_platform/core/services/api_suite_repository.py`

前端建议新增专属页面，而不是继续长期复用通用模块页：

- 新建接口测试专属工作台页面
- 增加用例、执行、报告、沉淀专属视图

## 九、分阶段实施计划

## 第一阶段：最小可用闭环

目标：

- 打通 `OpenAPI JSON -> 用例 -> 执行 -> 报告 -> 沉淀`

范围：

- 仅支持 OpenAPI/Swagger JSON
- 实现接口分类
- 实现资源归组
- 实现结构化用例生成
- 实现基础 CRUD 关联
- 实现 `pytest` 执行
- 实现基础报告与沉淀

完成标准：

- 用户上传 API Fox 导出的 OpenAPI JSON
- 平台能识别接口清单和资源组
- 平台能生成结构化用例
- 用户可填写环境与鉴权后直接执行
- 页面可展示失败明细
- 结果可沉淀为历史资产

## 第二阶段：关联增强

目标：

- 把“能执行”升级到“能稳定串链路”

范围：

- 响应字段提取
- 列表回查定位
- 运行时上下文变量
- 依赖失败自动跳过
- 关联待确认面板

## 第三阶段：报告与回归增强

目标：

- 把执行结果升级成回归资产

范围：

- Allure 集成
- 失败重跑
- 套件版本化
- 环境模板
- 历史趋势展示

## 第四阶段：高级平台能力

目标：

- 继续演进到完整接口测试资产平台

范围：

- OpenAPI 变更影响分析
- 受影响接口回归
- 定时执行
- CI 集成
- 缺陷系统联动
- 纯文本接口文档辅助解析

## 十、风险与约束

### 1. 文档质量风险

即使是 OpenAPI JSON，也可能存在：

- schema 引用不完整
- 示例响应与真实接口不一致
- 创建接口不返回对象标识

平台必须做好降级和人工确认能力。

### 2. 鉴权复杂度风险

部分接口可能依赖：

- Header
- Cookie
- 多字段组合
- 动态登录流程

第一阶段需先以“手工填写鉴权信息”为主。

### 3. 误关联风险

如果多个对象共享相似字段，列表回查可能命中多条数据。

因此第一阶段必须支持：

- 生成唯一测试数据
- 回查结果唯一性校验
- 关联待确认降级

## 十一、与当前代码现状的关系

当前仓库中已经存在：

- 接口测试 mode：`api_test_gen`
- 一键执行模式映射
- 历史记录能力
- Web 工作台基础框架

但当前仍缺失：

- OpenAPI 资产化
- 结构化接口用例模型
- 接口关联编排
- 执行引擎
- 专属报告模型
- 回归沉淀模型

因此本次设计并不是简单增强当前提示词，而是把现有接口测试能力升级为一套完整的专项平台链路。

## 十二、结论

本次接口测试能力建设，应围绕 API Fox 导出的 OpenAPI JSON，建设一套“规范驱动、结构化、可执行、可沉淀”的接口测试闭环平台。

第一阶段必须先打通最小闭环：

- 规范解析
- 用例生成
- 基础关联
- 执行
- 报告
- 沉淀

在此基础上，再逐步增强：

- 复杂关联
- 回归复用
- 差异分析
- 平台化运营能力

只有这样，接口测试模块才能真正从“脚本生成器”升级为“测试资产平台”。
