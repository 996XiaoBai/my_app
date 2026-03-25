# 测试平台 Web 工作台

该目录是测试平台的 Next.js 前端工作台，对接本地 FastAPI 服务 `http://localhost:8000`。

## 启动方式

推荐从仓库根目录统一启动整套 Web 工作台：

```bash
./start.sh
```

它会同时启动：

1. FastAPI：`8000`
2. Next.js：`3000`

如果只想单独启动前端：

```bash
cd test_platform/web
npm run dev
```

## 常用命令

```bash
cd test_platform/web
npm run lint
npm test
npm run build
```

## 说明

- 前端当前使用 Node 原生测试运行 `src/**/*.test.ts`
- API 基础地址定义在 `src/lib/apiConfig.ts`
- 稳定导航模块的模式映射已经通过前端别名与后端统一
- 当前稳定测试工程模块已经包含“测试用例”和“测试用例评审”
- 测试用例页支持将当前生成结果一键送审到测试用例评审页

## 相关文档

- `test_platform/docs/本地开发指南.md`
- `test_platform/docs/测试平台技术文档.md`
- `docs/superpowers/specs/2026-03-23-test-case-review-design.md`
