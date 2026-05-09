# 联网搜索退役清理

## 背景

用户在智能体技能分组里仍看到“联网搜索”，但当前新系统规则已经明确：AI 对话 live path 不支持联网搜索、WebResearch、公网 URL fetch 或 provider-hosted/native search。天气等业务能力必须属于插件技能包，主 AI runtime 只接收当前企业/智能体实际解析出的工具元数据，不能用关键字或历史别名硬编码能力。

另有风险：上一轮其它 AI 曾误改 AI 模块并已被用户要求恢复，所以本任务必须以当前工作树代码为证据，逐项复核，不能默认脏改动都是正确的。

## 目标

1. 联网搜索不能作为技能包、技能、智能体绑定、运行时候选工具、provider payload、诊断有效能力或 smoke 验收通过证据出现。
2. `selected_skill_names`、历史中文别名、英文旧名、provider 事件名都不能重新激活联网搜索。
3. 已存在数据库里的联网搜索技能包/技能/授权要在迁移中清退或失效，避免 UI 继续显示为可绑定能力。
4. 天气能力保留为插件能力；主 runtime 不硬编码天气业务逻辑，smoke/e2e 不把天气当成默认 builtin/runtime 能力，也不在没有解析出可执行天气工具时宣称天气可用。
5. 文档和测试表达新系统规则：没有兼容补丁，没有 legacy alias 触发新 turn 的能力。

## 非目标

- 不删除天气插件。
- 不恢复 WebResearch 或公网 fetch 能力。
- 不引入新的 LLM prompt 文本来模拟联网搜索。
- 不做生产 real-dialogue smoke 完整验收；本任务只能提供 structural / behavioral 验证，真实 provider smoke 仍按 testing-discipline 单独归档。

## 验收标准

- 主运行时代码扫描不再发现天气/联网搜索硬编码正向能力分支。
- skill package / skill 创建或更新拒绝联网搜索名称、key、source_ref、source_plugin。
- catalog / repository / agent grant 查询不返回已退役联网搜索能力。
- 运行时非法输入 guard 覆盖 `web_search`、`fetch_url`、`web_research`、`online_search`、hosted/native search、`联网搜索`、`网页搜索`、`百度公开搜索` 等旧名。
- real-dialogue smoke service 能识别候选工具、已选工具、selected skills 和 provider event 中的退役搜索痕迹。
- Alembic 迁移清退历史联网搜索 package / skill / grant。
- 新增或更新测试显式标注 `structural` / `behavioral` / `smoke`，并覆盖两类负例：旧名不能入参激活、历史 catalog 不能绑定或运行；smoke 只能证明真实 provider/replay 的可观察结果，不能用非空回答、历史搜索事件、天气工具命中或“测试通过”当作验收完成。

## 需要验证的命令

从 `backend/` 运行：

```powershell
python -m pytest tests/regressions/test_online_search_capability_removed.py tests/test_skill_resolver.py tests/services/test_agent_skill_grant_service.py tests/services/test_skill_service.py tests/services/test_skill_package_service_contracts.py tests/test_ai_real_dialogue_smoke_service.py -q
python scripts/check_prompt_contracts.py
python scripts/lint_migrations.py
python -m ruff check <touched-files>
python -m ruff format --check <touched-files>
$env:PYTHONPATH='.'; alembic heads
```

扫描：

```powershell
rg -n "mentions_weather|_WEATHER_TERMS|weather|get_current_weather|get_weather_forecast|weather_query|weather_tools|天气|forecast" backend/app/ai backend/app/services/ai -g "*.py"
rg -n "联网搜索|在线搜索|网页搜索|web_search|online_search|web_research|fetch_url|SearchProvider|WebResearch|WebSearch|native_web_search|hosted_web_search" backend/app frontend/apps/web-antd/src ops docs .trellis -g "*.py" -g "*.ts" -g "*.vue" -g "*.json" -g "*.md"
```

第二条扫描允许命中 denylist、清退迁移、测试和历史说明，但不能命中正向能力注册或运行时暴露。
