"""
Test type: behavioral
Regression for: BUG-2026-05-04-2281
Original symptom: conversation 2281 completed fetch_url recovery with only a
generic "Fetched https://..." assistant answer while the successful fetched body
contained the requested LMArena/Qwen ranking facts.
Scope: recovery evidence rendering from successful fetch_url body text.
Mock strategy: no LLM/provider/tool executor mocks; inputs are recorded-shaped
ToolResult evidence from conversation 2281.
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


def _conversation_2281_fetch_result() -> ToolResult:
    output = (
        "Content from https://mp.weixin.qq.com/s/example-2281:\n"
        "Redirected from: http://www.baidu.com/link?url=example-2281\n\n"
        "全球知名的大模型盲测榜单LMArena更新了新一期排名，"
        "阿里巴巴千问最新旗舰模型预览版Qwen3.5-Max-Preview首度亮相，"
        "斩获1464分，超过了GPT5.4、Grok4.1等海外模型，"
        "以及豆包2.0、GLM5、Kimi2.5等全部国产模型。\n\n"
        "此外，LMArena基于各公司最强模型对全球大模型机构进行排名，"
        "5家中国公司闯进前十，阿里位列全球前五、中国第一，"
        "字节、智谱、月之暗面、百度等也闯入全球前十。\n"
    )
    return ToolResult(
        tool_call_id="call-fetch-2281",
        name="fetch_url",
        success=True,
        output=output,
        summary="Fetched https://mp.weixin.qq.com/s/example-2281",
        summary_payload={
            "fetch_url": True,
            "ok": True,
            "requested_url": "http://www.baidu.com/link?url=example-2281",
            "final_url": "https://mp.weixin.qq.com/s/example-2281",
            "title": None,
            "description": None,
            "summary": "Fetched https://mp.weixin.qq.com/s/example-2281",
        },
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


def test_bug_2026_05_04_2281_uses_body_not_generic_fetched_url_summary() -> None:
    output = _build_output(_conversation_2281_fetch_result())

    assert "Qwen3.5-Max-Preview首度亮相" in output
    assert "斩获1464分" in output
    assert "阿里位列全球前五、中国第一" in output
    assert "Fetched https://mp.weixin.qq.com/s/example-2281" not in output


def test_bug_2026_05_04_2281_read_model_repairs_historical_fetched_url_answer() -> None:
    fetch_result = _conversation_2281_fetch_result()
    preview = _build_output(fetch_result)
    message = {
        "conversation_id": 2281,
        "role": "assistant",
        "created_at": "2026-05-04T08:06:45.379940+00:00",
        "content": "Fetched https://mp.weixin.qq.com/s/example-2281",
        "metadata": {
            "turn_record": {
                "final_output_source": "recovery_evidence",
                "turn_flow": {
                    "answer_card": {
                        "summary": "Fetched https://mp.weixin.qq.com/s/example-2281",
                        "sections": [
                            {
                                "title": "Answer",
                                "content": "Fetched https://mp.weixin.qq.com/s/example-2281",
                            }
                        ],
                    },
                    "evidence": [
                        {
                            "id": "call-fetch-2281",
                            "kind": "tool",
                            "title": "fetch_url",
                            "tool_name": "fetch_url",
                            "source_ref": "fetch_url",
                            "status": "success",
                            "tool_call_id": "call-fetch-2281",
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
    assert "Qwen3.5-Max-Preview首度亮相" in patched["content"]
    answer_card = patched["metadata"]["turn_flow"]["answer_card"]
    assert answer_card["summary"] == preview
    assert answer_card["sections"][0]["content"] == preview
    assert patched["metadata"]["recovery_evidence_read_model_repaired"] is True
    assert (
        patched["metadata"]["recovery_evidence_read_model_repair_scope"]
        == LEGACY_RECOVERY_EVIDENCE_REPAIR_SCOPE
    )


def test_bug_2026_05_04_2281_read_model_does_not_repair_new_live_payloads() -> None:
    fetch_result = _conversation_2281_fetch_result()
    message = {
        "conversation_id": 3001,
        "role": "assistant",
        "created_at": "2026-05-04T09:00:01+00:00",
        "content": "Fetched https://mp.weixin.qq.com/s/example-2281",
        "metadata": {
            "turn_record": {
                "final_output_source": "recovery_evidence",
                "turn_flow": {
                    "answer_card": {
                        "summary": "Fetched https://mp.weixin.qq.com/s/example-2281",
                        "sections": [
                            {
                                "title": "Answer",
                                "content": "Fetched https://mp.weixin.qq.com/s/example-2281",
                            }
                        ],
                    },
                    "evidence": [
                        {
                            "id": "call-fetch-2281",
                            "kind": "tool",
                            "title": "fetch_url",
                            "tool_name": "fetch_url",
                            "source_ref": "fetch_url",
                            "status": "success",
                            "tool_call_id": "call-fetch-2281",
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

    assert patched is message
    assert patched["content"] == "Fetched https://mp.weixin.qq.com/s/example-2281"
    assert "recovery_evidence_read_model_repaired" not in patched["metadata"]
