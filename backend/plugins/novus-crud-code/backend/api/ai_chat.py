"""DataForge Studio — AI 数据对话 handler

通过 ctx.call_ai_feature() 调用平台 Agent，传入项目上下文。
"""
from __future__ import annotations


async def chat(request, db, ctx):
    """POST /projects/{project_id}/ai/chat"""
    try:
        project_id = int(request.path_params["project_id"])
    except (KeyError, ValueError, TypeError):
        return {"error": "invalid project_id", "code": 4001, "status_code": 422}

    body = await request.json()
    message = body.get("message", "").strip()
    feature_code = body.get("feature_code", "data_query")
    conversation_id = body.get("conversation_id")

    if not message:
        return {"error": "message is required", "code": 4001, "status_code": 422}

    valid_features = {"data_query", "data_write", "data_analytics"}
    if feature_code not in valid_features:
        feature_code = "data_query"

    system_context = (
        f"You are a data assistant for DataForge Studio project (id={project_id}). "
        "Use the available tools to query, write, or analyze data records as requested."
    )

    messages = [
        {"role": "system", "content": system_context},
        {"role": "user", "content": message},
    ]

    try:
        # call_ai_feature(feature_code, messages) -> str
        reply: str = await ctx.call_ai_feature(feature_code, messages)
        return {"reply": reply, "conversation_id": conversation_id,
                "feature_code": feature_code}
    except Exception as exc:
        return {"error": str(exc), "code": 5000, "status_code": 500}
