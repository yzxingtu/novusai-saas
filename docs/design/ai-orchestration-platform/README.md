# AI 编排平台规划目录

本目录用于集中沉淀“AI 编排与工作流平台”相关设计，避免与现有零散设计稿混放。

## 当前文档

1. [01-platform-architecture-20260323.md](./01-platform-architecture-20260323.md)
   平台定位、模块图、作用域/授权/计费模型、工作流权限矩阵、最小行业样板。

2. [02-platform-data-model-20260323.md](./02-platform-data-model-20260323.md)
   平台数据模型草案，说明哪些实体应复用现有模型，哪些实体需要新增。

3. [03-page-and-permission-map-20260323.md](./03-page-and-permission-map-20260323.md)
   管理端 / 企业端页面清单、职责边界、权限矩阵建议。

4. [04-billing-and-entitlement-spec-20260323.md](./04-billing-and-entitlement-spec-20260323.md)
   平台订阅、行业方案授权、插件 License、企业定制交付的统一计费与授权规则。

5. [05-approval-and-risk-gate-spec-20260323.md](./05-approval-and-risk-gate-spec-20260323.md)
   风险分级、审批策略分层、`L4` 高自治执行闸门、审批预览包、超时与驳回规则。

6. [06-solution-plugin-spec-20260323.md](./06-solution-plugin-spec-20260323.md)
   规定行业解决方案如何以插件形式打包、安装、授权、升级，并与模板、Agent、Skill 和企业配置体系对齐。

7. [07-short-video-growth-solution-detail-20260323.md](./07-short-video-growth-solution-detail-20260323.md)
   以“爆款短视频增长方案包”作为最小行业样板，验证插件化行业方案、AI 编排、审批、草稿与复盘闭环。

8. [08-workflow-builder-capability-matrix-20260323.md](./08-workflow-builder-capability-matrix-20260323.md)
   规范管理端工作室、企业模板编辑器、企业简单构建器三种构建面，以及不同节点、能力、模式、权限的开放矩阵。

9. [09-trigger-and-release-spec-20260323.md](./09-trigger-and-release-spec-20260323.md)
   规范工作流的触发类型、发布对象、版本快照、灰度范围、回滚机制以及触发与审批的联动关系。

10. [10-custom-delivery-operating-model-20260323.md](./10-custom-delivery-operating-model-20260323.md)
   规范复杂代码型工作流与企业专属能力的定制交付流程，包括分流、评估、报价、冻结、实施、验收、上线、交接和变更管理。

11. [11-observability-and-evaluation-spec-20260323.md](./11-observability-and-evaluation-spec-20260323.md)
   规范平台上线后的可观测性与评估体系，区分监控与评估，并定义运行、成本、审批、质量、业务结果等多层指标。

12. [12-runtime-policy-engine-spec-20260323.md](./12-runtime-policy-engine-spec-20260323.md)
   规范统一的运行时策略引擎，收口套餐、授权、插件 gate、发布触发、风险审批、知识可用性等所有运行时裁决。

13. [13-enterprise-knowledge-and-context-injection-spec-20260323.md](./13-enterprise-knowledge-and-context-injection-spec-20260323.md)
   规范企业业务知识如何以配置、知识库、运行时上下文、反馈回流四条通道注入到 Agent 和工作流中。

14. [14-solution-lifecycle-and-upgrade-playbook-20260323.md](./14-solution-lifecycle-and-upgrade-playbook-20260323.md)
   规范行业方案从孵化、试点、正式发行到弃用退役的全生命周期，以及平台原件、企业激活版本、企业副本和定制增强的升级与回滚机制。

15. [15-workflow-data-contract-and-schema-spec-20260323.md](./15-workflow-data-contract-and-schema-spec-20260323.md)
   规范工作流输入输出、节点端口、Artifact、审批包、评估记录的统一数据契约与 Schema 体系，确保平台按契约运行而不是只靠 Prompt 约定。

