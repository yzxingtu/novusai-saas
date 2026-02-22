# 技能包架构全景 — 深度代码审查报告

> 生成时间：2026-02-22 | 基于实际源码逐行审计

---

## 一、数据模型层（ER 关系图）

```
┌─────────────────────────────────────────────────────────────────────┐
│                          数据库表结构                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────┐         ┌──────────────────────┐          │
│  │  skill_packages      │ 1───N   │       skills         │          │
│  │  （技能包）           │         │     （技能）          │          │
│  ├──────────────────────┤         ├──────────────────────┤          │
│  │ id (主键)            │◄────────│ package_id (外键)    │          │
│  │ tenant_id (可空)     │         │ id (主键)            │          │
│  │ name 名称            │         │ tenant_id (可空)     │          │
│  │ description 描述     │         │ name 名称            │          │
│  │ avatar 头像          │         │ description 描述     │          │
│  │ scope 作用域(枚举)   │         │ type 类型(枚举)      │          │
│  │ source_plugin 来源   │         │ config 配置(JSON)    │          │
│  │ is_system 系统标记   │         │ toolkit_content 代码 │          │
│  │ valves_schema 配置项 │         │ toolkit_meta 元数据  │          │
│  │ valves_config 配置值 │         │ input_schema 输入    │          │
│  │ is_active 是否启用   │         │ output_schema 输出   │          │
│  │ sort_order 排序      │         │ is_system 系统标记   │          │
│  │ is_deleted 软删除    │         │ is_active 是否启用   │          │
│  │ delete_level 删除层级│         │ sort_order 排序      │          │
│  └──────────┬───────────┘         │ timeout 超时(秒)     │          │
│             │                     │ is_deleted 软删除    │          │
│             │                     │ delete_level 删除层级│          │
│             │                     └──────────────────────┘          │
│             │                                                       │
│             │ 1───N                                                  │
│             ▼                                                       │
│  ┌──────────────────────────┐       ┌──────────────────────┐        │
│  │ agent_skill_bindings     │ N───1 │       agents         │        │
│  │ （智能体-技能包绑定）     │       │     （智能体）        │        │
│  ├──────────────────────────┤       ├──────────────────────┤        │
│  │ id (主键)                │       │ id (主键)            │        │
│  │ tenant_id (可空)         │       │ tenant_id (可空)     │        │
│  │ agent_id (外键) ─────────┼──────►│ name 名称            │        │
│  │ package_id (外键) ───────┼──┐    │ scope 作用域         │        │
│  │ enabled 是否启用         │  │    │ model_id (外键→      │        │
│  │ config_override 配置覆盖 │  │    │   ai_models)         │        │
│  │ sort_order 排序          │  │    │ system_prompt 提示词 │        │
│  │ consent_mode 授权模式    │  │    │ is_system 系统标记   │        │
│  │ skill_consent_overrides  │  │    │ status 状态          │        │
│  │   技能级授权覆盖(JSON)   │  │    │ execution_mode 模式  │        │
│  │ UQ(agent_id, package_id) │  │    │ ...                  │        │
│  └──────────────────────────┘  │    └──────────────────────┘        │
│                                │                                    │
│                   指向 skill_packages                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 核心关系

| 关系 | 基数 | 外键位置 |
|---|---|---|
| **技能包 → 技能** | 1:N | `skills.package_id` |
| **智能体 ↔ 技能包** | M:N | `agent_skill_bindings`（中间表） |
| **智能体 → AI 模型** | N:1 | `agents.model_id` |

> **重要**：智能体**不直接绑定**单个技能（Skill），而是始终绑定**技能包**（SkillPackage）。解析器在运行时加载技能包内所有激活的技能。

---

## 二、作用域与多租户体系

```
┌──────────────────────────────────────────────────────────────┐
│                    ResourceScopeEnum 作用域枚举                │
├─────────┬────────────────────────────────────────────────────┤
│  tenant │ tenant_id = X（必填）                               │
│  租户级  │ 仅该租户可见                                        │
│         │ 租户可完全增删改查                                    │
├─────────┼────────────────────────────────────────────────────┤
│  admin  │ tenant_id = NULL                                    │
│  管理级  │ 仅管理端可见                                        │
│         │ 租户可绑定使用（只读），可通过"从模板克隆"复制为自有    │
├─────────┼────────────────────────────────────────────────────┤
│  global │ tenant_id = NULL                                    │
│  全局级  │ 全平台可见（管理端 + 所有租户）                       │
│         │ 自动包含在租户的列表查询中                             │
└─────────┴────────────────────────────────────────────────────┘
```

### 可见性规则（源自 Repository 代码）

**租户端** (`SkillPackageRepository.query_list`)：
```python
WHERE (tenant_id = :当前租户ID) OR (scope = 'global')
```

**租户端绑定下拉** (`get_available_for_binding`)：
```python
WHERE is_active AND NOT is_deleted AND (
    tenant_id = :当前租户ID                          -- 自有包
    OR (tenant_id IS NULL AND scope IN ('admin', 'global'))  -- 共享包
)
```

**管理端** (`AdminSkillPackageRepository` / `BaseRepository`)：
- 无租户过滤 — 可查看**所有租户**、**所有作用域**的技能包。

---

## 三、技能类型体系

```
┌───────────────────┬───────────────┬──────────────────────────────────┐
│   SkillTypeEnum    │ 产生工具数量   │ 工作原理                         │
├───────────────────┼───────────────┼──────────────────────────────────┤
│  knowledge_base   │  0 个工具     │ 不生成 ToolDefinition。           │
│  知识库            │               │ 提取知识库 ID → RAG 检索后       │
│                   │               │ 注入到 system_prompt 中。         │
├───────────────────┼───────────────┼──────────────────────────────────┤
│  data_intelligence│  1~4 个工具   │ data_query（始终生成）             │
│  数据智能          │               │ + data_create/update/delete      │
│                   │               │ （由 TablePolicy 控制）           │
├───────────────────┼───────────────┼──────────────────────────────────┤
│  toolkit          │  N 个工具     │ Python 源码存于 toolkit_content   │
│  工具包            │               │ Tools 类的每个公开方法 →          │
│                   │               │ 1 个 ToolDefinition              │
├───────────────────┼───────────────┼──────────────────────────────────┤
│  builtin          │  1 或 N 个    │ 单工具模式（默认）或              │
│  内置              │               │ config.tools[] → N 个工具        │
├───────────────────┼───────────────┼──────────────────────────────────┤
│  http             │  1 个工具     │ 声明式 HTTP 调用                  │
│  HTTP 调用         │               │ URL/方法/头/请求体模板            │
├───────────────────┼───────────────┼──────────────────────────────────┤
│  email            │  1 个工具     │ 通过 EmailService 发送邮件        │
│  邮件              │               │                                  │
├───────────────────┼───────────────┼──────────────────────────────────┤
│  code_execution   │  1 个工具     │ 在安全沙箱中执行代码              │
│  代码执行          │               │                                  │
└───────────────────┴───────────────┴──────────────────────────────────┘
```

---

## 四、AI 执行全链路 — 智能体如何使用技能包

```
用户消息
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  AgentChatService / API 控制器                               │
│  （租户端/管理端接收用户消息）                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ExecutionDispatcher.dispatch() — 执行分发器                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 1. 加载智能体 Agent（校验 status=published）            │ │
│  │ 2. 并发控制（AgentConcurrencyLimiter）                  │ │
│  │ 3. 配额检查（AgentQuotaManager）                        │ │
│  │ 4. BEFORE_EXECUTE 钩子                                 │ │
│  │                                                        │ │
│  │ 5. ★ resolve_for_agent(db, agent, tenant_id) ★        │ │
│  │    ┌──────────────────────────────────────────────┐   │ │
│  │    │ 阶段一：加载技能包绑定                         │   │ │
│  │    │   查询 agent_skill_bindings                   │   │ │
│  │    │   WHERE agent_id=X AND enabled=true           │   │ │
│  │    │   → 得到 package_ids + 配置覆盖               │   │ │
│  │    │                                                │   │ │
│  │    │ 阶段二：从绑定的技能包中加载技能               │   │ │
│  │    │   WHERE package_id IN (...) AND is_active     │   │ │
│  │    │   → 合并 Skill.config + 绑定覆盖              │   │ │
│  │    │   → 注入 package.valves_config 作为 "valves"  │   │ │
│  │    │                                                │   │ │
│  │    │ 阶段三：SkillResolver.resolve(skills) 解析     │   │ │
│  │    │   按技能类型分发：                              │   │ │
│  │    │   ├─ knowledge_base → 提取知识库ID + RAG配置  │   │ │
│  │    │   ├─ data_intelligence → 1~4个 ToolDefinition │   │ │
│  │    │   ├─ toolkit → 解析Python源码 → N个 ToolDef   │   │ │
│  │    │   ├─ builtin → 1或N个 ToolDef                 │   │ │
│  │    │   ├─ http → 1个 ToolDef（含HTTP配置）         │   │ │
│  │    │   ├─ email → 1个 ToolDef（send_email）        │   │ │
│  │    │   ├─ code_execution → 1个 ToolDef             │   │ │
│  │    │                                                │   │ │
│  │    │ 返回 SkillResolveResult {                      │   │ │
│  │    │   tools: [ToolDefinition, ...],    工具列表    │   │ │
│  │    │   knowledge_base_ids: [1, 5, ...], 知识库ID   │   │ │
│  │    │   rag_config: {...},               RAG配置    │   │ │
│  │    │   tool_consent_modes: {"名": "auto"}, 授权    │   │ │
│  │    │   warnings: [...]                  警告       │   │ │
│  │    │ }                                              │   │ │
│  │    └──────────────────────────────────────────────┘   │ │
│  │                                                        │ │
│  │ 6. 创建引擎（对话/任务/批处理）                         │ │
│  │    engine.execute(agent, request, skill_result)        │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  BaseEngine._prepare_execution() — 执行前准备               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 1. 构建 system_prompt（Jinja2 渲染变量）               │ │
│  │ 2. 若有 knowledge_base_ids → RAG 检索注入到 prompt    │ │
│  │ 3. 将 ToolDefinition[] → OpenAI function calling 格式 │ │
│  │    通过 to_openai_tools() 转换                         │ │
│  │ 4. 工具优化器：按用户问题筛选相关工具                    │ │
│  └────────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  ConversationEngine.stream_execute() — 流式对话引擎         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 循环（最多 10 轮）：                                    │ │
│  │ 1. AIGateway.stream_chat(消息, 工具, 模型配置)         │ │
│  │ 2. 若 LLM 返回 tool_calls：                           │ │
│  │    → ToolSandbox.execute(call_id, 工具名, 参数)       │ │
│  │    → 按 tool_type 路由到对应执行器：                    │ │
│  │      ┌─────────────────────────────────────────────┐  │ │
│  │      │ toolkit       → ToolkitExecutor  (Python)   │  │ │
│  │      │ builtin       → BuiltinToolExecutor         │  │ │
│  │      │ text_to_sql   → TextToSQLExecutor           │  │ │
│  │      │ data_create   → CreateRecordExecutor        │  │ │
│  │      │ data_update   → UpdateRecordExecutor        │  │ │
│  │      │ data_delete   → DeleteRecordExecutor        │  │ │
│  │      │ http          → HTTP 执行器                 │  │ │
│  │      │ email         → 邮件执行器                  │  │ │
│  │      │ code_execution→ 代码执行器                  │  │ │
│  │      └─────────────────────────────────────────────┘  │ │
│  │    → 将 ToolResult 作为 tool 消息追加                  │ │
│  │    → 继续循环（LLM 看到工具结果后继续推理）             │ │
│  │ 3. 若 LLM 返回文本 → yield SSE 流式块 → 结束          │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、智能体 ↔ 技能包绑定机制

