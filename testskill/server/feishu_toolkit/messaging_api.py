"""消息模块

提供向个人或群聊发送文本、富文本和卡片消息的能力。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from feishu_toolkit.auth import feishu_request

router = APIRouter()


# ── 请求模型 ──────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    receive_id: str = Field(..., description="接收者 ID")
    receive_id_type: str = Field(..., description="ID 类型：open_id/user_id/email/chat_id")
    msg_type: str = Field(..., description="消息类型：text/post/interactive/image/file")
    content: str = Field(..., description="消息内容（JSON 字符串）")


class ReplyMessageRequest(BaseModel):
    message_id: str = Field(..., description="要回复的消息 ID")
    msg_type: str = Field(..., description="消息类型")
    content: str = Field(..., description="消息内容（JSON 字符串）")


# ── 路由 ──────────────────────────────────────────────────

@router.post("/send", summary="发送消息")
def send_message(req: SendMessageRequest) -> dict:
    """向指定用户或群聊发送消息。"""
    data = feishu_request(
        "POST",
        "/open-apis/im/v1/messages",
        params={"receive_id_type": req.receive_id_type},
        json_body={
            "receive_id": req.receive_id,
            "msg_type": req.msg_type,
            "content": req.content,
        },
    )
    return {
        "message_id": data.get("message_id", ""),
        "msg_type": req.msg_type,
    }


@router.post("/reply", summary="回复消息")
def reply_message(req: ReplyMessageRequest) -> dict:
    """回复指定消息。"""
    data = feishu_request(
        "POST",
        f"/open-apis/im/v1/messages/{req.message_id}/reply",
        json_body={
            "msg_type": req.msg_type,
            "content": req.content,
        },
    )
    return {
        "message_id": data.get("message_id", ""),
        "msg_type": req.msg_type,
    }
