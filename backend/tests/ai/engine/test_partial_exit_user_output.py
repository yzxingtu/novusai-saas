"""Test type: behavioral
Scope: recovery output rendering and web research evidence salvage.
Mock strategy: no LLM/provider mocks; recovery builders run real logic over fixed tool evidence.
"""

from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.recovery_web_research_gate import (
    WEB_RESEARCH_TERMINAL_CONTRACT_KEY,
    WEB_RESEARCH_TERMINAL_NO_RESULT,
    WEB_RESEARCH_TERMINAL_SEARCH_UNAVAILABLE,
)
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolResult


def _intent(intent_id: str, status: str, label: str) -> IntentPlan:
    return IntentPlan(
        intent_id=intent_id,
        kind="user_request",
        family="general",
        order=1,
        user_visible_label=label,
        source_text="",
        status=status,
        requires_tools=False,
    )


def _web_research_intent() -> IntentPlan:
    return IntentPlan(
        intent_id="intent-web",
        kind="web_research",
        family="web_research",
        order=1,
        user_visible_label="大模型 token 排行",
        source_text="帮我搜索一下2025年大模型使用token排行?",
        status="pending",
        requires_tools=True,
        allowed_tool_names=["fetch_url"],
        completion_signals=["fetch_url"],
    )


def _token_rank_fetch_result(
    *,
    description: str,
    summary: str,
    body: str | None,
) -> ToolResult:
    title = "沙利文发布《中国GenAI市场洞察：企业级大模型调用全景研究2025H2》报告，阿里云份额第一-阿里云"
    output_body = (
        body
        if body is not None
        else (
            "千问大模型以32%的份额位居中国企业级大模型调用份额第一\n\n"
            "报告详情\n\n"
            "国际市场调研机构沙利文（Frost&Sullivan）发布了最新一期《中国GenAI市场洞察：企业级大模型调用全景研究2025H2》报告，"
            "调研用户通过公有云、本地部署、MaaS等使用大模型的不同方式，盘点中国企业级大模型调用市场的全景。"
            "2025年下半年，中国企业级市场大模型的日均总消耗量为37万亿Tokens，其中，千问大模型占比32.1%位列第一。\n"
        )
    )
    output = (
        "Content from https://www.aliyun.com/analyst-reports/frost-genai-2025h2:\n"
        f"Title: {title}\n"
        f"Description: {description}\n\n"
        f"{output_body}"
    )
    return ToolResult(
        tool_call_id="tc-fetch",
        name="fetch_url",
        success=True,
        output=output,
        summary=summary,
        summary_payload={
            "fetch_url": True,
            "ok": True,
            "title": title,
            "description": description,
            "summary": summary,
        },
    )


def test_partial_exit_user_output_is_user_focused() -> None:
    intents = [
        _intent("intent-1", "completed", "Gather weather data"),
        _intent("intent-2", "completed", "Summarize the page"),
        _intent("intent-3", "pending", "Investigate remaining details"),
    ]

    output = RecoveryManager.build_partial_output(
        intents,
        reason="retry_budget_exhausted",
        provider_failure_kind="tool_timeout",
    )

    # Must not leak internal template markers or English metadata
    assert "[PARTIAL EXIT]" not in output
    assert "Failure kind" not in output
    assert "Reason:" not in output
    # Completed / unfinished labels should appear in natural text
    assert "Gather weather data" in output
    assert "Summarize the page" in output
    assert "Investigate remaining details" in output


def test_partial_exit_user_output_uses_partial_search_results_before_retry_exhausted_message() -> (
    None
):
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="新闻来源",
            source_text="查今天 AI 新闻",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["web_search", "fetch_url"],
            completion_signals=["fetch_url"],
            metadata={
                "partial_result": (
                    "AI News Daily - https://example.com/ai-news；"
                    "OpenAI Updates - https://example.com/openai"
                )
            },
        )
    ]

    output = RecoveryManager.build_partial_output(
        intents,
        reason="retry_budget_exhausted",
        provider_failure_kind="none",
    )

    assert "AI News Daily" in output
    assert "OpenAI Updates" in output
    assert "目前拿到的结果" in output
    assert "还需要继续核验" in output
    assert "如果你愿意，我可以继续" not in output