```
                    ┌──────────┐
                    │ 智能体    │
                    │ Agent    │
                    │ id=42    │
                    └────┬─────┘
                         │ 拥有多个绑定
                         ▼
           ┌─────────────────────────────┐
           │  AgentSkillBinding（M:N）    │
           ├─────────────────────────────┤
           │ agent_id=42, package_id=1   │──► 技能包「客服知识库」
           │   enabled=true ← 已启用     │       ├─ 技能: FAQ知识库 (knowledge_base)
           │   config_override=null      │       └─ 技能: 产品知识库 (knowledge_base)
           │   consent_mode="auto"       │
           │   sort_order=0              │
           ├─────────────────────────────┤
           │ agent_id=42, package_id=5   │──► 技能包「数据分析工具」
           │   enabled=true ← 已启用     │       ├─ 技能: 销售查询 (data_intelligence)
           │   config_override={...}     │       └─ 技能: 报表生成 (toolkit)
           │   consent_mode="ask"        │
           │   sort_order=1              │
           ├─────────────────────────────┤
           │ agent_id=42, package_id=12  │──► 技能包「数据分析」
           │   enabled=true              │       └─ 技能: data_analysis
           │   sort_order=2              │
           └─────────────────────────────┘

   绑定功能说明：
   ────────────
   • enabled：按绑定粒度启用/禁用
   • config_override：每个智能体可覆盖技能包的部分配置
   • consent_mode：auto(自动)|ask(需确认)|reject(拒绝) — 工具调用授权模式
   • skill_consent_overrides：包内按技能粒度覆盖授权模式
   • sort_order：控制工具优先级（LLM 按此排序接收工具列表）
   • UniqueConstraint(agent_id, package_id)：同一包不可重复绑定
```

