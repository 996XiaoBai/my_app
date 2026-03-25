# Test Cases: 直播提效+广告埋点治理

## Overview
- **Feature**: 直播提效与广告埋点治理
- **Requirements Source**: /Users/linkb/PycharmProjects/my_app/test_platform/docs/直播提效+广告埋点治理.pdf
- **Test Coverage**: APP直播间多场景触达、展示过滤规则、挽留弹窗、卡片位规则优化、UTMID归因埋点。
- **Last Updated**: 2026-03-16

## Test Case Categories

### 1. Functional Tests
Test cases covering normal user flows and core functionality.

#### TC-F-001: 首页帖子关联直播间跳转弹卡
- **Requirement**: 首页帖子关联+直播间跳转弹卡（2.1）
- **Priority**: High
- **Preconditions**:
  - 存在处于“直播中”状态的关联直播间
  - 用户正常浏览包含图文/视频的帖子
- **Test Steps**:
  1. 打开首页，浏览已关联直播间的帖子
  2. 观察帖子页面是否正常展示直播间跳转弹卡/链接
  3. 点击跳转链接/弹卡
- **Expected Results**:
  - 前端正常渲染跳转弹卡
  - 点击后成功跳转并进入对应直播间
- **Postconditions**: 用户成功停留在直播间页面

#### TC-F-002: 直播间挽留弹窗通用逻辑
- **Requirement**: 新增直播间挽留弹窗（2.2.1）
- **Priority**: Medium
- **Preconditions**:
  - 用户正在观看端内直播
- **Test Steps**:
  1. 用户点击左上角返回按钮或通过物理侧滑手势尝试退出直播间
  2. 观察是否弹出挽留弹窗
  3. 点击“留在直播间”
  4. 再次尝试退出，点击“确认退出”
- **Expected Results**:
  - 首次尝试退出时前端弹出设计的挽留提示框
  - 选择留下后弹窗无缝关闭，继续播放直播
  - 选择退出后，成功离开当前直播间
- **Postconditions**: 视用户交互选择而定

#### TC-F-003: 广告埋点全链路监控追溯
- **Requirement**: 广告位置埋点数据治理-转化效率跟踪（3.1）
- **Priority**: High
- **Preconditions**:
  - 分配一个带有特定活动 utmid 标识的站内/站外广告链接
- **Test Steps**:
  1. 用户（测试账号）点击带有 utmid 的广告链接进入直播间
  2. 在直播间内浏览商品并下单支付完成转化
  3. 后台数据分析师/开发测试人员查询底层埋点日志（ODS层或日志平台）
- **Expected Results**:
  - 点击、曝光、进入直播间、下单的各关键行为的自定义事件均已被触发和上报
  - 订单数据能完整追溯关联到原始访问的唯一广告位标识 `utmid`
- **Postconditions**: 埋点入库成功且关联查询一致

### 2. Edge Case Tests
Test cases covering boundary conditions and unusual inputs.

#### TC-E-001: 站内 utmid 连续覆盖测试
- **Requirement**: 关于大数据的utmid，如果在站内，下一个 utmid 会自动覆盖上一个（3.2）
- **Priority**: High
- **Preconditions**:
  - 构建至少2个站内跳转入口（如：焦点图入口A utmid=in_1，推荐信息流入口B utmid=in_2）
- **Test Steps**:
  1. 用户通过站内入口A（utmid=in_1）访问某中间页
  2. 没有产生交易时，用户又通过站内入口B（utmid=in_2）跳转进直播间并最终下单
  3. 检查落库的订单最后归因的 utmid 字段
- **Expected Results**:
  - 最终订单追溯到的来源广告位是 utmid=in_2（遵循站内自动覆盖原则）
- **Postconditions**: 链路归因为最新的有效触达

#### TC-E-002: 站外 utmid 强保留不覆盖测试
- **Requirement**: 如果是站外，则不会覆盖（3.2）
- **Priority**: High
- **Preconditions**:
  - 准备外部渠道（如微信/浏览器）广告链接（utmid=out_1）和站内链接（utmid=in_1）
- **Test Steps**:
  1. 用户从站外广告（utmid=out_1）拉起或唤醒进入APP特定落地页/直播间
  2. 用户退出后不久，在有效转化周期内，又点击站内入口（utmid=in_1）重复进入该直播间并下单
  3. 检查最终订单的引流归因
- **Expected Results**:
  - 订单的主要拉新/召回归因中，站外 utmid（out_1）记录不被站内新产生的（in_1）覆盖抹除
- **Postconditions**: 埋点成功保留全量归因参数，尤其是珍贵的站外入口属性

### 3. Error Handling Tests
Test cases covering error scenarios and failure modes.

#### TC-ERR-001: 首页帖子关联了已失效或封禁的直播间
- **Requirement**: 异常容错处理（隐式边界）
- **Priority**: Medium
- **Preconditions**:
  - 作者发布的某图文帖子绑定的直播间状态被管理后台终止或封禁
- **Test Steps**:
  1. 用户在前端刷到该关联帖子
  2. 观察直播关联组件状态并尝试点击
- **Expected Results**:
  - 组件UI降级展示为失效或置灰状态
  - 触发点击后弱提示“直播已结束/暂不可见”，拦截任何无效跳转
- **Postconditions**: 无实质页面跳转

### 4. State Transition Tests
Test cases covering state changes and workflows.

#### TC-ST-001: 卡片展示与过滤策略机制
- **Requirement**: 筛选置灰、未开始的直播不显示（含预约和已预约）、校验结果
- **Priority**: High
- **Preconditions**:
  - 配置3个不同生命周期的直播数据：A(直播中)、B(未开始/处于预约阶段)、C(后台配置置灰下架)
- **Test Steps**:
  1. 作为普通C端用户刷新首页/图文信息流
  2. 检查这三个直播对应的卡片能否被分发和展示出来
- **Expected Results**:
  - 直播 A：正常渲染直播中挂件和转跳入口
  - 直播 B：根据张亮便签“未开始的直播不显显⽰（含预约）”策略，B 彻底不显示任何预热卡片
  - 直播 C：根据“筛选置灰”设定，完全不分发或展示为过滤不可见状态
- **Postconditions**: 前端渲染结果符合各生命周期的过滤规则

## Test Coverage Matrix

| Requirement ID | Test Cases | Coverage Status |
|---------------|------------|-----------------|
| REQ-001 (帖子关联弹卡) | TC-F-001, TC-ERR-001 | ✓ Complete |
| REQ-002 (状态过滤/置灰规则) | TC-ST-001 | ✓ Complete |
| REQ-003 (直播挽留弹窗) | TC-F-002 | ✓ Complete |
| REQ-004 (广告埋点全链路追溯) | TC-F-003, TC-E-001, TC-E-002 | ✓ Complete |

## Notes
- `[便签]` 备注要求需要开发在联调阶段提供置灰后台或Mock手段协助 `TC-ST-001` 的校验。
- 广告位数据治理（埋点覆盖逻辑）需要数仓同学支持并在抓包阶段同步验收 `utmid` 字段。
