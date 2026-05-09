# 设计说明

## 决策

- 联网搜索是退役能力，不再是平台 builtin，也不能被插件/技能包用旧名重新注册。
- 天气不是联网搜索。天气保留为 `weather-widget` 等插件自己的 resolver/executor 能力，主 runtime 只能看到已经解析出的 `ToolDefinition` / `CapabilityDescriptor` 元数据；测试和 smoke 不能把天气当作默认 builtin/runtime 能力。
- 主 runtime 可以做安全过滤、工具 schema 投放、sandbox 执行和诊断投影；不能写“如果用户说天气/搜索，就调用某能力”的业务分支。
- 历史 trace 可以展示为历史诊断，但不能作为当前 turn 的 availability、selected tool、candidate tool 或 provider completion evidence。
- 数据库历史残留需要迁移清退，不只靠前端隐藏。UI 看到的“联网搜索”通常说明 catalog/package 或 grant 里还有旧数据。

## 关键边界

### 运行时输入防线

`backend/app/schemas/ai/invalid_ai_runtime_input.py` 是旧名和退役工具名的公共 guard。任何入口如果支持 `selected_skill_names`、tool 名称、provider event 或 runtime reference，都应复用这里的判断。

### Catalog / Binding 防线

`SkillPackage` / `Skill` 的创建更新服务负责写入时拒绝退役搜索。repository 和 grant service 负责读取时 fail closed，避免已有脏数据继续出现在可绑定列表或运行时授权集合。

### Smoke / Diagnostics 防线

`RuntimeRealDialogueSmokeService` 不应把 provider search event 当作证据。它应该把 `candidate_tool_names`、`selected_tools`、`selected_skills`、provider events 中出现的退役搜索标记为失败证据。

### 数据迁移防线

迁移应检查表/列是否存在，再清退相关 grants / skills / packages。迁移中不要用 f-string SQL 标识符，不要依赖失败后继续执行。

## 子代理分工

- A1：审计主 AI runtime 是否还存在天气/联网搜索硬编码正向能力。
- A2：审计 skill package / skill / grant / repository 是否仍会显示或绑定联网搜索。
- A3：审计 provider payload、diagnostics、smoke service 是否仍接受 hosted/native search。
- A4：审计前端显示和诊断过滤是否仍把联网搜索当 live capability。
- A5：审计迁移和历史数据清退方案。
- A6：审计测试是否符合 testing-discipline，尤其不能用弱 assertion 假绿。

## 风险

- 当前工作树有大量 AI 文件脏改动，可能包含其它 AI 的错误恢复痕迹。实现前必须读 diff 和相关文件，不能直接基于记忆补丁。
- 不能把“天气请求要工具”改成“主 runtime 知道天气业务”。天气可用性必须来自当前 resolved executable tools，smoke 只能把插件天气工具命中视为可观察事实，不能把它作为默认通过门槛。
- 不能把联网搜索留作“兼容旧名”。这是新系统退役能力，旧名只能被拒绝或作为历史诊断文字出现。

## 完成口径

本任务完成后可以声明：联网搜索退役在 structural / behavioral 层面被代码和测试防住。不能声明 AI real-dialogue milestone 完整通过，除非另有真实 provider smoke report 归档。
