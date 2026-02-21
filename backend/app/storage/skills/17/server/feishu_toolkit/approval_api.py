"""审批模块

提供查看审批定义、创建审批实例、查询审批状态和撤回审批的能力。
支持通过环境变量预配置常用审批类型的 approval_code，方便 Agent 自动发起审批。
"""

from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from feishu_toolkit.auth import feishu_request

router = APIRouter()
logger = logging.getLogger("feishu_toolkit.approval")


def _load_approval_code_map() -> dict[str, str]:
    """从环境变量加载审批类型映射。

    格式: FEISHU_APPROVAL_CODES='{"请假":"CODE1","加班":"CODE2","出差":"CODE3"}'
    每个 key 为审批类型名称，value 为对应的 approval_code。
    """
    raw = os.getenv("FEISHU_APPROVAL_CODES", "")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("FEISHU_APPROVAL_CODES 解析失败，请检查 JSON 格式")
        return {}


# ── 请求模型 ──────────────────────────────────────────────

class CreateApprovalRequest(BaseModel):
    approval_code: str = Field(..., description="审批定义 Code")
    open_id: str = Field(..., description="发起人 open_id（ou_ 开头）")
    form: str = Field(..., description="审批表单内容（JSON 字符串）")
    department_id: str | None = Field(None, description="发起人所属部门 ID")


class CancelApprovalRequest(BaseModel):
    approval_code: str = Field(..., description="审批定义 Code")
    instance_code: str = Field(..., description="审批实例 Code")
    user_id: str = Field(..., description="审批提交人 open_id")


class ApproveTaskRequest(BaseModel):
    approval_code: str = Field(..., description="审批定义 Code")
    instance_code: str = Field(..., description="审批实例 Code")
    task_id: str = Field(..., description="任务 ID")
    open_id: str = Field(..., description="操作人 open_id（审批人）")
    comment: str | None = Field(None, description="同意意见")
    form: str | None = Field(None, description="表单补充（可选）")


class RejectTaskRequest(BaseModel):
    approval_code: str = Field(..., description="审批定义 Code")
    instance_code: str = Field(..., description="审批实例 Code")
    task_id: str = Field(..., description="任务 ID")
    open_id: str = Field(..., description="操作人 open_id（审批人）")
    comment: str | None = Field(None, description="拒绝理由")


class TransferTaskRequest(BaseModel):
    approval_code: str = Field(..., description="审批定义 Code")
    instance_code: str = Field(..., description="审批实例 Code")
    task_id: str = Field(..., description="任务 ID")
    open_id: str = Field(..., description="当前审批人 open_id")
    transfer_open_id: str = Field(..., description="转交目标审批人 open_id")
    comment: str | None = Field(None, description="转交说明")


# ── 路由 ──────────────────────────────────────────────────

@router.get("/types", summary="列出可用审批类型")
def list_approval_types(
    user_id: str | None = Query(
        None,
        description="用户 open_id，传入后会从该用户的历史审批中发现审批类型",
    ),
) -> dict:
    """列出可用的审批类型。

    数据来源：
    1. 环境变量 FEISHU_APPROVAL_CODES 中预配置的审批类型
    2. 如果传入 user_id，还会从该用户的历史审批实例中发现审批类型

    飞书不提供"列出所有审批定义"的 API，因此推荐管理员在 .env 中预配置常用审批 code。
    """
    # 1. 从环境变量加载
    configured = _load_approval_code_map()
    types: dict[str, dict] = {
        name: {"approval_code": code, "source": "config"}
        for name, code in configured.items()
    }

    # 2. 从用户历史实例中发现
    if user_id:
        try:
            data = feishu_request(
                "POST",
                "/open-apis/approval/v4/instances/query",
                params={"user_id_type": "open_id"},
                json_body={"user_id": user_id, "page_size": 50},
            )
            for item in data.get("instance_list", []):
                approval = item.get("approval", {})
                name = approval.get("name", "")
                code = approval.get("code", "")
                if name and code and name not in types:
                    types[name] = {"approval_code": code, "source": "discovered"}
        except Exception:
            logger.warning("从用户历史实例发现审批类型失败", exc_info=True)

    return {
        "approval_types": [
            {"name": name, **info} for name, info in types.items()
        ],
        "hint": "如需更多审批类型，请在 .env 中配置 FEISHU_APPROVAL_CODES" if not types else "",
    }


@router.get("/definitions/{approval_code}", summary="查看审批定义")
def get_definition(approval_code: str) -> dict:
    """获取审批定义详情，包括表单控件结构。

    Agent 可通过此接口了解审批表单需要填写哪些字段，然后构建 form 参数。
    """
    data = feishu_request(
        "GET",
        f"/open-apis/approval/v4/approvals/{approval_code}",
    )
    return {
        "approval_code": data.get("approval_code", approval_code),
        "approval_name": data.get("approval_name", ""),
        "form": data.get("form", []),
        "node_list": data.get("node_list", []),
    }


@router.post("/create", summary="创建审批实例")
def create_instance(req: CreateApprovalRequest) -> dict:
    """发起一个新的审批申请。

    注意：创建审批实例 API 使用独立的 open_id / user_id 字段，
    不支持 user_id_type 查询参数。
    """
    body: dict = {
        "approval_code": req.approval_code,
        "open_id": req.open_id,
        "form": req.form,
    }
    if req.department_id:
        body["department_id"] = req.department_id

    data = feishu_request(
        "POST",
        "/open-apis/approval/v4/instances",
        json_body=body,
    )
    return {"instance_code": data.get("instance_code", "")}


