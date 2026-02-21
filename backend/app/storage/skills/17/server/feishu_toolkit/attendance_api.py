"""考勤模块

提供打卡结果查询、补卡记录查询和考勤组信息获取能力。
支持传入 open_id，自动转换为 employee_id。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from feishu_toolkit.auth import feishu_request

router = APIRouter()
logger = logging.getLogger("feishu_toolkit.attendance")


def _resolve_employee_ids(user_ids: list[str]) -> list[str]:
    """将 open_id (ou_ 开头) 转换为 employee_id。

    飞书考勤 API 只接受 employee_id/employee_no，
    此函数自动将 open_id 转换为 employee_id。
    """
    open_ids = [uid for uid in user_ids if uid.startswith("ou_")]
    plain_ids = [uid for uid in user_ids if not uid.startswith("ou_")]

    if not open_ids:
        return user_ids

    resolved: list[str] = list(plain_ids)
    for oid in open_ids:
        try:
            data = feishu_request(
                "GET",
                f"/open-apis/contact/v3/users/{oid}",
                params={"user_id_type": "open_id"},
            )
            user = data.get("user", data)
            eid = user.get("user_id", "")
            if eid:
                resolved.append(eid)
                logger.info("Resolved open_id %s → employee_id %s", oid, eid)
            else:
                logger.warning("No employee_id found for open_id %s, using as-is", oid)
                resolved.append(oid)
        except Exception:
            logger.warning("Failed to resolve open_id %s, using as-is", oid)
            resolved.append(oid)
    return resolved


# ── 请求模型 ──────────────────────────────────────────────

class QueryTasksRequest(BaseModel):
    user_ids: list[str] = Field(..., description="员工 ID 列表（支持 open_id 或 employee_id），最多 50 个")
    check_date_from: int = Field(..., description="起始日期，格式 yyyyMMdd")
    check_date_to: int = Field(..., description="结束日期，格式 yyyyMMdd")


class QueryRemedysRequest(BaseModel):
    user_ids: list[str] = Field(..., description="员工 ID 列表（支持 open_id 或 employee_id）")
    check_time_from: str = Field(..., description="起始时间（Unix 秒时间戳）")
    check_time_to: str = Field(..., description="结束时间（Unix 秒时间戳）")
    status: int | None = Field(None, description="状态：0=待审批, 1=未通过, 2=已通过, 3=已取消, 4=已撤回")


# ── 路由 ──────────────────────────────────────────────────

@router.post("/tasks", summary="查询打卡结果")
def query_tasks(req: QueryTasksRequest) -> dict:
    """获取员工在指定日期范围内的打卡结果。支持传入 open_id，自动转换。"""
    resolved_ids = _resolve_employee_ids(req.user_ids)
    data = feishu_request(
        "POST",
        "/open-apis/attendance/v1/user_tasks/query",
        params={"employee_type": "employee_id"},
        json_body={
            "user_ids": resolved_ids,
            "check_date_from": req.check_date_from,
            "check_date_to": req.check_date_to,
        },
    )
    return {"tasks": data.get("user_task_results", [])}


@router.post("/remedys", summary="获取补卡记录")
def query_remedys(req: QueryRemedysRequest) -> dict:
    """获取员工的补卡申请记录。支持传入 open_id，自动转换。"""
    resolved_ids = _resolve_employee_ids(req.user_ids)
    body: dict = {
        "user_ids": resolved_ids,
        "check_time_from": req.check_time_from,
        "check_time_to": req.check_time_to,
    }
    if req.status is not None:
        body["status"] = req.status

    data = feishu_request(
        "POST",
        "/open-apis/attendance/v1/user_task_remedys/query",
        json_body=body,
    )
    return {"remedys": data.get("user_remedys", [])}


@router.get("/group/{group_id}", summary="查询考勤组")
def get_group(group_id: str) -> dict:
    """获取考勤组的详细配置信息。"""
    data = feishu_request(
        "GET",
        f"/open-apis/attendance/v1/groups/{group_id}",
    )
    return data.get("group", data)
