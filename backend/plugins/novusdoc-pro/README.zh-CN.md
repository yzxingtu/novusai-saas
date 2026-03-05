# NovusDoc Pro — 协作增强插件

NovusDoc 商业扩展插件，为 NovusDoc 编辑器增加实时协作、评论批注、版本历史、文档权限、分享链接、Word/PDF 导出、文档模板等能力。

## 功能

- **实时协作** — 基于 Yjs + Socket.IO 的实时多人协作编辑
- **评论批注** — 行内评论批注、回复、标记已解决
- **版本历史** — 版本快照创建、查看、恢复
- **文档权限** — 文档级成员权限管理（所有者/编辑者/评论者/查看者）
- **分享链接** — 生成分享链接，支持过期时间与撤销
- **Word/PDF 导出** — 导出为 Word/PDF 格式
- **文档模板** — 文档模板管理

## 协作角色策略

- **仅 tenant_admin 可参与协作**（编辑、评论、查看）
- tenant_user **不支持**进入协作会话（Socket.IO auth_scopes 限制）
- 匿名用户可通过分享链接只读查看文档（public_routes）

## 安装

1. 确保 `novusdoc` 插件已安装并启用（前置依赖）
2. 管理后台 → 插件 → 上传 `novusdoc-pro.zip`
3. 点击 **启用**
4. 分配给租户（scope: `assigned_tenants`）

## 架构

- **插件名**: `novusdoc-pro`
- **DB 表前缀**: `px_novusdoc_pro_*`
- **Alembic 分支**: `plugin_novusdoc_pro`
- **i18n 前缀**: `plugin.novusdoc-pro.*`
- **API 路径**: `/tenant/plugins/novusdoc-pro/api/*`
- **CSS 前缀**: `.ndp-*`
- **Socket.IO 命名空间**: `/plugin/novusdoc-pro/collab`
- **定价**: 付费（14 天免费试用）

## 权限动作

| 动作 | 说明 |
|------|------|
| `collab` | 实时协作连接 |
| `comment` | 创建/编辑/删除/解决评论 |
| `share` | 创建/撤销分享链接 |
| `export` | Word/PDF 导出/导入 |
| `manage_members` | 添加/更新/移除文档成员 |

## 依赖

- **novusdoc** 插件（必需）
- **y-py** >= 0.6.0（用于协作持久化；在 Windows + Python 3.12 下将以降级模式启用，不提供持久化）