16. [16-runtime-execution-graph-and-recovery-spec-20260323.md](./16-runtime-execution-graph-and-recovery-spec-20260323.md)
   规范工作流运行时如何被实例化为执行图，以及节点状态、检查点、重试、恢复、补偿、人工接管和动态扩图的治理方式。

17. [17-enterprise-operator-console-spec-20260323.md](./17-enterprise-operator-console-spec-20260323.md)
   规范企业端正式运营控制台的信息架构、角色模型、任务驱动首页、运行/审批/异常/草稿/版本/成本等日常运营入口。

18. [18-solution-delivery-spec-bundle-and-acceptance-kit-20260323.md](./18-solution-delivery-spec-bundle-and-acceptance-kit-20260323.md)
   规范行业方案和企业定制交付在冻结、实施、验收、交接、升级过程中的规格包、验收包、交接包与已知限制说明包。

19. [19-evaluation-dataset-and-benchmark-governance-spec-20260323.md](./19-evaluation-dataset-and-benchmark-governance-spec-20260323.md)
   规范平台通用、行业方案、企业局部三层评估数据集、基准套件、盲测集、标注规范和版本门禁治理，确保评估可回归、可复用、可防泄漏。

20. [20-runtime-budget-quota-and-cost-guard-spec-20260323.md](./20-runtime-budget-quota-and-cost-guard-spec-20260323.md)
   规范运行时预算、配额和成本守卫在平台、企业、方案、工作流、节点多个层次的治理方式，以及超线后的提醒、确认、审批、降级和阻断动作。

21. [21-connector-trust-and-external-action-safety-spec-20260323.md](./21-connector-trust-and-external-action-safety-spec-20260323.md)
   规范连接器可信度、外部动作分类、凭据作用域、安全五件套、预检/干跑/正式执行、冻结与补偿机制，确保平台安全连接外部系统。

22. [22-organization-role-model-and-human-collaboration-lane-spec-20260323.md](./22-organization-role-model-and-human-collaboration-lane-spec-20260323.md)
   规范平台方与企业方的组织角色模型，以及请求、审阅、审批、编辑、运营、事故、所有者决策等正式人机协作通道与责任绑定方式。

23. [23-enterprise-data-governance-and-sensitive-information-boundary-spec-20260323.md](./23-enterprise-data-governance-and-sensitive-information-boundary-spec-20260323.md)
   规范企业数据的正式分级、作用域、用途限制、字段脱敏、Prompt/RAG/审批/评估/导出/日志等链路的敏感信息边界。

24. [24-agent-memory-and-long-term-learning-boundary-spec-20260323.md](./24-agent-memory-and-long-term-learning-boundary-spec-20260323.md)
   规范会话记忆、任务记忆、用户偏好记忆、长期学习信号、企业规则知识之间的边界，以及启用、写回、清理、撤销和审计规则。

25. [25-workflow-environment-promotion-and-change-governance-spec-20260323.md](./25-workflow-environment-promotion-and-change-governance-spec-20260323.md)
   规范工作流、方案插件、策略包、连接器配置等正式变更如何在草稿、验证、灰度、生产各环境间晋级、放行、回滚与紧急修复。

26. [26-open-integration-and-embedded-orchestration-spec-20260323.md](./26-open-integration-and-embedded-orchestration-spec-20260323.md)
   规范 API、Webhook、事件订阅、嵌入式工作台和对外回执链路，确保平台能力可安全接入和嵌入第三方系统。

27. [27-workflow-testing-simulation-and-dry-run-spec-20260323.md](./27-workflow-testing-simulation-and-dry-run-spec-20260323.md)
   规范工作流、方案插件和连接器在上线前后的静态校验、仿真、干跑、影子运行、回归评估和人工验收体系。

28. [28-tenant-onboarding-and-solution-activation-playbook-20260323.md](./28-tenant-onboarding-and-solution-activation-playbook-20260323.md)
   规范企业从签约、开通、方案安装、基线配置、沙盒试运行、试点上线到正式生产和护航期的标准作战路径。