### 绑定解析流程

```
resolve_for_agent(db, agent, tenant_id)
    │
    ├─ 1. 查询 agent_skill_bindings
    │      WHERE agent_id=42 AND enabled=true AND NOT is_deleted
    │      ORDER BY sort_order
    │
    ├─ 2. 遍历每个绑定：
    │      └─ 检查 binding.package.is_active AND NOT is_deleted
    │      └─ 收集 package_ids、config_overrides、consent_modes
    │
    ├─ 3. 查询 skills
    │      WHERE package_id IN (1, 5) AND is_active AND NOT is_deleted
    │      ORDER BY sort_order
    │
    ├─ 4. 合并配置（优先级从低到高）：
    │      skill.config ← package.valves_config（作为"valves"键）← binding.config_override
    │
    ├─ 5. SkillResolver.resolve(skills, 合并后配置)
    │      → 按技能类型分发 → ToolDefinition[]
    │
    └─ 6. 映射 consent_mode（技能包级 → 技能级覆盖）
```

---

## 六、管理端 vs 租户端 — 完整对比

### 6.1 后端架构差异

```
┌──────────────────────────────────┬──────────────────────────────────────┐
│         管理端 (Admin)            │          租户端 (Tenant)              │
├──────────────────────────────────┼──────────────────────────────────────┤
│ 控制器：                          │ 控制器：                              │
│   GlobalController               │   TenantController                   │
│   （无租户隔离）                   │   （自动注入 tenant_id）              │
│                                  │                                      │
│ 服务层：                          │ 服务层：                              │
│   AdminSkillPackageService       │   SkillPackageService                │
│   继承 GlobalService             │   继承 TenantService                 │
│                                  │                                      │
│ 仓库层：                          │ 仓库层：                              │
│   AdminSkillPackageRepository    │   SkillPackageRepository             │
│   继承 BaseRepository            │   继承 TenantRepository              │
│   （无 WHERE tenant_id 条件）     │   （自动 WHERE tenant_id=X            │
│                                  │    OR scope='global'）               │
│                                  │                                      │
│ 认证依赖：                        │ 认证依赖：                            │
│   ActiveAdmin                    │   ActiveTenantAdmin                  │
│                                  │                                      │
│ 权限资源码：                      │ 权限资源码：                          │
│   ai_skill_package               │   skill_package                      │
│   scope=ADMIN                    │   scope=TENANT                       │
│                                  │                                      │
│ 删除层级：                        │ 删除层级：                            │
│   _default_delete_level='admin'  │   _default_delete_level='tenant'     │
│   （直接进入管理端回收站）         │   （先进租户回收站，可升级到管理端）    │
└──────────────────────────────────┴──────────────────────────────────────┘
```