def test_partial_exit_user_output_hides_unfinished_web_results_after_provider_failure() -> (
    None
):
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="新闻来源",
            source_text="查今天 AI 新闻",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["web_search", "fetch_url"],
            completion_signals=["fetch_url"],
            metadata={
                "partial_result": (
                    "AI News Daily - https://example.com/ai-news；"
                    "OpenAI Updates - https://example.com/openai"
                )
            },
        )
    ]

    output = RecoveryManager.build_partial_output(
        intents,
        reason="provider_failure_after_partial_progress",
        provider_failure_kind="provider_http_5xx",
    )

    assert "AI News Daily" not in output
    assert "OpenAI Updates" not in output
    assert "目前拿到的结果" not in output
    assert "被系统中断了，请稍后再试。" in output


def test_update_intent_statuses_caches_partial_result_for_unfinished_search_intent() -> (
    None
):
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="新闻来源",
            source_text="查今天 AI 新闻",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["web_search", "fetch_url"],
            completion_signals=["fetch_url"],
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tool-1",
                name="web_search",
                success=True,
                summary_payload={
                    "items": [
                        {
                            "title": "AI News Daily",
                            "url": "https://example.com/ai-news",
                        },
                        {
                            "title": "OpenAI Updates",
                            "url": "https://example.com/openai",
                        },
                    ]
                },
            )
        ],
    )

    assert updated[0].status == "pending"
    assert "partial_result" in (updated[0].metadata or {})
    assert "AI News Daily" in updated[0].metadata["partial_result"]
    assert updated[0].allowed_tool_names == ["fetch_url"]
    assert updated[0].preferred_tool_names == ["fetch_url"]
    assert updated[0].completion_signals == ["fetch_url"]
    assert updated[0].metadata["requires_fetch_url"] is True
    assert updated[0].metadata["fetch_url_candidate_urls"] == [
        "https://example.com/ai-news",
        "https://example.com/openai",
    ]
    assert updated[0].metadata["fetch_url_attempted_urls"] == []
    assert updated[0].metadata["fetch_url_blocked_urls"] == []


def test_update_intent_statuses_marks_web_search_zero_results_as_completed() -> None:
    intents = [
        IntentPlan(
            intent_id="intent-1",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="AI 新闻",
            source_text="查今天 AI 新闻",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["web_search", "fetch_url"],
            completion_signals=["fetch_url"],
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tool-1",
                name="web_search",
                success=True,
                output="No results found for: AI news",
                summary_payload={
                    "status": "no_results",
                    "result_count": 0,
                    "items": [],
                },
            )
        ],
    )

    assert updated[0].status == "completed"
    assert updated[0].completed_by_tool_names == ["web_search"]
    assert updated[0].cached_result is not None
    assert "没有找到" in updated[0].cached_result
    assert updated[0].metadata.get("requires_fetch_url") is None
    assert (
        updated[0].metadata["auto_fetch_gate_reason"] == "search_no_results_completed"
    )
    assert (
        updated[0].metadata[WEB_RESEARCH_TERMINAL_CONTRACT_KEY]
        == WEB_RESEARCH_TERMINAL_NO_RESULT
    )