29. [29-recommendation-decision-engine-and-strategy-output-spec-20260323.md](./29-recommendation-decision-engine-and-strategy-output-spec-20260323.md)
   规范推荐决策引擎如何整合企业数据、知识资产、外部情报和反馈信号，输出可解释、可审阅、可执行的策略建议。

30. [30-solution-marketplace-admission-review-and-commercial-governance-spec-20260323.md](./30-solution-marketplace-admission-review-and-commercial-governance-spec-20260323.md)
   规范方案市场和插件市场的准入、审核、上架、定向分发、信任标识、商业治理、暂停和下架机制。

31. [31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md](./31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md)
   把 `01-30` 收敛成第一阶段实施总路线图，明确 4 个 AI 的并行拆分、文件冻结边界、集成顺序和交付标准；配套独立提示词与 handoff 模板见 `31-parallel-delivery-kit-20260323/`。

32. [32-parallel-execution-control-spec-20260323.md](./32-parallel-execution-control-spec-20260323.md)
   把 `31` 中的并行开发方案进一步收敛成正式执行控制规范，明确独立工作副本、冻结规则、handoff 节奏和并行结束后的串行收口条件。

33. [33-cross-agent-contract-matrix-20260323.md](./33-cross-agent-contract-matrix-20260323.md)
   固定 4 个 AI 并行开发时必须共享的对象所有权、状态枚举、字段命名、权限资源名、分页风格和前后端契约口径。

34. [34-integrator-prompt-and-serial-merge-checklist-20260323.md](./34-integrator-prompt-and-serial-merge-checklist-20260323.md)
   定义串行集成人的角色、输入物、共享文件合并权限、串行合并顺序、校验矩阵和最终交付物；配套 `Integrator-serial-merge-prompt.md` 用于直接分发给集成人。

35. [35-coordinator-launch-and-delivery-runbook-20260323.md](./35-coordinator-launch-and-delivery-runbook-20260323.md)
   定义总协调者在 4 AI 并行交付前、中、后的启动、分发、冻结、验收、移交流程；配套 `Coordinator-launch-and-control-prompt.md` 用于直接分发给主协调者。

36. [36-coordinator-freeze-signoff-and-integrator-transfer-template-20260323.md](./36-coordinator-freeze-signoff-and-integrator-transfer-template-20260323.md)
   提供主协调者可直接复制填写的冻结签收单与正式移交单模板，用于统一记录 4 个 AI 的冻结状态、handoff 质量和移交给 `integrator` 的正式说明。

37. [37-worktree-setup-and-branch-bootstrap-runbook-20260323.md](./37-worktree-setup-and-branch-bootstrap-runbook-20260323.md)
   提供基于 `git worktree` 的 4 AI + 1 integrator 工作副本初始化命令手册，覆盖目录规划、分支创建、校验、清理和常见误区。

38. [38-integrator-final-merge-report-template-20260323.md](./38-integrator-final-merge-report-template-20260323.md)
   提供 `integrator` 最终集成报告模板，用于统一记录合并顺序、共享文件接入、迁移、验证结果、冲突裁决和遗留问题。

## 已确认原则

