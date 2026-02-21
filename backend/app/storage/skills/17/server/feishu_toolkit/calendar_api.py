"""日历与会议室模块

提供日程创建、忙闲查询、会议室搜索和预约等功能。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from feishu_toolkit.auth import feishu_request


def _to_unix(time_str: str) -> str:
    """将 RFC3339 或 Unix 时间戳字符串统一转为 Unix 秒字符串"""
    # 如果已经是纯数字，直接返回
    if time_str.isdigit():
        return time_str
    try:
        dt = datetime.fromisoformat(time_str)
        return str(int(dt.timestamp()))
    except ValueError:
        return time_str

router = APIRouter()

_primary_calendar_id: str = ""


def _get_primary_calendar() -> str:
    """获取机器人的主日历 ID（自动缓存）"""
    global _primary_calendar_id
    if _primary_calendar_id:
        return _primary_calendar_id

    data = feishu_request("GET", "/open-apis/calendar/v4/calendars")
    for cal in data.get("calendar_list", []):
        if cal.get("role") == "owner":
            _primary_calendar_id = cal["calendar_id"]
            return _primary_calendar_id

    # fallback: 取第一个日历
    calendars = data.get("calendar_list", [])
    if calendars:
        _primary_calendar_id = calendars[0]["calendar_id"]
        return _primary_calendar_id

    raise Exception("No calendar found for this app")


# ── 请求/响应模型 ─────────────────────────────────────────

class CreateEventRequest(BaseModel):
    summary: str = Field(..., description="日程标题")
    start_time: str = Field(..., description="开始时间，RFC3339 格式")
    end_time: str = Field(..., description="结束时间，RFC3339 格式")
    description: str | None = Field(None, description="日程描述")
    attendee_user_ids: list[str] | None = Field(None, description="参与人 open_id 列表")
    room_id: str | None = Field(None, description="会议室 ID")
    calendar_id: str | None = Field(None, description="日历 ID，默认主日历")


class UpdateEventRequest(BaseModel):
    summary: str | None = Field(None, description="日程标题")
    start_time: str | None = Field(None, description="开始时间，RFC3339 格式")
    end_time: str | None = Field(None, description="结束时间，RFC3339 格式")
    description: str | None = Field(None, description="日程描述")
    calendar_id: str | None = Field(None, description="日历 ID，默认主日历")


class FreebusyRequest(BaseModel):
    time_min: str = Field(..., description="查询起始时间，RFC3339 格式")
    time_max: str = Field(..., description="查询结束时间，RFC3339 格式")
    user_id: str | None = Field(None, description="用户 open_id")
    room_id: str | None = Field(None, description="会议室 ID")


class AttendeeItem(BaseModel):
    type: str = Field(..., description="参与人类型：user/chat/resource")
    user_id: str | None = Field(None, description="用户 open_id")
    chat_id: str | None = Field(None, description="群组 ID")
    room_id: str | None = Field(None, description="会议室 ID")


class AddAttendeesRequest(BaseModel):
    attendees: list[AttendeeItem]
    need_notification: bool = True


# ── 路由 ──────────────────────────────────────────────────

@router.post("/events", summary="创建日程")
def create_event(req: CreateEventRequest) -> dict:
    """创建日程，可同时添加参与人和会议室。"""
    cal_id = req.calendar_id or _get_primary_calendar()

    event_body: dict[str, Any] = {
        "summary": req.summary,
        "start_time": {"timestamp": _to_unix(req.start_time)},
        "end_time": {"timestamp": _to_unix(req.end_time)},
    }
    if req.description:
        event_body["description"] = req.description

    data = feishu_request(
        "POST",
        f"/open-apis/calendar/v4/calendars/{cal_id}/events",
        json_body=event_body,
    )

    event = data.get("event", data)
    event_id = event.get("event_id", "")

    # 添加参与人和会议室
    attendees: list[dict[str, Any]] = []
    for uid in req.attendee_user_ids or []:
        attendees.append({"type": "user", "user_id": uid})
    if req.room_id:
        attendees.append({"type": "resource", "room_id": req.room_id})

    if attendees:
        feishu_request(
            "POST",
            f"/open-apis/calendar/v4/calendars/{cal_id}/events/{event_id}/attendees",
            json_body={"attendees": attendees},
        )

    return {
        "event_id": event_id,
        "summary": req.summary,
        "start_time": req.start_time,
        "end_time": req.end_time,
    }


@router.get("/events", summary="获取日程列表")
def list_events(
    start_time: str = Query(..., description="起始时间，RFC3339 格式"),
    end_time: str = Query(..., description="结束时间，RFC3339 格式"),
    calendar_id: str | None = Query(None, description="日历 ID"),
    page_size: int = Query(50, description="每页数量"),
) -> dict:
    """获取指定时间范围内的日程。"""
    cal_id = calendar_id or _get_primary_calendar()
    data = feishu_request(
        "GET",
        f"/open-apis/calendar/v4/calendars/{cal_id}/events",
        params={
            "start_time": _to_unix(start_time),
            "end_time": _to_unix(end_time),
            "page_size": page_size,
        },
    )
    return {"events": data.get("items", [])}


@router.post("/freebusy", summary="查询忙闲状态")
def query_freebusy(req: FreebusyRequest) -> dict:
    """查询用户或会议室在指定时间段内的忙闲情况。"""
    body: dict[str, Any] = {
        "time_min": req.time_min,
        "time_max": req.time_max,
    }
    if req.user_id:
        body["user_id"] = req.user_id
    if req.room_id:
        body["room_id"] = req.room_id

    data = feishu_request(
        "POST",
        "/open-apis/calendar/v4/freebusy/list",
        json_body=body,
    )
    return {"busy_times": data.get("freebusy_list", [])}


@router.get("/rooms", summary="查询会议室列表")
def list_rooms(
    room_level_id: str | None = Query(None, description="层级 ID，为空时返回租户所有会议室"),
    page_size: int = Query(20, description="每页数量"),
    page_token: str | None = Query(None, description="分页标记"),
) -> dict:
    """查询某个会议室层级下的会议室列表。"""
    params: dict[str, Any] = {"page_size": page_size}
    if room_level_id:
        params["room_level_id"] = room_level_id
    if page_token:
        params["page_token"] = page_token

    data = feishu_request(
        "GET",
        "/open-apis/vc/v1/rooms",
        params=params,
    )
    return {
        "rooms": data.get("rooms", []),
        "has_more": data.get("has_more", False),
        "page_token": data.get("page_token", ""),
    }


@router.post("/rooms/search", summary="搜索会议室")
def search_rooms(req: dict) -> dict:
    """通过关键词搜索会议室。"""
    body: dict[str, Any] = {}
    if req.get("keyword"):
        body["keyword"] = req["keyword"]
    if req.get("room_level_id"):
        body["room_level_id"] = req["room_level_id"]
    if req.get("page_size"):
        body["page_size"] = req["page_size"]

    data = feishu_request(
        "POST",
        "/open-apis/vc/v1/rooms/search",
        json_body=body,
    )
    return {
        "rooms": data.get("rooms", []),
        "has_more": data.get("has_more", False),
    }


@router.patch("/events/{event_id}", summary="更新日程")
def update_event(event_id: str, req: UpdateEventRequest) -> dict:
    """更新日程的标题/时间/描述等字段。"""
    cal_id = req.calendar_id or _get_primary_calendar()
    body: dict[str, Any] = {}
    if req.summary is not None:
        body["summary"] = req.summary
    if req.start_time is not None:
        body["start_time"] = {"timestamp": _to_unix(req.start_time)}
    if req.end_time is not None:
        body["end_time"] = {"timestamp": _to_unix(req.end_time)}
    if req.description is not None:
        body["description"] = req.description

    data = feishu_request(
        "PATCH",
        f"/open-apis/calendar/v4/calendars/{cal_id}/events/{event_id}",
        json_body=body,
    )
    event = data.get("event", data)
    return {
        "event_id": event.get("event_id", event_id),
        "summary": event.get("summary", req.summary),
    }


@router.get("/events/{event_id}", summary="获取日程详情")
def get_event(event_id: str, calendar_id: str | None = Query(None, description="日历 ID，默认主日历")) -> dict:
    """获取单个日程的详细信息。"""
    cal_id = calendar_id or _get_primary_calendar()
    data = feishu_request(
        "GET",
        f"/open-apis/calendar/v4/calendars/{cal_id}/events/{event_id}",
    )
    return data.get("event", data)


@router.post("/events/{event_id}/attendees", summary="添加日程参与人")
def add_attendees(event_id: str, req: AddAttendeesRequest) -> dict:
    """为已有日程添加参与人或预约会议室。"""
    cal_id = _get_primary_calendar()
    attendees = []
    for att in req.attendees:
        item: dict[str, Any] = {"type": att.type}
        if att.user_id:
            item["user_id"] = att.user_id
        if att.chat_id:
            item["chat_id"] = att.chat_id
        if att.room_id:
            item["room_id"] = att.room_id
        attendees.append(item)

    data = feishu_request(
        "POST",
        f"/open-apis/calendar/v4/calendars/{cal_id}/events/{event_id}/attendees",
        json_body={
            "attendees": attendees,
            "need_notification": req.need_notification,
        },
    )
    return {"attendees": data.get("attendees", [])}


@router.delete("/events/{event_id}", summary="删除日程")
def delete_event(event_id: str, calendar_id: str | None = Query(None, description="日历 ID，默认主日历")) -> dict:
    """删除指定日历中的一个事件。"""
    cal_id = calendar_id or _get_primary_calendar()
    feishu_request(
        "DELETE",
        f"/open-apis/calendar/v4/calendars/{cal_id}/events/{event_id}",
    )
    return {"success": True, "event_id": event_id}