def test_update_intent_statuses_uses_fetch_body_preview_for_web_research_result() -> (
    None
):
    intents = [
        IntentPlan(
            intent_id="intent-web",
            kind="web_research",
            family="web_research",
            order=1,
            user_visible_label="放假时间",
            source_text="湖南学生放假时间",
            status="pending",
            requires_tools=True,
            allowed_tool_names=["fetch_url"],
            completion_signals=["fetch_url"],
        )
    ]

    updated = RecoveryManager.update_intent_statuses(
        intents,
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch",
                name="fetch_url",
                success=True,
                output=(
                    "Content from https://finance.sina.com.cn/jjxw/2025-06-12/doc-inezupah3848475.shtml\n"
                    "Title: 放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网\n"
                    "Description: 近日湖南12地公布2025年中小学暑假放假时间长沙根据2024年校历安排，今年暑假从7月6日开始。\n"
                    "Key sections: 放假通知！湖南12地明确！, VIP课程推荐\n\n"
                    "放假通知！湖南12地明确！\n"
                    "湖南12地公布2025年中小学暑假放假时间。\n"
                    "根据2024年校历安排，今年暑假从7月6日开始。\n"
                    "2025学年第一学期：2025年9月1日上课，2026年1月31日结束。\n"
                ),
                summary="放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
                summary_payload={
                    "fetch_url": True,
                    "ok": True,
                    "title": "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
                    "description": "近日湖南12地公布2025年中小学暑假放假时间长沙根据2024年校历安排，今年暑假从7月6日开始。",
                    "summary": "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网",
                },
            )
        ],
    )

    assert updated[0].status == "completed"
    assert "今年暑假从7月6日开始" in updated[0].cached_result
    assert (
        updated[0].cached_result
        != "放假通知！湖南12地明确！|特殊教育学校_新浪财经_新浪网"
    )


def test_update_intent_statuses_uses_body_when_fetch_summary_description_is_incomplete() -> (
    None
):
    description = "国际市场调研机构沙利文（Frost&Sullivan）发布了最新一期《中国GenAI市场洞察：企业级大模型调用全景研究2025H2》报告，调研用户通过"
    summary = (
        "沙利文发布《中国GenAI市场洞察：企业级大模型调用全景研究2025H2》报告，阿里云份额第一-阿里云 - "
        f"{description}"
    )

    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[
            _token_rank_fetch_result(
                description=description,
                summary=summary,
                body=None,
            )
        ],
    )

    assert updated[0].status == "completed"
    assert "37万亿Tokens" in (updated[0].cached_result or "")
    assert "千问大模型占比32.1%位列第一" in (updated[0].cached_result or "")
    assert "报告详情" not in (updated[0].cached_result or "")
    assert not str(updated[0].cached_result or "").endswith("调研用户通过")


def test_update_intent_statuses_uses_body_when_fetch_summary_has_truncated_marker() -> (
    None
):
    description = (
        "沙利文报告显示，2025年下半年中国企业级市场大模型调用规模继续扩大，"
        "头部模型份额进一步集中。"
    )
    summary = (
        "沙利文发布《中国GenAI市场洞察：企业级大模型调用全景研究2025H2》报告 - "
        "沙利文报告显示，2025年下半年中国企业级市场大模型调用规模继续扩大... [truncated]"
    )
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[
            _token_rank_fetch_result(
                description=description,
                summary=summary,
                body=None,
            )
        ],
    )

    assert updated[0].status == "completed"
    assert "37万亿Tokens" in (updated[0].cached_result or "")
    assert "千问大模型占比32.1%位列第一" in (updated[0].cached_result or "")
    assert "[truncated]" not in (updated[0].cached_result or "")


def test_update_intent_statuses_uses_body_when_fetch_summary_is_generic_fetched_url() -> (
    None
):
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch",
                name="fetch_url",
                success=True,
                output=(
                    "Content from https://mp.weixin.qq.com/s/example:\n"
                    "Redirected from: http://www.baidu.com/link?url=example\n\n"
                    "全球知名的大模型盲测榜单LMArena更新了新一期排名，"
                    "阿里巴巴千问最新旗舰模型预览版Qwen3.5-Max-Preview首度亮相，"
                    "斩获1464分，超过了GPT5.4、Grok4.1等海外模型。\n\n"
                    "此外，LMArena基于各公司最强模型对全球大模型机构进行排名，"
                    "5家中国公司闯进前十，阿里位列全球前五、中国第一。\n"
                ),
                summary="Fetched https://mp.weixin.qq.com/s/example",
                summary_payload={
                    "fetch_url": True,
                    "ok": True,
                    "requested_url": "http://www.baidu.com/link?url=example",
                    "final_url": "https://mp.weixin.qq.com/s/example",
                    "title": None,
                    "description": None,
                    "summary": "Fetched https://mp.weixin.qq.com/s/example",
                },
            )
        ],
    )

    assert updated[0].status == "completed"
    assert "Qwen3.5-Max-Preview首度亮相" in (updated[0].cached_result or "")
    assert "阿里位列全球前五、中国第一" in (updated[0].cached_result or "")
    assert "Fetched https://mp.weixin.qq.com/s/example" not in (
        updated[0].cached_result or ""
    )


