"""
Test type: behavioral
Regression for: BUG-2026-05-04-2280
Original symptom: completed fetch_url recovery for conversation 2280 finalized
only the first preface line while the fetched body contained the requested Top 10
ranking.
Scope: recovery evidence rendering from successful fetch_url body text.
Mock strategy: no LLM/provider/tool executor mocks; inputs are recorded-shaped
ToolResult evidence from conversation 2280.
"""

from __future__ import annotations

from app.ai.engine.recovery_manager import RecoveryManager
from app.ai.engine.types import IntentPlan
from app.ai.tools.types import ToolResult
from app.services.ai.recovery_evidence_read_model import (
    LEGACY_RECOVERY_EVIDENCE_REPAIR_SCOPE,
    patch_recovery_evidence_answer_payload,
)


def _web_research_intent() -> IntentPlan:
    return IntentPlan(
        intent_id="intent-1",
        kind="web_research",
        family="web_research",
        order=1,
        user_visible_label="大模型排行榜",
        source_text="查一下大模型排行榜 2026  水平排行！",
        status="pending",
        requires_tools=True,
        allowed_tool_names=["fetch_url"],
        completion_signals=["fetch_url"],
    )


def _conversation_2280_fetch_result() -> ToolResult:
    title = "2026大模型战力榜：一句话看懂谁称王"
    body = (
        "Content from https://baijiahao.baidu.com/s?id=1855137075962049705&wfr=spider&for=pc:\n"
        "Redirected from: http://www.baidu.com/link?url=example-ranking\n"
        f"Title: {title}\n\n"
        "01 榜单来源与权重\n\n"
        "目前（2026年1月20日），大模型排行榜主要参考 四条权威数据线 ：\n\n"
        "LMArena盲测人类偏好（最接近“谁更好用”）\n\n"
        "Artificial Analysis综合智能指数\n\n"
        "illm-stats.com聚合榜单\n\n"
        "OpenRouter等实际使用量（反映真实市场选择）\n\n"
        "不同榜单侧重点不同：\n\n"
        "LMArena ：真实人类盲测，偏好得分最直观\n\n"
        "综合基准 （GPQA、SWE-bench、AIME）：硬核能力见真章\n\n"
        "使用量/流行度 ：谁被企业高频调用，谁就占C位\n\n"
        "02 2026年1月综合Top 10口诀版\n\n"
        "（融合LMArena偏好 + 基准表现 + 近期报道，排名有轻微主观综合，不同榜单Top 3可能互换）\n\n"
        "❒ 1. Gemini 3 Pro（Google）——最稳王者\n\n"
        "LMArena Text榜首（Elo ~1489–1492）\n\n"
        "❒ 2. Claude Opus 4.5（Anthropic）——编码之神\n\n"
        "SWE-bench编码得分 80%+ ，agent能力顶尖\n\n"
        "❒ 3. GPT-5.2（OpenAI）——推理核弹\n\n"
        "推理、数学、速度三项 部分基准第一\n\n"
        "❒ 4. Grok 4.1（xAI）/Grok 4.1 Thinking——黑马冲榜\n\n"
        "LMArena Elo ~1480+，紧追前三\n\n"
        "❒ 5. Gemini 3 Flash（Google）——性价比之王\n\n"
        "速度快、价格低，LMArena排名靠前\n\n"
        "❒ 6. Claude Sonnet 4.5（Anthropic）——平衡快枪手\n\n"
        "速度比Opus快很多，使用量巨大（OpenRouter常Top 1–2）\n\n"
        "❒ 7. DeepSeek/Doubao系列（字节）——中国突围代表\n\n"
        "部分硬核基准（数学/代码） 冲进前十\n\n"
        "❒ 8. Qwen系列（阿里通义千问）或MiniMax M系列——场景尖兵\n\n"
        "在垂直行业与使用量榜单非常靠前\n\n"
        "❒ 9. Llama 4/Llama系列最新（Meta）——开源天花板\n\n"
        "开源社区“天花板”级别参数规模\n\n"
        "❒ 10. MiMo/Xiaomi系列或Moonshot Kimi等中国闭源强模型——本地之王\n\n"
        "使用量与某些垂直场景 稳居头部\n"
    )
    return ToolResult(
        tool_call_id="call-fetch",
        name="fetch_url",
        success=True,
        output=body,
        summary=title,
        summary_payload={
            "fetch_url": True,
            "ok": True,
            "requested_url": "http://www.baidu.com/link?url=example-ranking",
            "final_url": "https://baijiahao.baidu.com/s?id=1855137075962049705&wfr=spider&for=pc",
            "title": title,
            "description": None,
            "summary": title,
        },
    )


