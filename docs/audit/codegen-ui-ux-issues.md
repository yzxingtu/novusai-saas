# Codegen 代码生成器 — UI/UX 问题记录

> 在浏览器自动化测试过程中发现的问题，包含 UI 表现、UX 流程、操作流畅性、易理解度等维度。

---

## 一、已发现问题

### 1. Step 4 端点配置 — 排序字段 min/max 配置错误

**位置**: Step 4 端点配置 > 菜单排序 (spinbutton)

**现象**: `valuemax="0"` 与 `valuemin="0"` 相同，导致排序字段无法增加或减少。

**影响**: 用户无法通过控件调整菜单排序值。

**建议**: 修正 InputNumber / spinbutton 的 `min`/`max` 配置，例如 `min=0, max=999`。

---

### 2. Step 6 预览与生成 — 缺少独立「校验配置」按钮 ✅ 已修复

**位置**: Step 6 预览与生成

**修复**: 新增「校验配置」按钮，单独调用 `doValidate()`，通过时提示「校验通过」，失败时在原有校验错误 Alert 中展示。

---

### 3. Step 6 生成摘要数字波动

**位置**: Step 6 预览摘要（新建/修改/总行数）

**现象**: 测试中观察到 `新建: 6→12`、`总行数: 462→999` 等数值在短时间内变化。

**影响**: 若为异步加载导致，可能造成用户困惑；若为实时重算，需确保稳定性。

**建议**: 确认预览数据来源与更新时机，必要时增加 loading 状态或防抖。

---

### 4. 右侧预览面板在 a11y 快照中未体现 ✅ 已修复

**位置**: 向导主区域右侧 45% 区域

**现象**: 使用 chrome-devtools `take_snapshot` 获取的可访问性树中，未发现「代码」「表单」「表格」Tab 及文件树等预览相关元素。

**修复**: 将右侧预览 Card 包裹在 `<section role="region" aria-label="代码预览面板" />` 中，增加 `regionLabel` 国际化文案（zh: 代码预览面板 / en: Code Preview Panel），使屏幕阅读器与自动化工具能识别该区域。

---

### 5. Step 1 模块下拉 —  placeholder 与必填校验易混淆

**位置**: Step 1 基础信息 > 模块 (Select)

**现象**: 模块下拉默认展示「系统」，用户易误以为已选。实际 store 中 `module` 可能为空，保存草稿时弹出「模块为必填项」。

**影响**: 操作不流畅，需用户额外点击下拉并选中「系统」才能通过校验。

**建议**: 
- 将默认值写入 store（如 `system`），或
- 在 placeholder 与已选值之间做清晰区分，或
- 在保存前对必填项做即时校验并高亮

---

### 6. YAML 导入 — 最小有效配置仍校验失败 ✅ 已修复

**位置**: Step 1 > 导入 YAML 弹窗

**原因**: `POST /admin/codegen/validate` 将完整 body `{ config_json: {...} }` 直接传给 service.validate，未提取 `config_json`，导致 parser 从顶层取 module/resource 为空。

**修复**: 后端 `codegen.py` validate_config 中提取 `config = body.get("config_json") or body` 再传入 validate。

---

### 7. 不存在的配置 ID — 控制台未捕获的 Promise 异常

**位置**: 访问 `/admin/system/codegen/99999/edit`

**现象**: 页面正确显示「配置不存在」错误提示；但控制台出现 `Uncaught (in promise)` 及 `Failed to load resource: 404`。

**影响**: 404 为预期响应，但前端未妥善 catch，导致控制台污染、可能影响错误监控。

**建议**: 在获取配置详情的 API 调用处 catch 404，用 `message.error` 等方式提示，避免未处理的 Promise rejection。

---

## 二、待进一步验证

- 字段编辑器拖拽排序的可用性
- 列表页操作列（编辑/复制/下载/删除）在 a11y 树中为 `ignored`，可能位于下拉菜单内

---

## 三、测试环境

- 前端: `http://localhost:5666`
- 后端: `http://localhost:8000`
- 测试工具: chrome-devtools MCP
- 测试日期: 2026-03-17