def test_completed_output_uses_fetch_body_for_recovered_user_visible_answer() -> None:
    description = "国际市场调研机构沙利文（Frost&Sullivan）发布了最新一期《中国GenAI市场洞察：企业级大模型调用全景研究2025H2》报告，调研用户通过"
    summary = (
        "沙利文发布《中国GenAI市场洞察：企业级大模型调用全景研究2025H2》报告，阿里云份额第一-阿里云 - "
        f"{description}"
    )
    tool_result = _token_rank_fetch_result(
        description=description,
        summary=summary,
        body=None,
    )
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[tool_result],
    )

    output = RecoveryManager.build_completed_output(
        updated,
        tool_results=[tool_result],
        reason="partial_exit_recovery",
    )

    assert "37万亿Tokens" in output
    assert "千问大模型占比32.1%位列第一" in output
    assert "报告详情" not in output
    assert not output.endswith("调研用户通过")


def test_update_intent_statuses_keeps_complete_fetch_summary_when_body_is_absent() -> (
    None
):
    description = (
        "2025年中国企业级大模型市场爆发增长，日均调用量突破10万亿tokens。"
        "阿里通义以17.7%份额领跑。"
    )
    summary = f"中国企业调用大模型日均超10万亿Tokens，阿里通义份额第一 - {description}"
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[
            _token_rank_fetch_result(
                description=description,
                summary=summary,
                body="",
            )
        ],
    )

    assert updated[0].status == "completed"
    assert updated[0].cached_result == summary


def test_update_intent_statuses_does_not_promote_failed_fetch_url_evidence() -> None:
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch",
                name="fetch_url",
                success=False,
                error="HTTP 502 while fetching https://example.com/report",
                summary="截断但失败的网页摘要",
                summary_payload={
                    "fetch_url": True,
                    "ok": False,
                    "title": "失败报告",
                    "description": "失败摘要",
                    "summary": "失败报告 - 失败摘要",
                },
            )
        ],
    )

    assert updated[0].status == "pending"
    assert updated[0].cached_result is None
    assert "partial_result" not in (updated[0].metadata or {})


def test_update_intent_statuses_does_not_promote_low_relevance_fetch_url_evidence() -> (
    None
):
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch-low-relevance",
                name="fetch_url",
                success=True,
                output=(
                    "Content from https://baijiahao.baidu.com/s?id=1860091565873698107:\n"
                    "Title: 2026大模型创新TOP100\n\n"
                    "AI信息操控。3·15晚会曝光AI大模型投毒黑产，"
                    "GEO服务商通过软文影响AI推荐，随后讨论OpenClaw和token调用量。"
                ),
                summary="2026大模型创新TOP100",
                summary_payload={
                    "fetch_url": True,
                    "ok": True,
                    "title": "2026大模型创新TOP100",
                    "summary": "2026大模型创新TOP100",
                    "relevance_status": "low_relevance",
                    "relevance_reason": "low_query_relevance",
                    "web_research_evidence": {
                        "status": "partial",
                        "answer_quality": "none",
                        "failure_kind": "low_query_relevance",
                        "diagnostics": {
                            "evidence_status": "partial",
                            "answer_source": "none",
                            "failure_kind": "low_query_relevance",
                            "fetched_urls": [],
                            "rejected_urls": [
                                "https://baijiahao.baidu.com/s?id=1860091565873698107"
                            ],
                        },
                    },
                },
            )
        ],
    )

    assert updated[0].status == "pending"
    assert updated[0].completed_by_tool_names == []
    assert updated[0].cached_result is None
    assert "partial_result" not in (updated[0].metadata or {})
    assert updated[0].metadata["fetch_url_answer_quality"] == "missing"


