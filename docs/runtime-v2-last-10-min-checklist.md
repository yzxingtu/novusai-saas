# Runtime-v2 上线前最后 10 分钟检查命令清单

适用范围：
- 发布前最后一次 canary / 预发检查
- runtime-v2 灰度前从 `legacy` 切到 `shadow` 或 `pageaware_only`
- 灰度放量前快速确认 page-aware / fallback / turn diagnostics 正常

默认工作目录：

```powershell
cd E:\git_clone\novusai-saas-yudi\backend
```

## 1. 先确认运行时开关

```powershell
Get-ChildItem Env:CLAUDE_CODE_STYLE_RUNTIME
Get-ChildItem Env:CLAUDE_CODE_STYLE_RUNTIME_SHADOW_ENABLED
Get-ChildItem Env:CLAUDE_CODE_STYLE_RUNTIME_SHADOW_SAMPLE_RATE
Get-ChildItem Env:CLAUDE_CODE_STYLE_RUNTIME_SHADOW_MAX_PER_MINUTE
Get-ChildItem Env:CLAUDE_CODE_STYLE_RUNTIME_SHADOW_WHITELIST
```

判定标准：
- `legacy`：只做基线，不验证 runtime-v2 用户结果
- `shadow`：只允许低采样或白名单
- `pageaware_only`：只允许 page-aware 场景进入 runtime-v2
- `active`：确认前面 3 档都已经稳定

## 2. 跑最小后端回归

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests\ai\engine\test_tool_invocation_planner.py -q
& '.\.venv\Scripts\python.exe' -m pytest tests\services\test_conversation_engine_prepare_execution.py -k "local_page_content_request or prefers_current_time_tool_for_time_question or explicit_web_request" -q
& '.\.venv\Scripts\python.exe' -m pytest tests\services\test_runtime_v2_replay.py -k "after_chunk or failure_before_first_chunk" -q
& '.\.venv\Scripts\python.exe' -m pytest tests\test_openai_adapter_responses.py -k "fallback" -q
```

判定标准：
- 这 4 组至少全绿
- 若任何一组失败，不进入放量

如有 5-10 分钟窗口，再补一轮 CI 对齐边界：

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/ -x --tb=short -q
```

判定口径：
- 该命令用于识别“仓库全量基线状态”，不是 runtime-v2 单独放行门槛
- 若失败点与 runtime-v2 无直接关系（如插件历史基线、环境依赖、公共配置只读属性 monkeypatch），记录后可继续按 runtime-v2 专项指标灰度

## 3. 用 CLI 抽检真实对话

先抽 page-aware 样本：

```powershell
& '.\.venv\Scripts\python.exe' -m app.cli ai conversation show 580 --tail 16 --full-content
```

重点看：
- `tool_calls` 是否真的调用了 `get_page_context` / `pageop_*`
- assistant `metadata.context_diagnostics.tool_planner.family` 是否为 `page_ops`
- `Recent call logs` 是否为 success

再抽已知历史问题样本：

```powershell
& '.\.venv\Scripts\python.exe' -m app.cli ai conversation show 579 --tail 12 --full-content
& '.\.venv\Scripts\python.exe' -m app.cli ai conversation show 577 --tail 12 --full-content
& '.\.venv\Scripts\python.exe' -m app.cli ai conversation show 584 --tail 12 --full-content
& '.\.venv\Scripts\python.exe' -m app.cli ai conversation show 586 --tail 20 --full-content
& '.\.venv\Scripts\python.exe' -m app.cli ai conversation show 589 --tail 12 --full-content
& '.\.venv\Scripts\python.exe' -m app.cli ai conversation show 597 --tail 12 --full-content
& '.\.venv\Scripts\python.exe' -m app.cli ai conversation show 599 --tail 20 --full-content
```

判定标准：
- `579` 可以作为“旧样本”对照，确认它当时确实卡在 `family=none`
- `580` 必须已经体现出 page-aware 工具调用成功
- `577` 用于确认旧 page-aware 问题现在已经有测试和修复覆盖
- `584` 应能直接看到 `get_current_weather` 的 tool call，且 `tool_planner.family=weather`
- `586` 应体现完整 weather 续执行链：先 pending consent，再在批准后真正执行 `get_current_weather`，最后 assistant 根据工具结果给出自然语言反馈
- `589` 是 `588` 同型混合请求（头疼 + 天气 + page_context）的修复后对照样本：第一跳应直接是 `get_current_weather`，而不是 `get_page_context`
- `597` 是天气链路健康样本：应看到 `pending_consent -> get_current_weather 成功执行 -> assistant 自然语言总结`
- `599` 是 mixed page-aware + weather 边界样本：当前可接受现象是工具集合同时暴露 page/weather，但若页面会话缺失会先出现 `pageop_* session_not_found`，需要继续观察是否发生反复 `get_page_context` 循环

## 4. 检查最近日志中的工具策略

查看最近 120 条相关日志：

```powershell
Select-String -Path 'logs\app.log' -Pattern 'Prepare execution tool policy|Tool selection status|runtime_v2_stream_fallback|runtime_v2_stream_failure_after_chunk' | Select-Object -Last 120
```

重点看：
- `family=page_ops` 时 `selected_tool_count` 不应为 `0`
- `page_context_present=True` 且用户在问页面内容时，不应再出现 `family=none`
- 若出现 `runtime_v2_stream_failure_after_chunk=True`，属于已出 chunk 后失败，需要重点看灰度指标
- 若出现 `runtime_v2_stream_fallback=legacy_stream` 或 `sync_chat`，需要确认比例没有异常上升

## 5. 快速技能探针