@router.get("/list", summary="查询审批实例列表")
def list_instances(
    approval_code: str | None = Query(None, description="审批定义 Code"),
    user_id: str | None = Query(None, description="发起人 open_id"),
    instance_status: str | None = Query(None, description="状态：PENDING/APPROVED/REJECT/RECALL/ALL"),
    start_time: str | None = Query(None, description="起始时间（Unix 毫秒时间戳）"),
    end_time: str | None = Query(None, description="结束时间（Unix 毫秒时间戳）"),
    page_size: int = Query(10, description="每页数量"),
) -> dict:
    """根据条件查询审批实例。"""
    body: dict = {"page_size": page_size}
    if approval_code:
        body["approval_code"] = approval_code
    if user_id:
        body["user_id"] = user_id
    if instance_status:
        body["instance_status"] = instance_status
    if start_time:
        body["start_time"] = start_time
    if end_time:
        body["end_time"] = end_time

    data = feishu_request(
        "POST",
        "/open-apis/approval/v4/instances/query",
        params={"user_id_type": "open_id"},
        json_body=body,
    )
    return {
        "count": data.get("count", 0),
        "instances": data.get("instance_list", []),
    }


@router.get("/{instance_code}", summary="获取审批详情")
def get_instance(instance_code: str) -> dict:
    """获取单个审批实例的详细信息。"""
    return feishu_request(
        "GET",
        f"/open-apis/approval/v4/instances/{instance_code}",
    )


# ── 审批人任务操作 ──────────────────────────────────────────

@router.get("/tasks", summary="查询用户待办/已办任务")
def search_tasks(
    user_id: str = Query(..., description="审批人 open_id"),
    approval_code: str | None = Query(None, description="审批定义 Code"),
    instance_code: str | None = Query(None, description="审批实例 Code"),
    task_status: str | None = Query("PENDING", description="任务状态：PENDING/APPROVED/REJECT/DELEGATE/ALL"),
    page_size: int = Query(10, description="每页数量"),
    page_token: str | None = Query(None, description="翻页令牌"),
) -> dict:
    """查询指定用户的审批任务。

    底层调用 Feishu: POST /open-apis/approval/v4/tasks/search
    """
    params: dict = {"user_id_type": "open_id", "page_size": page_size}
    if page_token:
        params["page_token"] = page_token

    body: dict = {"user_id": user_id}
    if approval_code:
        body["approval_code"] = approval_code
    if instance_code:
        body["instance_code"] = instance_code
    if task_status:
        body["task_status"] = task_status

    data = feishu_request(
        "POST",
        "/open-apis/approval/v4/tasks/search",
        params=params,
        json_body=body,
    )
    return {
        "has_more": data.get("has_more", False),
        "page_token": data.get("page_token", ""),
        "tasks": data.get("task_list", data.get("data", [])),
    }


@router.post("/tasks/approve", summary="同意审批任务")
def approve_task(req: ApproveTaskRequest) -> dict:
    payload = {
        "approval_code": req.approval_code,
        "instance_code": req.instance_code,
        "task_id": req.task_id,
        "user_id": req.open_id,  # 结合 user_id_type=open_id
    }
    if req.comment:
        payload["comment"] = req.comment
    if req.form:
        payload["form"] = req.form

    feishu_request(
        "POST",
        "/open-apis/approval/v4/tasks/approve",
        params={"user_id_type": "open_id"},
        json_body=payload,
    )
    return {"success": True, "task_id": req.task_id, "instance_code": req.instance_code}


@router.post("/tasks/reject", summary="拒绝审批任务")
def reject_task(req: RejectTaskRequest) -> dict:
    payload = {
        "approval_code": req.approval_code,
        "instance_code": req.instance_code,
        "task_id": req.task_id,
        "user_id": req.open_id,  # 结合 user_id_type=open_id
    }
    if req.comment:
        payload["comment"] = req.comment

    feishu_request(
        "POST",
        "/open-apis/approval/v4/tasks/reject",
        params={"user_id_type": "open_id"},
        json_body=payload,
    )
    return {"success": True, "task_id": req.task_id, "instance_code": req.instance_code}


@router.post("/tasks/transfer", summary="转交审批任务")
def transfer_task(req: TransferTaskRequest) -> dict:
    payload = {
        "approval_code": req.approval_code,
        "instance_code": req.instance_code,
        "task_id": req.task_id,
        "user_id": req.open_id,
        "transfer_user_id": req.transfer_open_id,
    }
    if req.comment:
        payload["comment"] = req.comment

    feishu_request(
        "POST",
        "/open-apis/approval/v4/tasks/transfer",
        params={"user_id_type": "open_id"},
        json_body=payload,
    )
    return {"success": True, "task_id": req.task_id, "instance_code": req.instance_code}


@router.post("/cancel", summary="撤回审批")
def cancel_instance(req: CancelApprovalRequest) -> dict:
    """撤回审批中或已通过的审批实例。"""
    feishu_request(
        "POST",
        "/open-apis/approval/v4/instances/cancel",
        params={"user_id_type": "open_id"},
        json_body={
            "approval_code": req.approval_code,
            "instance_code": req.instance_code,
            "user_id": req.user_id,
        },
    )
    return {"success": True, "instance_code": req.instance_code}
