# NovusDoc — AI 文档编辑器

NovusAI 平台的现代化 AI 富文本编辑器插件（免费社区版）。

## 功能

- **Tiptap 编辑器** — 块级富文本编辑（StarterKit、表格、图片、链接、代码块、任务列表、上下标、高亮、文本对齐）
- **文档管理** — 文档 CRUD，文件夹树形管理，标签，收藏
- **AI 写作助手** — 续写、优化、校对、翻译、摘要、扩写、改写、自定义 Prompt、侧栏对话（SSE 流式）
- **斜杠命令** — `/` 菜单快速插入块（标题、列表、引用、代码块、表格等）
- **全文搜索** — PostgreSQL GIN 索引全文搜索
- **图片上传** — 拖拽/粘贴/文件选择，通过平台存储服务
- **导出** — HTML 和 Markdown 文件下载导出
- **自动保存** — 可配置间隔（默认 3 秒节流）
- **双路由** — 列表页 `/docs` + 编辑页 `/docs/:docId`（支持深链接、浏览器前进后退）

### 规划中 / 未实现

- ~~目录大纲~~ — 规划中
- Word/PDF 导出 — 由 **novusdoc-pro** 商业版提供

## 安装

1. 管理后台 → 插件 → 上传 `novusdoc.zip`
2. 点击 **启用**
3. 分配给企业（scope: `assigned_tenants`）

## 开发

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

## 架构

- **插件名**: `novusdoc`
- **DB 表前缀**: `px_novusdoc_*`
- **Alembic 分支**: `plugin_novusdoc`
- **i18n 前缀**: `plugin.novusdoc.*`
- **API 路径**: `/tenant/plugins/novusdoc/api/*`
- **CSS 前缀**: `.nd-*`
- **定价**: 免费（社区版）

## 相关

- **novusdoc-pro** — 商业扩展插件（实时协作、评论批注、版本历史、文档权限、分享链接、Word/PDF 导出、模板）