def _inline_2280_fetch_result() -> ToolResult:
    result = _conversation_2280_fetch_result()
    body_lines = [
        line.strip()
        for line in str(result.output or "").splitlines()
        if line.strip()
        and not line.startswith(("Content from ", "Redirected from: ", "Title: "))
    ]
    return ToolResult(
        tool_call_id=result.tool_call_id,
        name=result.name,
        success=True,
        output=(
            "Content from https://baijiahao.baidu.com/s?id=1855137075962049705:\n"
            "Title: 2026大模型战力榜：一句话看懂谁称王\n\n"
            f"{' '.join(body_lines)}"
        ),
        summary=result.summary,
        summary_payload=dict(result.summary_payload or {}),
    )


def _build_output(fetch_result: ToolResult) -> str:
    updated = RecoveryManager.update_intent_statuses(
        [_web_research_intent()],
        messages=[],
        tool_results=[fetch_result],
    )
    output = RecoveryManager.build_completed_output(
        updated,
        tool_results=[fetch_result],
        reason="partial_exit_recovery",
    )

    assert updated[0].status == "completed"
    assert updated[0].completed_by_tool_names == ["fetch_url"]
    return output


def test_bug_2026_05_04_2280_keeps_ranked_fetch_body_in_recovery_output() -> None:
    output = _build_output(_conversation_2280_fetch_result())

    assert "02 2026年1月综合Top 10口诀版" in output
    assert "1. Gemini 3 Pro" in output
    assert "2. Claude Opus 4.5" in output
    assert "3. GPT-5.2" in output
    assert "10. MiMo/Xiaomi系列或Moonshot Kimi" in output
    assert "Content from " not in output
    assert "Redirected from:" not in output
    assert "http://www.baidu.com/link" not in output
    assert not output.strip().endswith("四条权威数据线 ：")


def test_bug_2026_05_04_2280_splits_inline_ranked_fetch_body() -> None:
    output = _build_output(_inline_2280_fetch_result())

    assert "02 2026年1月综合Top 10口诀版" in output
    assert "1. Gemini 3 Pro" in output
    assert "5. Gemini 3 Flash" in output
    assert "10. MiMo/Xiaomi系列或Moonshot Kimi" in output
    assert not output.strip().endswith("四条权威数据线 ：")


def test_bug_2026_05_04_2280_read_model_repairs_historical_short_answer() -> None:
    fetch_result = _conversation_2280_fetch_result()
    preview = _build_output(fetch_result)
    message = {
        "conversation_id": 2280,
        "role": "assistant",
        "created_at": "2026-05-03T20:46:49.740473+00:00",
        "content": "01 榜单来源与权重 目前（2026年1月20日），大模型排行榜主要参考 四条权威数据线 ：",
        "metadata": {
            "turn_record": {
                "final_output_source": "recovery_evidence",
                "turn_flow": {
                    "answer_card": {
                        "summary": "01 榜单来源与权重 目前（2026年1月20日），大模型排行榜主要参考 四条权威数据线 ：",
                        "sections": [
                            {
                                "title": "Answer",
                                "content": "01 榜单来源与权重 目前（2026年1月20日），大模型排行榜主要参考 四条权威数据线 ：",
                            }
                        ],
                    },
                    "evidence": [
                        {
                            "id": "call-fetch",
                            "kind": "tool",
                            "title": "fetch_url",
                            "tool_name": "fetch_url",
                            "source_ref": "fetch_url",
                            "status": "success",
                            "tool_call_id": "call-fetch",
                            "snippet": fetch_result.summary,
                            "output": fetch_result.output,
                            "summary_payload": fetch_result.summary_payload,
                        }
                    ],
                },
            }
        },
    }

    patched = patch_recovery_evidence_answer_payload(message)

    assert patched["content"] == preview
    assert "10. MiMo/Xiaomi系列或Moonshot Kimi" in patched["content"]
    answer_card = patched["metadata"]["turn_flow"]["answer_card"]
    assert answer_card["summary"] == preview
    assert answer_card["sections"][0]["content"] == preview
    assert patched["metadata"]["recovery_evidence_read_model_repaired"] is True
    assert (
        patched["metadata"]["recovery_evidence_read_model_repair_scope"]
        == LEGACY_RECOVERY_EVIDENCE_REPAIR_SCOPE
    )
