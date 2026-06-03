# 浏览器测试规范（MCP）

> 使用 MCP 浏览器工具进行前端页面功能验证时，遵循以下规范。

## 目录

- [〇、MCP 工具优先级](#〇mcp-工具优先级)
- [一、环境信息](#一环境信息)
- [二、登录凭据](#二登录凭据)
- [三、测试步骤规范](#三测试步骤规范)
- [四、注意事项](#四注意事项)

## 〇、MCP 工具优先级

| 优先级 | 工具 | 说明 |
|--------|------|------|
| **1（首选）** | `chrome-devtools` MCP | 直接操控 Chrome DevTools，支持网络请求检查、控制台、性能分析、DOM 快照 |
| **2（备选）** | `playwright` MCP | Playwright 自动化，适合完整的 E2E 流程测试 |

**选择原则：**
- 日常页面验证、表单填写、点击操作 → 优先 `chrome-devtools`（`take_snapshot` / `click` / `fill` / `navigate_page`）
- 需要文件上传（`browser_file_upload`）、多标签页管理 → 使用 `playwright`
- 两者工具名前缀不同：chrome-devtools 无前缀（如 `take_snapshot`），playwright 带 `browser_` 前缀（如 `browser_snapshot`）
- **不要混用**：一次测试流程中只使用一个 MCP 工具，避免浏览器状态冲突

## 一、环境信息

| 项目 | 值 |
|------|-----|
| 前端 Dev Server | `http://localhost:5666` |
| 后端 API Server | `http://localhost:8000` |
| 平台管理端路径前缀 | `/admin/*` |
| 企业端路径前缀 | `/tenant/*` |

## 二、登录凭据

### 平台管理员（Admin）

| 字段 | 值 |
|------|-----|
| 登录页 | `http://localhost:5666/admin/login` |
| 用户名 | `admin` |
| 密码 | `admin123456` |

### 企业端（Tenant）

开发环境下企业端和管理端同样跑在 `localhost:5666`，登录路径固定为 `/tenant/login`。

| 字段 | 值 |
|------|-----|
| 登录页 | `http://localhost:5666/tenant/login` |
| 用户名 | `adminsss` |
| 密码 | `admin123456` |

> **备选方式**：也可通过平台管理端的企业列表"一键登录"（操作菜单 → 进入后台 / 当前标签页进入）进入企业端。

## 三、测试步骤规范

### 3.1 登录平台管理端

**chrome-devtools（首选）：**
```
1. navigate_page(type="url", url="http://localhost:5666/admin/login")
2. take_snapshot → 获取页面快照，找到输入框 uid
3. fill(uid=用户名uid, value="admin") + fill(uid=密码uid, value="admin123456")
4. click(uid=登录按钮uid)
5. wait_for(text=["概览"]) → 等待登录完成
```

**playwright（备选）：**
```
1. browser_navigate → http://localhost:5666/admin/login
2. browser_snapshot → 获取页面快照
3. browser_fill_form → 填入用户名 admin 和密码 admin123456
4. browser_click → 点击登录按钮
5. browser_wait_for → 等待页面跳转完成
```

### 3.2 登录企业端

**chrome-devtools（首选）：**
```
1. navigate_page(type="url", url="http://localhost:5666/tenant/login")
2. take_snapshot → 获取页面快照，找到输入框 uid
3. fill(uid=用户名uid, value="adminsss") + fill(uid=密码uid, value="admin123456")
4. click(uid=登录按钮uid)
5. wait_for(text=["概览"]) → 等待登录完成
```

**playwright（备选）：**
```
1. browser_navigate → http://localhost:5666/tenant/login
2. browser_snapshot → 获取页面快照
3. browser_fill_form → 填入用户名 adminsss 和密码 admin123456
4. browser_click → 点击登录按钮
5. browser_wait_for → 等待页面跳转完成
```

### 3.3 页面导航

**chrome-devtools：**
```
1. navigate_page(type="url", url="目标URL")
2. take_snapshot → 获取当前页面状态
3. 根据快照中的 uid 进行操作
```

**playwright：**
```
1. browser_navigate → 目标 URL
2. browser_snapshot → 获取当前页面状态
3. 根据快照中的 ref 进行操作
```

### 3.4 表单操作

**chrome-devtools：**
```
1. take_snapshot → 获取表单元素 uid
2. fill(uid, value) 或 fill_form → 填写表单字段
3. click(uid=提交按钮uid)
4. wait_for(text=["成功提示文本"])
```

**playwright：**
```
1. browser_snapshot → 获取表单元素 ref
2. browser_fill_form / browser_type → 填写表单字段
3. browser_click → 点击提交/保存按钮
4. browser_wait_for → 等待操作结果
```

### 3.5 文件上传测试

> 文件上传推荐使用 playwright MCP（chrome-devtools 不直接支持 file input 操作）

```
1. browser_snapshot → 找到上传按钮/区域
2. browser_click → 点击上传触发器（如 FilePicker 按钮或 ImageUpload 区域）
3. browser_file_upload → 上传测试文件
4. browser_wait_for → 等待上传完成
5. browser_snapshot → 验证上传结果
```

### 3.6 网络请求检查（chrome-devtools 专属）

```
1. list_network_requests(resourceTypes=["fetch", "xhr"]) → 查看 API 请求列表
2. get_network_request(reqid=请求ID) → 查看请求/响应详情
3. list_console_messages(types=["error"]) → 检查控制台错误
```

### 3.7 回收站专项回归

#### 管理端模块回收站

目标：确认管理端 CRUD 页面仍用统一弹窗，并可跳转总回收站。

```
1. navigate_page → 例如 http://localhost:5666/admin/ai/agents
2. take_snapshot → 打开页面工具栏中的回收站按钮
3. 验证弹窗内出现“查看总回收站”
4. list_network_requests(resourceTypes=["fetch", "xhr"]) → 确认 /admin/.../recycle-bin/count 与 /admin/.../recycle-bin?... 返回 200
5. 点击“查看总回收站” → wait_for(["总回收站"])
```

#### 企业端模块回收站

目标：确认企业端只有模块回收站，没有总回收站入口。

```
1. navigate_page → 例如 http://ss.dakkii.cn:5666/tenant/ai/knowledge-bases
2. take_snapshot → 打开页面工具栏中的回收站按钮
3. 验证弹窗文案为“转入管理端总回收站，由平台统一恢复或清理”
4. 验证弹窗内不存在“查看总回收站”
5. list_network_requests(resourceTypes=["fetch", "xhr"]) → 确认 /tenant/.../recycle-bin/count 与 /tenant/.../recycle-bin?... 返回 200
```

#### 管理端总回收站

目标：确认唯一总回收站在管理端加载正常。

```
1. navigate_page → http://localhost:5666/admin/system/recycle-bin
2. wait_for(["总回收站"])
3. list_network_requests(resourceTypes=["fetch", "xhr"]) → 确认：
   - /admin/recycle-bin/modules
   - /admin/recycle-bin/summary
   - /admin/recycle-bin?module=...&page[number]=1&page[size]=...
   均返回 200
```

#### 企业端不存在总回收站

目标：确认产品边界未被权限误放开。

```
1. navigate_page → http://ss.dakkii.cn:5666/tenant/system/recycle-bin
2. take_snapshot
3. 验证页面是 404 / 未找到页面，而不是可访问的回收站页面
```

#### 路由冲突排查

适用于像 `/{task_id}`、`/{id}` 这类动态路由较早注册的控制器。

```
1. 打开对应页面并进入模块回收站
2. list_network_requests(resourceTypes=["fetch", "xhr"])
3. 确认请求命中的是 /.../recycle-bin?...，状态是 200
4. 若出现 422 且错误类似 path.task_id / int_parsing，优先检查后端控制器里 recycle-bin 路由是否注册在动态路由之前
```

## 四、注意事项

- **snapshot 优先于 screenshot**：始终优先使用快照获取页面状态，仅在需要视觉验证时截图
- **元素引用可能过期**：页面状态变化后（导航、弹窗打开/关闭），之前的 `uid`/`ref` 可能失效，需重新 snapshot
- **等待加载**：页面导航或 AJAX 操作后，使用 `wait_for` 等待关键文本出现，避免操作未加载完成的页面
- **弹窗/Modal**：Ant Design Vue 的 Modal/Drawer 打开后需要重新 snapshot 获取弹窗内元素引用
- **错误处理**：操作失败时先检查 console messages（过滤 errors）排查前端错误
- **多标签页**：一键登录企业会打开新标签页，chrome-devtools 用 `select_page`，playwright 用 `browser_tabs` 管理
- **不要混用**：一次测试流程中只使用一个 MCP 工具（chrome-devtools 或 playwright），避免状态冲突
