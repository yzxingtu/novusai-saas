# AI 架构规则（强制）

> 本规则适用于 NovusAI SaaS 项目中所有涉及 AI 功能的开发。违反任何一条均视为代码缺陷。

## 一、核心原则：Agent→Skill 全链路

**所有 AI 功能必须通过 Agent 调度 Skill 完成，禁止直接调用 AIGateway。**

```
外部请求 → Agent.run() → Skill.execute() → AIGateway → LLM Provider
```

### 禁止事项

- ❌ 在 Controller/Service 层直接实例化 `AIGateway` 发起 LLM 调用
- ❌ 新增绕过 Agent→Skill 链路的 AI 端点
- ❌ 在非 engine 层代码中 `from app.ai.gateway import AIGateway`

### 允许事项

- ✅ Agent engine 内部的 LLM 调用（`conversation.py` / `base.py` / `task.py`）— 属于 Agent 实现层
- ✅ `AIGateway.test_model` — 仅限模型连通性测试，不用于业务功能

## 二、技能（Skill）体系

### 技能包是一级管理单元

- 技能（Skill）**必须**归属于某个技能包（SkillPackage）
- `package_id` 为必填外键，不可为空

### 前端统一入口（禁止独立技能路由）

- `/admin/ai/skill-packages` — 管理端唯一技能管理入口
- `/tenant/ai/skill-packages` — 租户端唯一技能管理入口
- **禁止**存在独立的 `/admin/ai/skills` 或 `/tenant/ai/skills` 页面
- 技能包详情页内嵌技能 CRUD（新增/编辑/删除/排序）
- 新建技能时 `package_id` 自动填充，用户无需手动选择

### 技能类型（SkillTypeEnum）

| 类型 | 说明 | Executor |
|------|------|----------|
| `toolkit` | Python 工具包（Tools 类） | ToolkitExecutor |
| `knowledge_base` | 知识库检索（RAG） | 无（RAG 注入 system_prompt） |
| `data_intelligence` | 数据智能（Text-to-SQL + CRUD） | TextToSQLExecutor |
| `builtin` | 内置函数 | BuiltinToolExecutor |

未知类型走插件解析路径（PluginExecutor）。

### Toolkit 技能（toolkit 类型）

- 编写 Python 源码，定义 `Tools` 类，每个公开方法自动映射为一个 LLM 可调用工具
- 字段：`toolkit_content`（Text）存储 Python 源码，`toolkit_meta`（JSON）存储解析结果
- 支持 Valves 配置：通过 `valves_schema` 动态渲染配置表单
- 前端编辑器：Monaco Editor + 实时解析预览 + ZIP 上传

## 三、系统 Agent 与系统 Skill

- 系统级 Agent/Skill 标记 `is_system=True`，**不可删除/禁用**
- 通过 seed migration 创建，`scope=admin`，`tenant_id=NULL`
- 前端管理页面中系统记录有特殊标识（锁图标），操作按钮隐藏

## 四、新增 AI 功能标准流程

```
1. 定义 Skill 类型（如已有类型可复用则跳过）
2. 新增 SkillTypeEnum 枚举值 + i18n
3. 实现 Executor（继承 BaseToolExecutor）
4. 在 resolver.py 注册类型→Executor 映射
5. 创建 Skill 记录（可通过 migration 或 API）
6. 将 Skill 绑定到 Agent（AgentSkillBinding）
7. 通过 Agent 对话或 Agent.run() 触发 Skill
```

**禁止跳过步骤直接调用 AIGateway 实现 AI 功能。**

## 五、关键文件索引

| 文件 | 说明 |
|------|------|
| `backend/app/enums/agent.py` | SkillTypeEnum 定义 |
| `backend/app/ai/tools/executors/` | 所有 Executor 实现 |
| `backend/app/ai/skills/resolver.py` | 类型→Executor 注册 |
| `backend/app/models/ai/skill.py` | Skill ORM 模型 |
| `backend/app/models/ai/skill_package.py` | SkillPackage ORM 模型 |
| `backend/app/ai/engine/conversation.py` | Agent 对话引擎（允许内部 LLM 调用） |
| `backend/app/ai/gateway.py` | AI 网关（仅由 Executor/Engine 调用） |