### 6.2 API 端点差异

```
┌───────────────────────┬──────────────────────────┬──────────────────────────┐
│ 功能                   │ 管理端 (/admin/...)       │ 租户端 (/tenant/...)      │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 技能包列表             │ GET  /ai/skill-packages  │ GET  /ai/skill-packages  │
│                       │ （所有作用域、所有租户）    │ （仅本租户 + global 包）  │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 下拉选项               │ GET  .../select          │ GET  .../select          │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 可绑定列表             │ —                        │ GET  .../available       │
│                       │                          │ （自有 + admin + global）  │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 创建                   │ POST（任意作用域，        │ POST（仅 tenant 作用域）  │
│                       │  可指定 tenant_id）        │ tenant_id=当前租户       │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 上传 ZIP 安装          │ POST .../upload          │ POST .../upload          │
│                       │ scope=admin              │ scope=tenant             │
│                       │ 允许 is_system=true      │ 始终 is_system=false     │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 克隆                   │ POST .../{id}/clone      │ —                        │
│                       │ （任意作用域 → 任意作用域）│                          │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 从模板克隆             │ —                        │ POST .../from-template/  │
│                       │                          │  {id}                    │
│                       │                          │ （admin/global → 租户自有）│
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 导出                   │ GET .../{id}/export      │ —                        │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 导入                   │ POST .../import          │ —                        │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 调用统计               │ GET .../{id}/stats       │ —                        │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ Valves 环境配置        │ GET/PUT .../valves       │ GET/PUT .../valves       │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 包内技能列表           │ GET .../{id}/skills      │ GET .../{id}/skills      │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 切换启用状态           │ PUT .../{id}/status      │ —                        │
├───────────────────────┼──────────────────────────┼──────────────────────────┤
│ 回收站                 │ 管理端级别路由            │ 租户端级别路由            │
└───────────────────────┴──────────────────────────┴──────────────────────────┘
```

