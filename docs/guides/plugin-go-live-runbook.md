# 插件系统上线与回滚 Runbook（M209-T12）

## 1. 目标

用于本次插件安全收口改造上线：

- Dispatcher 严格参数注入（request/ctx/db-proxy）
- PluginDbProxy 沙箱增强（session 逃逸封堵）
- PluginContext 受控 license 读取
- `novusdoc` / `novusdoc-pro` / `weather-widget` 规范化改造

## 2. 发布前准入门槛（必须全部满足）

1. 自动化回归通过（含 M502 新增套件）

```bash
python -m pytest tests/plugins/test_contract_lifecycle.py -q
python -m pytest tests/test_plugin_api_dispatcher_security.py tests/test_plugin_loader.py tests/test_plugin_lifecycle_lock.py tests/test_plugin_module_loader.py tests/test_plugin_asset_resolver.py tests/test_plugin_api_dispatcher_context_safety.py tests/test_plugin_license_query_stability.py tests/test_plugin_service_license_activation.py tests/test_plugin_license_verification_policy.py tests/test_plugin_version_manager_locking.py tests/test_plugin_webhook_dispatcher_security.py -q
```

2. 三插件冒烟报告已产出：`docs/guides/plugin-smoke-validation.md`
3. 文档规范已更新：`docs/guides/plugin-developer-guide.md`
4. M502 安全基线检查项全部 PASS（见 smoke 文档覆盖矩阵）

## 3. 灰度发布策略

### Phase 0：预发布环境（100%）

- 部署新版本后执行三插件手工冒烟：
  - novusdoc 文档 CRUD + AI 路径
  - novusdoc-pro license 门控路径
  - weather-widget 配置与天气查询路径
- 观察 30 分钟，关键指标无异常再进入 Phase 1

### Phase 1：生产灰度（10% 流量 / 单租户组）

- 仅放量给白名单租户
- 观察 60 分钟
- 若指标稳定，进入 Phase 2

### Phase 2：生产扩容（50% 流量）

- 扩到半量租户
- 观察 60 分钟
- 若稳定，进入 Phase 3

### Phase 3：全量（100%）

- 全量切换
- 持续观察 24 小时

## 4. 观测指标与阈值

| 指标 | 阈值 | 说明 |
|---|---|---|
| 插件 API 5xx 错误率 | `< 1%` | `/admin/plugins/*/api/*`, `/tenant/plugins/*/api/*` |
| 插件 API P95 延迟 | `< 1.5s` | 按插件维度观测 |
| 403 命中率（db 能力不足） | 基线 ± 20% | 严格注入后可能上升，需确认是否配置问题 |
| handler 加载失败数 | `= 0` | 日志关键字：`handler failed to load` |
| plugin sandbox 拒绝数 | 可解释且稳定 | 关键字：`PluginSecurityError` |

## 5. 回滚触发条件

满足任一条件立即回滚：

1. 连续 10 分钟插件 API 5xx 错误率 >= 3%
2. 大面积 403（非预期权限门控）导致核心功能不可用
3. 任一核心插件（novusdoc / novusdoc-pro / weather-widget）不可用且 15 分钟内无法修复
4. 出现安全风险或数据破坏迹象

## 6. 回滚流程（SOP）

### Step A：业务止血

1. 暂停灰度放量
2. 对异常插件执行禁用（优先禁用问题插件，保留其余插件）

### Step B：版本回滚

1. 回滚后端服务到上一稳定版本
2. 重启服务并执行健康检查
3. 重新执行最小冒烟（novusdoc 列表页 + weather config + novusdoc-pro 门控）

### Step C：数据与迁移评估

1. 确认本次变更是否涉及新迁移分支执行
2. 若涉及，按插件分支评估是否需要 downgrade（避免盲目全局回滚）
3. 保留故障现场日志与请求样本

## 7. 值班与责任

| 角色 | 职责 |
|---|---|
| 发布负责人 | 执行灰度、推进阶段切换、做 go/no-go 决策 |
| 后端负责人 | 指标监控、错误定位、回滚执行 |
| 前端负责人 | 插件页面可用性验证、路径/菜单验证 |
| QA | 冒烟脚本执行与结果留档 |

## 8. 发布记录模板

```md
## 发布记录
- 发布时间：
- 发布版本：
- 灰度阶段：Phase X
- 指标快照：
  - API 5xx：
  - P95：
  - 403 命中：
- 异常与处置：
- 是否进入下一阶段：Yes/No
- 决策人：
```

## 9. 收口要求

- 发布结束后，补充本次发布记录到项目文档
- 若发生回滚，必须输出事故复盘（根因、影响面、修复计划）
