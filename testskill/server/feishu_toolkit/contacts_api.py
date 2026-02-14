"""通讯录模块

提供用户信息查询、部门信息查询和搜索能力。
全部基于 tenant_access_token，Agent 可直接使用。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from feishu_toolkit.auth import feishu_request

router = APIRouter()
logger = logging.getLogger("feishu_toolkit.contacts")


# ── 请求模型 ──────────────────────────────────────────────

class SearchUsersRequest(BaseModel):
    query: str = Field(..., description="搜索关键词（姓名）")
    department_id: str = Field("0", description="从哪个部门开始搜索，默认根部门")
    recursive: bool = Field(True, description="是否递归搜索子部门")


class SearchDepartmentsRequest(BaseModel):
    query: str = Field(..., description="搜索关键词（部门名称）")
    parent_department_id: str = Field("0", description="父部门 ID，默认根部门")


# ── 内部工具 ──────────────────────────────────────────────

def _list_sub_departments(parent_id: str = "0") -> list[dict]:
    """列出指定部门的直属子部门（tenant_access_token）"""
    all_depts: list[dict] = []
    page_token = ""
    while True:
        params: dict = {"parent_department_id": parent_id, "page_size": 50}
        if page_token:
            params["page_token"] = page_token
        data = feishu_request(
            "GET",
            "/open-apis/contact/v3/departments",
            params=params,
        )
        all_depts.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token", "")
    return all_depts


def _list_department_users_internal(department_id: str) -> list[dict]:
    """列出部门直属成员（tenant_access_token）"""
    all_users: list[dict] = []
    page_token = ""
    while True:
        params: dict = {"department_id": department_id, "page_size": 50}
        if page_token:
            params["page_token"] = page_token
        data = feishu_request(
            "GET",
            "/open-apis/contact/v3/users/find_by_department",
            params=params,
        )
        all_users.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token", "")
    return all_users


def _collect_departments_recursive(parent_id: str = "0", max_depth: int = 5) -> list[dict]:
    """递归收集部门树（限制深度防止过深遍历）"""
    if max_depth <= 0:
        return []
    depts = _list_sub_departments(parent_id)
    result = list(depts)
    for dept in depts:
        dept_id = dept.get("open_department_id", "")
        if dept_id:
            result.extend(_collect_departments_recursive(dept_id, max_depth - 1))
    return result


# ── 路由 ──────────────────────────────────────────────────

@router.get("/user/{user_id}", summary="获取用户信息")
def get_user(
    user_id: str,
    user_id_type: str = Query("open_id", description="ID 类型：open_id/user_id/union_id"),
) -> dict:
    """根据用户 ID 获取用户详细信息。"""
    data = feishu_request(
        "GET",
        f"/open-apis/contact/v3/users/{user_id}",
        params={"user_id_type": user_id_type},
    )
    return data.get("user", data)


@router.post("/users/search", summary="搜索用户")
def search_users(req: SearchUsersRequest) -> dict:
    """通过关键词搜索用户（基于部门遍历 + 姓名匹配）。

    使用 tenant_access_token，遍历部门成员并按姓名模糊匹配。
    """
    query_lower = req.query.lower()

    # 收集要搜索的部门 ID
    dept_ids = [req.department_id]
    if req.recursive:
        sub_depts = _collect_departments_recursive(req.department_id)
        dept_ids.extend(d.get("open_department_id", "") for d in sub_depts if d.get("open_department_id"))

    matched: list[dict] = []
    for dept_id in dept_ids:
        try:
            users = _list_department_users_internal(dept_id)
        except Exception:
            logger.debug("Skipping dept %s", dept_id)
            continue
        for user in users:
            name = user.get("name", "")
            en_name = user.get("en_name", "")
            if query_lower in name.lower() or query_lower in en_name.lower():
                matched.append(user)
    return {"items": matched}


@router.get("/department/{department_id}", summary="获取部门信息")
def get_department(department_id: str) -> dict:
    """获取单个部门的详细信息。"""
    data = feishu_request(
        "GET",
        f"/open-apis/contact/v3/departments/{department_id}",
    )
    return data.get("department", data)


@router.post("/departments/search", summary="搜索部门")
def search_departments(req: SearchDepartmentsRequest) -> dict:
    """通过部门名称搜索部门（基于部门树遍历 + 名称匹配）。

    使用 tenant_access_token，递归遍历部门树并按名称模糊匹配。
    """
    query_lower = req.query.lower()
    all_depts = _collect_departments_recursive(req.parent_department_id)
    matched = [
        dept for dept in all_depts
        if query_lower in dept.get("name", "").lower()
    ]
    return {"items": matched}


@router.get("/department/{department_id}/users", summary="获取部门成员")
def list_department_users(
    department_id: str,
    page_size: int = Query(50, description="每页数量"),
    page_token: str | None = Query(None, description="分页标记"),
) -> dict:
    """获取指定部门的直属成员列表。"""
    params: dict = {
        "department_id": department_id,
        "page_size": page_size,
    }
    if page_token:
        params["page_token"] = page_token

    data = feishu_request(
        "GET",
        "/open-apis/contact/v3/users/find_by_department",
        params=params,
    )
    return {
        "items": data.get("items", []),
        "has_more": data.get("has_more", False),
        "page_token": data.get("page_token", ""),
    }