### 6.3 作用域校验差异

**管理端** (`AdminSkillPackageService._before_create`)：
- 可创建**任意作用域**的技能包（tenant/admin/global）
- `scope=tenant` 时，必须提供 `tenant_id`
- `scope=admin` 或 `scope=global` 时，自动设置 `tenant_id=NULL`
- 名称唯一性在**同一 scope + tenant_id** 范围内检查

**租户端** (`SkillPackageService._before_create`)：
- **只能**创建 `scope=tenant` 的技能包
- `tenant_id` 由 `TenantService` 自动注入
- 名称唯一性仅在本租户范围内检查
- **不能**创建 `is_system=True` 的技能包

---

## 七、系统保护层

```
is_system = True（系统技能包标记）
    │
    ├─ 不可删除（管理端和租户端 Service 均检查）
    ├─ 不可修改以下字段：scope、is_system、is_active
    ├─ 前端：删除按钮隐藏、状态切换开关禁用
    ├─ 前端：显示紫色「系统」徽章
    │
    └─ 典型示例：
       ├─ 系统预置智能体绑定的技能包
       └─ 通过迁移脚本种子数据创建的技能包
```

---

## 八、完整生命周期图

```
┌──────────────────────────────────────────────────────────────┐
│                     技能包完整生命周期                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  创建                                                         │
│  ├─ 管理端：API 创建 + ZIP 上传 + JSON 导入 + 克隆           │
│  ├─ 租户端：API 创建 + ZIP 上传 + 从模板克隆                  │
│                                                               │
│  绑定到智能体                                                  │
│  ├─ 创建 AgentSkillBinding(agent_id, package_id)              │
│  ├─ 可选：config_override（配置覆盖）、consent_mode（授权模式）│
│  └─ 租户可使用：自有包 + admin 共享包 + global 全局包          │
│                                                               │
│  AI 执行                                                      │
│  ├─ Dispatcher 调用 resolve_for_agent()                       │
│  ├─ 加载 绑定 → 技能包 → 技能 → ToolDefinition               │
│  ├─ Engine 使用工具列表进行 LLM Function Calling              │
│  └─ Sandbox 按 tool_type 路由到对应执行器                      │
│                                                               │
│  删除（两级回收站）                                            │
│  ├─ 租户删除 → delete_level='tenant'（进入租户回收站）         │
│  │   └─ 级联：技能软删除、绑定物理删除                         │
│  ├─ 管理端升级 → delete_level='admin'（进入管理端回收站）      │
│  ├─ 永久删除 → 物理删除 + 清理磁盘存储文件                     │
│  └─ 30 天自动清理（Celery Beat 定时任务）                      │
│                                                               │
│  恢复                                                         │
│  └─ 级联恢复技能包下所有子技能                                 │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 九、关键源码文件索引

### 模型层
| 文件 | 说明 |
|---|---|
| `backend/app/models/ai/skill_package.py` | 技能包 ORM（TenantModel，tenant_id 可空） |
| `backend/app/models/ai/skill.py` | 技能 ORM（通过 package_id 外键归属技能包） |
| `backend/app/models/ai/agent.py` | 智能体 ORM（含 skill_bindings 关系） |
| `backend/app/models/ai/agent_skill_binding.py` | M:N 中间表（智能体 ↔ 技能包） |

### 枚举层
| 文件 | 说明 |
|---|---|
| `backend/app/enums/agent.py` | SkillTypeEnum（7种类型）+ ToolTypeEnum + ToolConsentModeEnum |
| `backend/app/enums/common.py` | ResourceScopeEnum（tenant/global/admin） |

### AI 引擎（技能解析 → 执行）
| 文件 | 说明 |
|---|---|
| `backend/app/ai/skills/resolver.py` | SkillResolver + resolve_for_agent() — 核心转换逻辑 |
| `backend/app/ai/engine/dispatcher.py` | ExecutionDispatcher — 编排整个执行流程 |
| `backend/app/ai/engine/base.py` | BaseEngine — _prepare_execution 使用 SkillResolveResult |
| `backend/app/ai/tools/sandbox.py` | ToolSandbox — 按 tool_type 路由到执行器 |
| `backend/app/ai/tools/types.py` | ToolDefinition / ToolResult / ExecutionContext 类型定义 |

### 执行器（每种 tool_type 一个）
| 文件 | 对应工具类型 |
|---|---|
| `backend/app/ai/tools/executors/toolkit_executor.py` | toolkit（Python 工具包） |
| `backend/app/ai/tools/executors/builtin_executor.py` | builtin（内置工具） |
| `backend/app/ai/tools/executors/text_to_sql_executor.py` | text_to_sql（自然语言转SQL） |
| `backend/app/ai/tools/executors/crud_executor.py` | data_create/update/delete（数据增删改） |

### 服务层 / 仓库层
| 文件 | 说明 |
|---|---|
| `backend/app/services/ai/skill_package_service.py` | SkillPackageService（租户）+ AdminSkillPackageService（全局） |
| `backend/app/repositories/ai/skill_package_repository.py` | 仓库 + 级联 Mixin + 作用域感知查询 |

### API 控制器
| 文件 | 说明 |
|---|---|
| `backend/app/api/admin/skill_packages.py` | AdminSkillPackageController（GlobalController）— 14 个端点 |
| `backend/app/api/tenant/skill_packages.py` | TenantSkillPackageController（TenantController）— 11 个端点 |

---

## 十、架构不变量（设计原则）

1. **智能体永远不直接绑定单个技能** — 始终绑定技能包。
2. **SkillResolver 是唯一桥梁** — 连接 ORM 模型和 AI 引擎运行时（ToolDefinition）。
3. **resolve_for_agent() 在 Dispatcher 层调用**，不在 Engine 内部 — Engine 接收已解析好的 `SkillResolveResult`。
4. **knowledge_base 类型技能产生 0 个 ToolDefinition** — 通过 RAG 管线注入上下文到 system_prompt。
5. **作用域创建后不可变** — 不能将租户包改为管理包或反之。
6. **系统技能包/技能**（is_system=True）不可删除、禁用，scope/is_system 字段不可修改。
7. **租户可查看并绑定 admin/global 技能包**，但不能修改 — 只能通过"从模板克隆"复制为自有。
8. **删除级联规则**：删除技能包 → 软删除所有子技能 + 物理删除所有 AgentSkillBinding。
9. **Valves 环境配置**存储在技能包级别，解析时注入到每个工具的 config 中（键名 `_valves_config`）。