```powershell
@'
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.types import ExecutionRequest
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

class _FakeRouter:
    def __init__(self, db):
        self.db = db
    async def route(self, agent, request, estimated_tokens, tools=None):
        _ = agent, request, estimated_tokens, tools
        return None

def _build_agent():
    return SimpleNamespace(
        id=59,
        name='Verifier',
        system_prompt='You are {{ agent_name }}.',
        rag_config=None,
        context_config=None,
        temperature=0.2,
        max_tokens=1024,
        top_p=1.0,
        model=SimpleNamespace(
            supports_audio=False,
            supports_video=False,
            supports_vision=False,
        ),
    )

def _skill_result():
    return SkillResolveResult(
        tools=[
            ToolDefinition(name='web_search', description='Search the web'),
            ToolDefinition(name='fetch_url', description='Fetch a webpage'),
            ToolDefinition(name='get_page_context', description='Read page context'),
            ToolDefinition(name='invoke_page_operation', description='Operate page'),
            ToolDefinition(name='get_current_weather', description='Get current weather'),
            ToolDefinition(name='get_weather_forecast', description='Get weather forecast'),
            ToolDefinition(name='data_query', description='Query platform data'),
            ToolDefinition(name='get_current_time', description='Get current time'),
        ]
    )

async def probe(label, prompt, input_variables=None):
    engine = ConversationEngine(db=MagicMock(), gateway=MagicMock(), sandbox=MagicMock())
    request = ExecutionRequest(
        agent_id=59,
        tenant_id=0,
        user_id=1,
        messages=[ChatMessage(role='user', content=prompt)],
        input_variables=input_variables or {},
    )
    with (
        patch('app.ai.rag_injector.load_agent_kb_bindings', new=AsyncMock(return_value=([], {}))),
        patch('app.ai.routing.router.ModelRouter', new=_FakeRouter),
    ):
        prep = await engine._prepare_execution(_build_agent(), request, skill_result=_skill_result())
    print({
        'label': label,
        'family': prep.tool_use_policy.family,
        'mode': prep.tool_use_policy.mode,
        'reason': prep.tool_use_policy.reason,
        'selected_tool_names': [tool.name for tool in prep.tools],
    })

async def main():
    await probe('page', '看看本页面的内容', {'page_context': {'page_key': 'admin.ai.conversations', 'page_data': {'available_operations': [{'name': 'read_visible_rows', 'readonly': True}]}}})
    await probe('web', '联网查一下最近乌克兰的局势')
    await probe('time', '现在几点了')
    await probe('data', '查询这条记录的明细')
    await probe('weather', '今天北京天气怎么样？')

asyncio.run(main())
'@ | & '.\.venv\Scripts\python.exe' -
```

判定标准：
- `page` / `web` / `time` / `data` / `weather` 都不应落到 `family=none`
- `conversation 580` 的后两轮天气提问可以作为修复前历史样本：当时 CLI 输出 `tool_planner.family=none`，日志也在 `backend/logs/app.log` 第 8616/8634 行记录了 `allowed_tool_names=[]`；若修复后新探针仍重现同类结果，暂停放量
- `conversation 584` 可以作为 weather 工具调用中间态样本：CLI 能看到 `get_current_weather` tool call 和 pending consent
- `conversation 586` 可以作为修复后真实续执行样本：批准 consent 后工具真正执行，CLI 可看到 `get_current_weather` 的失败结果与 assistant 的自然语言总结
- `conversation 589` 可以作为 `588` 修复后的 mixed-intent 正样本：即使存在健康表述和页面上下文，CLI 仍应先发起 weather tool call
- `conversation 584` 发生的 `get_current_weather` tool call 带上了 `pending_consent` payload（CLI 里 `tool_calls` 记录 `pending_consent` 字段，后续 tool response 直接回复 `requires_confirmation=true`），这是 weather 工具正常等待用户授权的中间态，不应该被误判为 runtime-v2 失败；只要日志/CLI 继续显示 pending consent+tool response，就说明 weather tool 已经接入，只等用户确认即可

## 6. 前端最小放行检查

切到前端目录后执行：

```powershell
cd E:\git_clone\novusai-saas-yudi\frontend
pnpm run check:type
pnpm run build
```

判定标准：
- `check:type` 必须通过
- `build` 必须通过
- `lint` 当前不是 runtime-v2 放量阻塞项，但失败点要单独记录

## 7. 放量前最终口径

可以放量：
- `580` 这类 page-aware 真样本已成功调用页面工具
- `584` 这类 weather 真样本已成功进入天气工具链
- `586` 这类 weather 真样本已完成 consent 后续执行，不再重复 ask
- `589` 这类 mixed-intent weather 真样本已不再误落到 page tools
- `597` 这类 weather 真样本已能稳定完成从 consent 到执行到回答的闭环
- page-aware 对应回归测试全绿
- weather 探针已进入 `family=weather`
- `runtime_v2_stream_failure_after_chunk` 没有异常激增
- `shadow` 成本和 diff 比例在预期内

暂缓全量：
- 最近日志里再次出现 page-aware 请求却 `family=none` 且 `selected_tool_count=0`
- `runtime_v2_stream_fallback` 激增
- `Engine stream upstream failed` 激增
- 天气探针仍落到 `family=none`
- mixed 请求（如先看页面再查天气）出现大量重复 `get_page_context` 且没有推进到目标工具执行

## 8. 快速回滚命令

```powershell
$env:CLAUDE_CODE_STYLE_RUNTIME='legacy'
$env:CLAUDE_CODE_STYLE_RUNTIME_SHADOW_ENABLED='false'
```

然后滚动重启对应实例，并再次执行：

```powershell
Select-String -Path 'logs\app.log' -Pattern 'runtime_v2|shadow compare|runtime_v2_stream_fallback' | Select-Object -Last 60
```

判定标准：
- runtime-v2 相关日志快速下降
- 新流量恢复 legacy 行为
