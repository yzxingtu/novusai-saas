# NovusAI SaaS

现代化 AI 集成 SaaS 开发框架，基于 Python + Vue 构建。

## 技术栈

### 后端
- **Python 3.10+** - 核心语言
- **FastAPI** - Web 框架
- **SQLAlchemy 2.0** - ORM
- **PostgreSQL** - 主数据库
- **Redis** - 缓存与消息队列
- **Celery** - 异步任务队列
- **Alembic** - 数据库迁移

### 前端
- **Vue.js 3.x** - 前端框架
- **TypeScript** - 类型安全
- **Vite** - 构建工具
- **Ant Design Vue** - UI 组件库
- **Pinia** - 状态管理
- **Vue Router** - 路由管理
- **vue-i18n** - 国际化

## 项目结构

```
novusai-saas/
├── backend/                 # 后端项目目录
│   ├── app/                # 应用源码
│   │   ├── api/           # API 路由层
│   │   │   └── v1/       # API v1 版本
│   │   ├── core/         # 核心配置与基础设施
│   │   ├── models/       # 数据库模型
│   │   ├── services/     # 业务逻辑服务层
│   │   ├── schemas/      # Pydantic 数据验证模型
│   │   ├── utils/        # 工具函数
│   │   ├── middleware/   # 中间件
│   │   ├── tasks/        # Celery 异步任务
│   │   └── websocket/    # WebSocket 处理器
│   ├── migrations/        # Alembic 数据库迁移
│   └── tests/             # 后端测试
│
├── frontend/               # 前端项目目录
│   ├── src/               # 源码目录
│   │   ├── api/          # API 请求模块
│   │   ├── assets/       # 静态资源
│   │   ├── components/   # 通用组件
│   │   ├── composables/  # 组合式函数
│   │   ├── layouts/      # 布局组件
│   │   ├── locales/      # 国际化文件
│   │   ├── router/       # 路由配置
│   │   ├── stores/       # Pinia 状态管理
│   │   ├── styles/       # 全局样式
│   │   ├── types/        # TypeScript 类型
│   │   ├── utils/        # 工具函数
│   │   └── views/        # 页面视图
│   └── public/            # 公共静态文件
│
├── docs/                   # 项目文档
│   ├── api/               # API 文档
│   ├── guides/            # 开发指南
│   └── architecture/      # 架构设计文档
│
├── scripts/                # 脚本工具
│   ├── deploy/            # 部署脚本
│   ├── dev/               # 开发辅助脚本
│   └── migration/         # 迁移脚本
│
├── shared/                 # 前后端共享资源
│   ├── types/             # 共享类型定义
│   └── constants/         # 共享常量
│
├── .gitignore             # Git 忽略配置
├── .warp/                 # Warp Agent 配置
└── README.md              # 项目说明（本文件）
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 6+
- Docker（可选，用于 PostgreSQL / Redis / Prometheus / Grafana）

### Docker 依赖服务（推荐）

```bash
# 在项目根目录启动 PostgreSQL、Redis、Prometheus、Grafana
docker compose -f docker-compose.dev.yml up -d
```

包含：PostgreSQL(5432)、Redis(6379)、Prometheus(9090)、Grafana(3000)。开发环境下 Grafana 会自动配置为 `http://localhost:3000`，监控页 Grafana Tab 可直接使用。

### 后端开发

```bash
# 进入后端目录
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -e .  # 或 pip install -r requirements.txt
# 安装 -e . 后可获得 novusai CLI

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件配置数据库等

# 运行数据库迁移（启动时也会自动执行）
novusai db upgrade head

# 启动开发服务器
novusai run --reload
# 另开终端启动 Celery Worker + Beat
novusai celery dev
# 启动前端
pnpm dev:antd
```

### 前端开发

```bash
# 进入前端目录
cd frontend

# 安装依赖
pnpm install  # 或 npm install

# 配置环境变量
cp .env.example .env.local
# 编辑 .env.local 配置 API 地址

# 启动开发服务器
pnpm dev  # 或 npm run dev
```

## 分支策略

本项目采用 Git Flow 分支模型：

- `main` - 生产环境分支，只接受 release 分支合并
- `develop` - 开发主分支，日常开发基于此分支
- `feature/backend-xxx` - 后端功能分支
- `feature/frontend-xxx` - 前端功能分支
- `release/vX.X.X` - 发布分支
- `hotfix/xxx` - 紧急修复分支

### 开发流程

1. 从 `develop` 分支创建功能分支
2. 在功能分支上开发
3. 提交 Pull Request 到 `develop`
4. Code Review 通过后合并

## 开发规范

请参阅 `docs/guides/` 目录下的开发规范文档：

- [后端开发规范](docs/guides/backend-development.md)
- [前端开发规范](docs/guides/frontend-development.md)
- [API 设计规范](docs/guides/api-design.md)
- [Git 提交规范](docs/guides/git-commit.md)

注释须中英双语（见 [注释规范补全清单](docs/comment-compliance-remaining.md)）。

## 许可证

MIT License
