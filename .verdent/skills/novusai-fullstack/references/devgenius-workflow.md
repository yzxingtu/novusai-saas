# DevGenius MCP 标准工作流

本项目通过 DevGenius MCP 进行项目管理。MCP 集成名称：`devgenius-quanzhan`。

所有工具前缀：`mcp_devgenius-quanzhan_`

---

## 启动任务

```
1. get_project_context          → 获取项目信息、任务列表、配置
2. get_my_tasks                 → 查看分配给自己的任务
3. claim_task(task_id)          → 认领任务（锁定 120 分钟）
4. get_task_detail(task_id)     → 查看验收标准、子任务、备注
```

若任务复杂（预计 >2 小时 或 涉及多模块），必须拆分：

```
5. split_task_into_subtasks(task_id, subtasks=[...])
6. update_subtask_status(subtask_id, status="in_progress")
```

---

## 开发前查文档

```
7. search_documents(query="相关关键词")     → 搜索规范/设计文档
8. get_document_by_id(document_id)          → 阅读文档内容
```

若无相关规范文档，引导用户创建或自行创建：

```
9.  get_document_categories()                → 获取分类列表
10. create_document(title, content, category) → 创建文档
```

写入文档规则：
- **先查后写**：用 `search_documents` 确认不存在
- 存在 → `update_document_by_id(document_id, content)` 更新
- 不存在 → `create_document(...)` 创建
- 禁止重复创建相同主题文档

---

## 完成任务

```
11. update_subtask_status(subtask_id, status="completed", notes="完成摘要")
12. update_task_status(task_id, status="completed", version=N, notes="完成报告")
```

`notes` 必须包含：完成了什么、修改了哪些文件、测试状态。

---

## 里程碑管理（按需）

```
list_project_milestones()                    → 查看里程碑列表
get_milestone_detail(milestone_id)           → 查看里程碑详情
create_milestone(name, tasks=[...])          → 创建里程碑（推荐同时创建任务）
create_milestone_tasks(milestone_id, tasks)  → 追加任务
```

---

## 完整流程图

```
新会话
  │
  ├─ get_project_context
  ├─ get_my_tasks
  ├─ claim_task
  │
  ├─ [复杂任务?] → split_task_into_subtasks
  │
  ├─ search_documents → 阅读规范
  │   └─ [无规范?] → 引导创建 / create_document
  │
  ├─ 开发（遵循前后端规范 §二 §三）
  │   ├─ update_subtask_status → in_progress / completed
  │   └─ [重大变更?] → update_document / create_document
  │
  └─ update_task_status → completed（附完成报告）
```

---

## MCP 工具速查

| 类别 | 工具 | 说明 |
|------|------|------|
| **上下文** | `get_project_context` | 项目信息 + 任务 |
| | `get_project_summary` | 轻量概览 |
| **任务** | `get_my_tasks` | 我的任务 |
| | `claim_task` | 认领（锁 120 分钟） |
| | `update_task_status` | 更新状态 |
| | `get_task_detail` | 任务详情 |
| **子任务** | `split_task_into_subtasks` | 拆分 |
| | `get_task_subtasks` | 查看子任务 |
| | `update_subtask_status` | 更新子任务 |
| **文档** | `search_documents` | 搜索 |
| | `list_documents` | 列表 |
| | `get_document_by_id` | 读取 |
| | `create_document` | 创建 |
| | `update_document_by_id` | 更新 |
| | `get_document_categories` | 分类列表 |
| | `create_document_category` | 创建分类 |
| **里程碑** | `list_project_milestones` | 列表 |
| | `get_milestone_detail` | 详情 |
| | `create_milestone` | 创建 |
| | `create_milestone_tasks` | 追加任务 |
