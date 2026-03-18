# CRUD 代码生成器 — 浏览器自动化测试方案（Chrome DevTools MCP）

> 本方案严格遵循 `.cursor/skills/novusai-saas/references/browser-testing-spec.md`，**仅使用 chrome-devtools MCP**，禁止使用 Playwright MCP。

## 工具映射表

| 原 Playwright 工具 | Chrome DevTools 工具 | 用途 |
|-------------------|---------------------|------|
| `browser_navigate` | `navigate_page` | 导航到 URL |
| `browser_snapshot` | `take_snapshot` | 获取页面可访问性快照（获取 uid） |
| `browser_take_screenshot` | `take_screenshot` | 截图 |
| `browser_click` | `click` | 点击元素（需 uid） |
| `browser_type` / `browser_fill_form` | `fill` / `fill_form` | 输入/填表 |
| `browser_select_option` | `fill`（select 元素） | 选择下拉选项 |
| `browser_press_key` | `press_key` | 按键操作 |
| `browser_drag` | `drag` | 拖拽 |
| `browser_wait_for` | `wait_for` | 等待文本出现 |
| `browser_network_requests` | `list_network_requests` | 检查网络请求 |
| `browser_console_messages` | `list_console_messages` | 检查控制台 |
| `browser_evaluate` | `evaluate_script` | 执行 JS |

**元素引用**：chrome-devtools 使用 `uid`（非 Playwright 的 `ref`）。

## 测试环境

- 前端：`http://localhost:5666`
- 后端：`http://localhost:8000`
- 登录：`admin` / `admin123456`
- 目标：`/admin/system/codegen`

## 测试用例速查（TC-01 ~ TC-22）

与主方案 `codegen浏览器自动化测试方案` 的步骤一致，仅将工具名替换为上表映射。

### 批次 1：TC-01 ~ TC-05

- **TC-01**：`navigate_page` → 登录页 → `take_snapshot` → `fill_form` → `click` 登录 → `wait_for`
- **TC-02**：`navigate_page` → `/admin/system/codegen` → `take_snapshot` → `list_network_requests`
- **TC-03**：`click` 新建 → `take_snapshot` 验证 Step 1
- **TC-04**：`fill` resource / display_name → 验证自动推导
- **TC-05**：`click` 预设下拉 → 选择 simple → `take_snapshot` 验证预填充

### 批次 2 ~ 4

参见主方案，所有 `browser_*` 均替换为 chrome-devtools 对应工具。
