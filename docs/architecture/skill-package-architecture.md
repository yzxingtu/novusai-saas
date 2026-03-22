# SkillPackage 架构（2026-03 现行）

## 1. 定位

`SkillPackage` 现在承担三件事：

1. 归组单元：把多个 `Skill` 组织成一个可管理目录项。
2. 来源单元：标记该组能力来自平台系统、平台目录、企业自有还是插件托管。
3. 展示单元：为管理端与企业端提供可读目录、摘要字段和解析后的工具预览。

它**不再是运行时绑定真相**。

运行时真正决定某个 Agent 拥有哪些能力的依据是：

- `AgentSkillGrant -> Skill -> SkillResolver -> ToolDefinition`

也就是说，Agent 在执行时直接消费 Skill 授权，不再依赖“包级自动绑定”语义。

---

## 2. 运行时真相

当前 AI 运行链路：

```text
Agent
  -> AgentSkillGrant
  -> Skill
  -> SkillResolver
  -> ToolDefinition / RAG 配置 / 其它执行元数据
```

关键不变量：

- `Skill` 必须归属于某个 `SkillPackage`
- `SkillPackage` 只负责目录、来源和归组
- Agent 运行时是否拿到能力，只看 `AgentSkillGrant`
- 不要重新引入 `SkillPackage auto-bind`、`AgentSkillBinding` 或“整包天然生效”语义

---

## 3. 信息架构字段

为避免前后端继续把旧包级绑定语义当成主语义，当前 API 统一补充规范化摘要字段：

- `package_role_key`
  - `platform_system`
  - `platform_catalog`
  - `tenant_owned`
  - `plugin_managed`
- `source_summary`
  - `platform:system`
  - `platform:catalog`
  - `tenant:{tenant_id}`
  - `plugin:{plugin_name}`
- `runtime_binding_mode`
  - 当前固定为 `direct_agent_skill_grant`
- `valves_field_count`
- `configured_valves_count`

原则：

- 前端展示优先使用上述规范化字段
- 通用详情接口默认不返回原始 `valves_config`

---

## 4. 管理端与企业端边界

### 管理端

- 路由：`/admin/ai/skill-packages`
- 能力：完整目录管理、导入导出、克隆、详情、valves 配置
- 用途：维护 SkillPackage 目录、Skill 归属和来源元数据

### 企业端

- 路由：`/tenant/ai/skill-packages`
- 能力：**只读目录**
- 可看内容：
  - 包角色
  - 来源摘要
  - 包内 Skill
  - 解析后的工具定义
- 禁止：
  - SkillPackage CRUD
  - valves 编辑
  - 导入导出/克隆
  - 包级运行绑定动作

企业端之所以允许目录页，是为了让租户管理员理解“当前可见能力来自哪里、包里有什么、最终会解析出哪些工具”，而不是把这里变成运行时绑定入口。

---

## 5. 插件映射模型

插件与 SkillPackage/Skill 的关系现在也收口为显式映射：

```text
plugin.yaml
  -> extensions.capabilities[*]        # 能力声明层
  -> extensions.skills[*]              # Skill 投影层
  -> extensions.skills[*].capabilities # 显式引用 capability.key
  -> SkillPackage / Skill 同步投影
```

约束：

- `extensions.capabilities[*]` 与 `extensions.skills[*].capabilities[]` 必须显式关联
- 插件启用/升级时同步的是 `SkillPackage + Skill` 目录投影
- 插件启用**不等于**自动把整包绑定给 Agent
- 插件前端如声明 `dashboard_widgets`，必须在插件自己的前端入口导出对应组件

---

## 6. 与知识库链路的边界

本轮 SkillPackage 收口不会破坏知识库链路，原因如下：

- 知识库运行时入口仍然是 `Agent` 侧的直接配置与授权链路
- `SkillPackage` 只负责归组和目录，不承载知识库检索真相
- `knowledge_base` 类型 `Skill` 仍然通过 `SkillResolver` 进入 RAG 相关元数据，而不是靠包级绑定决定是否生效

因此，SkillPackage 的信息架构调整不会改变知识库检索、召回或注入逻辑。

---

## 7. 当前实现落点

后端：

- `backend/app/api/shared/_skill_package_summary.py`
- `backend/app/api/admin/skill_packages.py`
- `backend/app/api/tenant/skill_packages.py`
- `backend/app/services/ai/skill_package_service.py`
- `backend/app/repositories/ai/skill_package_repository.py`

前端：

- `frontend/apps/web-antd/src/views/admin/ai/skill-packages/*`
- `frontend/apps/web-antd/src/views/tenant/ai/skill-packages/*`
- `frontend/apps/web-antd/src/api/admin/skill-packages.ts`
- `frontend/apps/web-antd/src/api/tenant/skill-packages.ts`

---

## 8. 结论

后续涉及 SkillPackage 的实现，都应遵守以下一句话：

> SkillPackage 是归组 / 来源 / 目录单元；Agent 的运行时能力真相是直接 Skill 授权。