- 行业解决方案中心并入插件市场，以插件形式安装和授权。
- 平台方生产能力、代码型工作流、复杂连接器与行业方案。
- 企业方负责使用平台能力、注入业务知识、搭建简单工作流。
- 企业允许轻编排，但不允许扩展平台内核。
- 代码型工作流只能由管理端制作和交付。
- 资源所有权决定管理权，管理端不介入企业日常运营。
- 平台同时支持 `deterministic`、`hybrid`、`agentic` 三种运行模式。
- 高自治执行必须带强人工审核闸门。
- 第一版行业样板采用“爆款短视频增长方案包”，只做到草稿闭环。
- 审批策略按“平台基线 -> 方案预设 -> 企业覆盖 -> 工作流局部”分层，下层只能加严不能放宽。
- 行业方案插件是资源包，不是单个工具，运行时仍以授权链路和 Agent 直接 Skill 授权为准。
- 工作流构建能力按“平台工作室 / 企业模板编辑 / 企业简单构建”三层开放，企业端始终遵守“可编排，不可扩核”。
- 触发和发布必须拆开建模，未发布版本不得进入正式自动触发链路。
- 定制交付本质上是平台托管生产能力，不是把复杂开发能力下放给企业。
- 平台必须同时具备可观测性和评估能力，才能从“能跑”升级为“可治理、可优化”。
- 所有运行时入口都应归口到统一策略引擎裁决，避免授权、风险、发布和插件规则四处漂移。
- 企业知识注入必须分容器、分通道、分预算管理，不能把所有业务知识粗暴塞进 Prompt。
- 行业方案必须具备完整生命周期与升级作战机制，平台原件升级、企业激活升级与企业副本升级必须分层治理。
- 工作流平台必须坚持契约优先，所有关键输入输出都应可 Schema 化、版本化、校验化。
- 工作流运行必须被正式建模为带检查点和恢复路径的执行图，不能把复杂运行时退化成线性日志。
- 企业端必须有面向日常运营的正式控制台，围绕待办、审批、异常、结果和优化闭环组织，而不是围绕开发资源组织。
- 方案交付必须沉淀为规格包、验收包、交接包和限制说明包，避免需求、验收和升级口径漂移。
- 平台必须把评估数据集和基准套件当作正式资产治理，不能把评估退化成临时演示或零散样本比较。
- 预算、配额和成本守卫必须进入运行时内核，并按平台、企业、方案、工作流、节点多层联动治理。
- 外部连接能力必须同时治理连接器可信度和动作风险等级，正式写动作必须具备身份、作用域、幂等、回执和预览五个安全要素。
- 人机协作必须被正式建模为组织角色和协作通道，而不能退化成零散人工备注或通用待办。
- 企业数据必须分级分类、分作用域、分用途治理，敏感信息不得无约束进入 Prompt、评估集、日志、导出和外发链路。
- 记忆不是原始聊天堆积，长期学习必须以结构化反馈和人工确认驱动，禁止跨企业无边界自学习。
- 正式生产变更必须经过环境晋级、验证门禁、灰度观察和可回滚快照，禁止在生产上直接活体编辑。
- 平台对外开放能力必须继续继承租户、权限、配额、风险和审计治理，开放入口不等于治理降级。
- 推荐决策能力应成为平台内核，默认输出带证据和假设的决策草案，而不是直接自动执行结论。
- 市场对象必须分层治理，公共市场、定向分发和企业私有模板库不得混为一谈。

## 第一阶段收口说明

当前 `01-30` 已覆盖第一阶段核心蓝图：

- 平台定位、权限、计费、插件与方案体系
- 编排、发布、运行时、审批、预算、连接器、安全与数据边界
- 评估、测试、交付、企业开通、市场治理、推荐决策与开放集成

按当前规划口径，第一阶段核心文档已基本收口。

在此基础上，本目录已经进一步补齐：

- [31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md](./31-master-implementation-roadmap-and-4-agent-parallel-delivery-plan-20260323.md)
- [32-parallel-execution-control-spec-20260323.md](./32-parallel-execution-control-spec-20260323.md)
- [33-cross-agent-contract-matrix-20260323.md](./33-cross-agent-contract-matrix-20260323.md)
- [34-integrator-prompt-and-serial-merge-checklist-20260323.md](./34-integrator-prompt-and-serial-merge-checklist-20260323.md)

现在不仅有平台蓝图，也有可直接落地的：

- 4 AI 并行拆分方案
- 并行执行控制规范
- 跨 AI 契约矩阵
- 主协调者启动与交付作战手册
- 主协调者冻结签收与移交模板
- `git worktree` 初始化命令手册
- 串行集成人执行说明
- 串行集成人最终集成报告模板

## 可选延伸文档

- `39-analytics-semantic-metric-layer-and-indicator-governance-spec-YYYYMMDD.md`
- `40-model-routing-provider-strategy-and-aiops-governance-spec-YYYYMMDD.md`
