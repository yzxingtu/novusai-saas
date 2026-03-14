# NovusDoc Pro — Collaboration Extension

NovusDoc 商业扩展插件，为 NovusDoc 编辑器增加实时协作、评论批注、版本历史、文档权限、分享链接、Word/PDF 导出、文档模板等能力。

## Features

- **Real-time Collaboration** — Yjs + Socket.IO 实时多人协作编辑
- **Comments** — 行内评论批注、回复、标记已解决
- **Version History** — 版本快照创建、查看、恢复
- **Document Members** — 文档级成员权限管理（owner/editor/commenter/viewer）
- **Share Links** — 生成分享链接，支持过期时间与撤销
- **Word/PDF Export** — 导出为 Word/PDF 格式（stub，待实装）
- **Templates** — 文档模板管理

## Collaboration Role Policy

- **仅 tenant_admin 可参与协作**（编辑、评论、查看）
- tenant_user **不支持**进入协作会话（Socket.IO auth_scopes 限制）
- 匿名用户可通过分享链接只读查看文档（public_routes）

## Installation

1. 确保 `novusdoc` 插件已安装并启用（依赖）
2. 管理后台 → 插件 → 上传 `novusdoc-pro.zip`
3. 点击 **启用**
4. 分配给企业（scope: `assigned_tenants`）

## Architecture

- **Plugin name**: `novusdoc-pro`
- **DB table prefix**: `px_novusdoc_pro_*`
- **Alembic branch**: `plugin_novusdoc_pro`
- **i18n prefix**: `plugin.novusdoc-pro.*`
- **API path**: `/tenant/plugins/novusdoc-pro/api/*`
- **CSS prefix**: `.ndp-*`
- **Socket.IO namespace**: `/plugin/novusdoc-pro/collab`
- **Pricing**: Paid (¥9999 CNY, 14-day trial)

## Permission Actions

| Action | Description |
|--------|-------------|
| `collab` | 实时协作连接 |
| `comment` | 创建/编辑/删除/解决评论 |
| `share` | 创建/撤销分享链接 |
| `export` | Word/PDF 导出/导入 |
| `manage_members` | 添加/更新/移除文档成员 |

## Dependencies

- **novusdoc** plugin (required)
- **y-py** >= 0.6.0 (used for collaboration persistence; on Windows + Python 3.12 the plugin enables in degraded mode without persistence)
