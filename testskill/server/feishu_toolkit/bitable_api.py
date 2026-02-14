"""多维表格模块

提供飞书多维表格（Bitable）的创建、查询、新增和更新记录能力。
支持通过 API 创建新的多维表格和列出已有多维表格，无需手动获取 app_token。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from feishu_toolkit.auth import feishu_request

router = APIRouter()
logger = logging.getLogger("feishu_toolkit.bitable")


# ── 请求模型 ──────────────────────────────────────────────

class CreateBitableRequest(BaseModel):
    name: str = Field(..., description="多维表格名称")
    folder_token: str | None = Field(
        None,
        description="目标文件夹 token，为空时创建在应用根目录",
    )


class SearchRecordsRequest(BaseModel):
    app_token: str = Field(..., description="多维表格 App Token")
    table_id: str = Field(..., description="数据表 ID")
    field_names: list[str] | None = Field(None, description="指定返回的字段名称")
    filter: dict | None = Field(None, description="筛选条件")
    sort: list[dict] | None = Field(None, description="排序条件")
    page_size: int = Field(20, description="每页数量，最大 500")


class CreateRecordRequest(BaseModel):
    app_token: str = Field(..., description="多维表格 App Token")
    table_id: str = Field(..., description="数据表 ID")
    fields: dict[str, Any] = Field(..., description="字段数据")


class UpdateRecordRequest(BaseModel):
    app_token: str = Field(..., description="多维表格 App Token")
    table_id: str = Field(..., description="数据表 ID")
    fields: dict[str, Any] = Field(..., description="要更新的字段数据")


# ── 辅助函数 ──────────────────────────────────────────────

def _get_root_folder_token() -> str:
    """获取应用根目录的 folder_token。"""
    data = feishu_request("GET", "/open-apis/drive/explorer/v2/root_folder/meta")
    return data.get("token", "")


# ── 路由: 多维表格管理 ────────────────────────────────────

@router.post("/apps", summary="创建多维表格")
def create_bitable(req: CreateBitableRequest) -> dict:
    """创建一个新的多维表格。

    如果不提供 folder_token，将创建在应用根目录下。
    返回新多维表格的 app_token 和默认数据表 table_id。
    """
    folder = req.folder_token or _get_root_folder_token()
    body: dict[str, Any] = {"name": req.name, "folder_token": folder}

    data = feishu_request(
        "POST",
        "/open-apis/bitable/v1/apps",
        json_body=body,
    )
    app_info = data.get("app", {})
    return {
        "app_token": app_info.get("app_token", ""),
        "name": app_info.get("name", req.name),
        "url": app_info.get("url", ""),
        "default_table_id": app_info.get("default_table_id", ""),
        "folder_token": folder,
    }


@router.get("/apps", summary="列出多维表格")
def list_bitables(
    folder_token: str | None = Query(
        None,
        description="文件夹 token，为空时列出应用根目录下的多维表格",
    ),
) -> dict:
    """列出指定文件夹下的多维表格。

    通过云空间 Drive API 列出文件并筛选 bitable 类型。
    """
    folder = folder_token or _get_root_folder_token()
    items: list[dict] = []
    page_token: str | None = None

    # 分页获取所有文件
    for _ in range(20):  # 防止无限循环
        params: dict[str, Any] = {
            "folder_token": folder,
            "page_size": 50,
        }
        if page_token:
            params["page_token"] = page_token

        data = feishu_request(
            "GET",
            "/open-apis/drive/v1/files",
            params=params,
        )
        for f in data.get("files", []):
            if f.get("type") == "bitable":
                items.append({
                    "app_token": f.get("token", ""),
                    "name": f.get("name", ""),
                    "url": f.get("url", ""),
                    "created_time": f.get("created_time", ""),
                    "modified_time": f.get("modified_time", ""),
                    "owner_id": f.get("owner_id", ""),
                })

        if not data.get("has_more"):
            break
        page_token = data.get("page_token")

    return {"folder_token": folder, "bitables": items}


@router.get("/fields", summary="列出字段")
def list_fields(
    app_token: str = Query(..., description="多维表格 App Token"),
    table_id: str = Query(..., description="数据表 ID"),
) -> dict:
    """获取数据表的字段（列）定义。

    返回字段名、类型等信息，方便了解表结构后进行数据操作。
    """
    data = feishu_request(
        "GET",
        f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
    )
    items = data.get("items", [])
    return {
        "fields": [
            {
                "field_id": f.get("field_id", ""),
                "field_name": f.get("field_name", ""),
                "type": f.get("type", 0),
                "is_primary": f.get("is_primary", False),
                "property": f.get("property", {}),
            }
            for f in items
        ]
    }


# ── 路由: 数据表与记录 ────────────────────────────────────

@router.get("/tables", summary="列出数据表")
def list_tables(
    app_token: str = Query(..., description="多维表格 App Token"),
) -> dict:
    """获取多维表格中的数据表列表。"""
    data = feishu_request(
        "GET",
        f"/open-apis/bitable/v1/apps/{app_token}/tables",
    )
    return {"tables": data.get("items", [])}


@router.post("/records/search", summary="查询记录")
def search_records(req: SearchRecordsRequest) -> dict:
    """根据条件查询多维表格中的记录。"""
    body: dict[str, Any] = {"page_size": req.page_size}
    if req.field_names:
        body["field_names"] = req.field_names
    if req.filter:
        body["filter"] = req.filter
    if req.sort:
        body["sort"] = req.sort

    data = feishu_request(
        "POST",
        f"/open-apis/bitable/v1/apps/{req.app_token}/tables/{req.table_id}/records/search",
        json_body=body,
    )
    return {
        "total": data.get("total", 0),
        "items": data.get("items", []),
    }


@router.post("/records", summary="新增记录")
def create_record(req: CreateRecordRequest) -> dict:
    """向数据表中新增一条记录。"""
    data = feishu_request(
        "POST",
        f"/open-apis/bitable/v1/apps/{req.app_token}/tables/{req.table_id}/records",
        json_body={"fields": req.fields},
    )
    record = data.get("record", data)
    return {
        "record_id": record.get("record_id", ""),
        "fields": record.get("fields", {}),
    }


@router.put("/records/{record_id}", summary="更新记录")
def update_record(record_id: str, req: UpdateRecordRequest) -> dict:
    """更新数据表中的一条记录。"""
    data = feishu_request(
        "PUT",
        f"/open-apis/bitable/v1/apps/{req.app_token}/tables/{req.table_id}/records/{record_id}",
        json_body={"fields": req.fields},
    )
    record = data.get("record", data)
    return {
        "record_id": record.get("record_id", record_id),
        "fields": record.get("fields", {}),
    }