def test_update_intent_statuses_does_not_complete_title_only_fetch_url_evidence() -> (
    None
):
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch",
                name="fetch_url",
                success=True,
                output=(
                    "Content from https://example.com/ranking:\n"
                    "Title: 2026大模型战力榜\n"
                ),
                summary="2026大模型战力榜",
                summary_payload={
                    "fetch_url": True,
                    "ok": True,
                    "title": "2026大模型战力榜",
                    "summary": "2026大模型战力榜",
                },
            )
        ],
    )

    assert updated[0].status == "pending"
    assert updated[0].completed_by_tool_names == []
    assert updated[0].cached_result is None
    assert updated[0].metadata["fetch_url_answer_quality"] == "missing"


def test_update_intent_statuses_records_search_unavailable_terminal_contract() -> None:
    intent = IntentPlan(
        intent_id="intent-web",
        kind="web_research",
        family="web_research",
        order=1,
        user_visible_label="AI 新闻",
        source_text="查今天 AI 新闻",
        status="pending",
        requires_tools=True,
        allowed_tool_names=["web_search", "fetch_url"],
        preferred_tool_names=["web_search", "fetch_url"],
        completion_signals=["fetch_url"],
    )

    updated = RecoveryManager.update_intent_statuses(
        [intent],
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch",
                name="fetch_url",
                success=True,
                output="Content from https://example.com/news:\nTitle: AI 新闻",
                summary="AI 新闻",
                summary_payload={
                    "fetch_url": True,
                    "ok": True,
                    "title": "AI 新闻",
                    "summary": "AI 新闻",
                },
            )
        ],
    )

    assert updated[0].status == "completed"
    assert updated[0].completed_by_tool_names == ["fetch_url"]
    assert updated[0].metadata["auto_fetch_gate_reason"] == "search_not_successful"
    assert (
        updated[0].metadata[WEB_RESEARCH_TERMINAL_CONTRACT_KEY]
        == WEB_RESEARCH_TERMINAL_SEARCH_UNAVAILABLE
    )
    assert "fetch_url_answer_quality" not in updated[0].metadata


def test_update_intent_statuses_does_not_complete_ok_false_fetch_url_payload() -> None:
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[
            ToolResult(
                tool_call_id="tc-fetch",
                name="fetch_url",
                success=True,
                output="Content from https://example.com/ranking:\n正文看起来存在。",
                summary="2026大模型战力榜 - 正文看起来存在。",
                summary_payload={
                    "fetch_url": True,
                    "ok": False,
                    "title": "2026大模型战力榜",
                    "description": "正文看起来存在。",
                    "summary": "2026大模型战力榜 - 正文看起来存在。",
                },
            )
        ],
    )

    assert updated[0].status == "pending"
    assert updated[0].completed_by_tool_names == []
    assert updated[0].cached_result is None
    assert updated[0].metadata["fetch_url_answer_quality"] == "missing"


def test_recovery_does_not_complete_required_fetch_url_from_search_only_evidence() -> (
    None
):
    intent = _web_research_intent()
    intent.metadata = {
        "requires_fetch_url": True,
        "auto_fetch_gate_reason": "candidate_urls_ready",
        "fetch_url_candidate_urls": [
            "http://www.baidu.com/link?url=example-token-ranking"
        ],
        "partial_result": (
            "日耗37万亿 Tokens ,千问稳居第一 - "
            "http://www.baidu.com/link?url=example-token-ranking"
        ),
    }

    recovered_intents, recovered_output = (
        RecoveryManager.recover_web_search_output_from_evidence(
            [intent],
            tool_results=[
                ToolResult(
                    tool_call_id="tc-search",
                    name="web_search",
                    success=True,
                    summary="baidu_public: 1 result(s)",
                    summary_payload={
                        "status": "success",
                        "result_count": 1,
                        "items": [
                            {
                                "title": "日耗37万亿 Tokens ,千问稳居第一",
                                "url": "http://www.baidu.com/link?url=example-token-ranking",
                                "snippet": "沙利文报告显示，中国企业级大模型日均调用量为37万亿Tokens。",
                            }
                        ],
                    },
                )
            ],
            reason="retry_budget_exhausted",
        )
    )

    assert recovered_output == ""
    assert recovered_intents[0].status == "pending"
    assert recovered_intents[0].completed_by_tool_names == []
    assert recovered_intents[0].metadata["requires_fetch_url"] is True
