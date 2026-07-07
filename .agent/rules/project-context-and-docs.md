---
trigger: model_decision
description: 项目背景与文档位置
---
# 项目与文档

- NovusAI SaaS 是多租户 AI SaaS 开发框架，包含平台端、企业端、用户端、RBAC、插件、Agent/Skill/AIGateway、Socket.IO、附件存储、代码生成和 Alembic 迁移。
- 开始开发前先读 `README.md`；涉及已有设计时查 `docs/` 和相关源码。
- 人工维护文档放 `docs/`，按主题归档；根目录不新增散落 `.md`，`README.md` 与 agent 入口文件除外。
- 代码行为、接口、配置、部署或规则变化时，同步更新对应文档。
- `.qoder/repowiki/` 是 Qoder 自动生成的知识索引，只在代码结构变化且确有必要时更新。
- 文档与代码冲突时，先按源码确认事实，再更新文档。
