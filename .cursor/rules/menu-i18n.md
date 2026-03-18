# 菜单多语言规范 / Menu i18n rules

## 核心原则

**侧边栏动态菜单的标题由后端统一翻译，禁止在前端 locales 中维护 menu.* 翻译。**

| 职责 | 负责方 | 文件位置 |
|------|--------|----------|
| admin / tenant / user 侧边栏菜单标题 | **后端** | `backend/app/locales/en/menu.json`、`backend/app/locales/zh_CN/menu.json` |
| 用户端静态路由页面标题（如 ai-chat、settings） | 前端 | `frontend/.../locales/.../user.json`（如 `user.aiChat.title`、`user.settings.title`） |
| 其他页面文案（表格、表单、提示等） | 前端 | 各自模块的 `admin/`、`tenant/`、`shared/` 下的 JSON |

## 禁止行为

- ❌ 在 `frontend/.../locales/.../menu.json` 中维护菜单翻译
- ❌ 使用 `$t('menu.admin.xxx')`、`$t('menu.tenant.xxx')` 获取动态菜单标题（菜单数据由 API 返回，已包含翻译后的 `name`）
- ❌ 新增 CRUD 模块时在前端添加 menu 翻译（codegen 及后续维护只改后端 menu.json）

## 正确做法

- ✅ 新增菜单/权限时，在 **后端** `backend/app/locales/en/menu.json` 和 `backend/app/locales/zh_CN/menu.json` 的 `menu.admin` 或 `menu.tenant` 下添加对应 key
- ✅ 用户端静态路由（非后端菜单驱动的页面）用 `user.*` 等业务命名空间，如 `user.settings.title`、`user.aiChat.title`
- ✅ codegen 生成新资源时，将 `menu.admin.{resource}`、`menu.tenant.{resource}` 合并进后端 menu.json
