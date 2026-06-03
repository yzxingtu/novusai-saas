# 菜单多语言规范 / Menu i18n rules

## 核心原则

菜单标题的来源必须先分清“宿主菜单”和“插件菜单”，两者不是一套模型。

| 场景 | 真相来源 | 文件位置 |
|------|----------|----------|
| 宿主 admin / tenant / user 动态菜单标题 | **后端** `menu.json` | `backend/app/locales/en/menu.json`、`backend/app/locales/zh_CN/menu.json` |
| 插件菜单标题 | **插件 manifest** `pages[*].menu.title` | `backend/plugins/{name}/plugin.yaml` |
| 插件页面标题 | **插件 manifest** `pages[*].title` | `backend/plugins/{name}/plugin.yaml` |
| 用户端静态路由页面标题（如 ai-chat、settings） | 前端 locales | `frontend/.../locales/.../user.json` |
| 插件页面内部文案（按钮、表单、提示等） | 插件前端 locales | `registerLocale(locale, 'plugin.{manifest-name}', messages)` |

## 宿主菜单规则

- admin / tenant / user 的宿主动态菜单标题由后端权限系统翻译，前端消费 API 返回的已翻译 `name`
- 宿主菜单新增、改名、多语言补齐时，只改 `backend/app/locales/*/menu.json`
- 用户端静态路由标题不属于后端动态菜单，继续放前端 `user.*` 命名空间

## 插件菜单规则

- 插件菜单标题只来自 `plugin.yaml -> extensions.frontend.pages[*].menu.title`
- 插件页面标题只来自 `plugin.yaml -> extensions.frontend.pages[*].title`
- 插件页面内部业务文案才走 `registerLocale(locale, 'plugin.{manifest-name}', ...)`
- 插件 manifest 中的 `title` 与 `menu.title` 必须同时补齐 `zh-CN` 与 `en`
- 插件前端必须至少注册一个与 `manifest.name` 一致的 canonical prefix；legacy alias 只作为兼容副本

## 禁止行为

- 禁止把插件菜单标题写进 `backend/app/locales/*/menu.json`
- 禁止在前端 `menu.*` 命名空间里重复维护宿主动态菜单标题
- 禁止用 `$t('menu.admin.xxx')`、`$t('menu.tenant.xxx')` 驱动插件菜单标题
- 禁止只翻译插件页面内部文案，却漏掉 manifest 里的 `pages[*].title` 或 `pages[*].menu.title`

## 验收要求

- 宿主菜单：切语言后 `/permissions/menus` 返回的新语言标题必须直接反映到 sidebar
- 插件菜单：切语言后必须同时刷新 `/permissions/menus`、`/plugins/slots` 和当前活动 route meta，确保 sidebar、breadcrumb、document.title、页面主标题同步更新
