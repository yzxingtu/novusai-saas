---
inclusion: manual
---

# DevGenius MCP 标准工作流

本项目通过 DevGenius MCP 进行项目管理。MCP 集成名称：`devgenius-quanzhan`。

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

写入文档规则：
- **先查后写**：用 `search_documents` 确认不存在
- 存在 → `update_document_by_id(document_id, content)` 更新
- 不存在 → `create_document(...)` 创建
- 禁止重复创建相同主题文档

---

## 完成任务

```
11. update_subtask_status(subtask_id, status="completed", notes="完成摘要")
12. [里程碑最后一个任务完成时] 编写功能使用文档
13. update_task_status(task_id, status="completed", version=N, notes="完成报告")
```

`notes` 必须包含：完成了什么、修改了哪些文件、测试状态。

---

## 完整流程图

```
新会话
  ├─ get_project_context
  ├─ get_my_tasks
  ├─ claim_task
  ├─ [复杂任务?] → split_task_into_subtasks
  ├─ search_documents → 阅读规范
  ├─ 开发
  ├─ [里程碑完成?] → 编写使用文档
  └─ update_task_status → completed
```

---

## MCP 工具速查

| 类别 | 工具 | 说明 |
|------|------|------|
| 上下文 | `get_project_context` | 项目信息 + 任务 |
| 任务 | `get_my_tasks` | 我的任务 |
| | `claim_task` | 认领（锁 120 分钟） |
| | `update_task_status` | 更新状态 |
| 子任务 | `split_task_into_subtasks` | 拆分 |
| | `update_subtask_status` | 更新子任务 |
| 文档 | `search_documents` | 搜索 |
| | `create_document` | 创建 |
| | `update_document_by_id` | 更新 |
| 里程碑 | `list_project_milestones` | 列表 |
| | `create_milestone` | 创建 |
