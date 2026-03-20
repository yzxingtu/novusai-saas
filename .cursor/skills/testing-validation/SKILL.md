---
name: testing-validation
description: NovusAI 测试与验证技能。当需要为 Service 编写单元测试、用 MCP 浏览器做页面验证、验证上传下载或插件页面回归时，参考此技能。
---

# 测试与验证技能

## 何时使用

- 为 `backend/tests/services/` 补或改单元测试
- 验证新页面、表单、列表、上传下载、插件 UI
- 做浏览器回归、控制台错误排查、网络请求检查
- 需要明确本项目的测试最小验收标准

## 后端测试规则

- 测试不依赖真实 DB、Redis、网络
- 优先复用 `tests/services/conftest.py`
- Service 用 `__new__` 实例化并手动注入依赖
- 每个 Service 文件至少覆盖正常、边界、异常三类分支
- 一般不少于 6 个 case，核心服务建议 10 个以上

## 浏览器验证规则

- 优先 `chrome-devtools`
- 文件上传、多标签页再使用 `playwright`
- 同一条流程不要混用两套浏览器 MCP
- 页面状态变化后重新 snapshot
- 先查 console/network，再判定页面问题

## 常用验证清单

- 表单能打开、填充、提交、报错
- 列表能查询、分页、删除、鉴权显示
- 上传能成功，下载能触发，权限或可见性正确
- 插件页面在启用、禁用、卸载后都符合预期

## 参考

- `../novusai-saas/references/testing-spec.md`
- `../novusai-saas/references/browser-testing-spec.md`
