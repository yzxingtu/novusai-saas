# NovusDoc — AI Document Editor

NovusAI 平台的现代化 AI 富文本编辑器插件（免费社区版）。

## Features

- **Tiptap Editor** — 块级富文本编辑（StarterKit、表格、图片、链接、代码块、任务列表、上下标、高亮、文本对齐）
- **Document Management** — 文档 CRUD，文件夹树形管理，标签，收藏
- **AI Writing Assistant** — 续写、优化、校对、翻译、摘要、扩写、改写、自定义 Prompt、侧栏对话（SSE 流式）
- **Slash Commands** — `/` 菜单快速插入块（标题、列表、引用、代码块、表格等）
- **Full-text Search** — PostgreSQL GIN 索引全文搜索
- **Image Upload** — 拖拽/粘贴/文件选择，通过平台存储服务
- **Export** — HTML 和 Markdown 文件下载导出
- **Auto Save** — 可配置间隔（默认 3 秒节流）
- **Dual Route** — 列表页 `/docs` + 编辑页 `/docs/:docId`（支持深链接、浏览器前进后退）

### Roadmap / Not Yet Implemented

- ~~Outline Panel~~ — 目录大纲（规划中）
- Word/PDF 导出 — 由 **novusdoc-pro** 商业版提供

## Installation

1. 管理后台 → 插件 → 上传 `novusdoc.zip`
2. 点击 **启用**
3. 分配给企业（scope: `assigned_tenants`）

## Development

```bash
# 后端校验
cd backend
python scripts/plugin_cli.py validate plugins/novusdoc

# 前端开发模式（Vite 自动编译）
cd frontend && pnpm dev

# 前端 UMD 构建（生产）
cd backend/plugins/novusdoc/frontend
npm install && npx vite build
```

## Architecture

- **Plugin name**: `novusdoc`
- **DB table prefix**: `px_novusdoc_*`
- **Alembic branch**: `plugin_novusdoc`
- **i18n prefix**: `plugin.novusdoc.*`
- **API path**: `/tenant/plugins/novusdoc/api/*`
- **CSS prefix**: `.nd-*`
- **Pricing**: Free (community edition)

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `docs` | 文档列表（分页/筛选/排序） |
| POST | `docs` | 创建文档 |
| GET | `docs/{doc_id}` | 文档详情 |
| PUT | `docs/{doc_id}` | 更新文档 |
| DELETE | `docs/{doc_id}` | 删除文档 |
| GET | `folders` | 文件夹列表（树形） |
| POST | `folders` | 创建文件夹 |
| PUT | `folders/{id}` | 更新文件夹 |
| DELETE | `folders/{id}` | 删除文件夹 |
| GET | `search` | 全文搜索 |
| POST | `upload` | 图片上传 |
| GET | `tags` | 标签列表 |
| POST | `tags` | 创建标签 |
| DELETE | `tags/{id}` | 删除标签 |
| GET | `docs/{doc_id}/export/html` | 导出 HTML |
| GET | `docs/{doc_id}/export/markdown` | 导出 Markdown |
| POST | `docs/{doc_id}/ai/*` | AI 功能（9 种） |

## Related

- **novusdoc-pro** — 商业扩展插件（实时协作、评论批注、版本历史、文档权限、分享链接、Word/PDF 导出、模板）
