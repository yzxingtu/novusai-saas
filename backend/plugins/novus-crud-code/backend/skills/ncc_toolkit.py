"""
DataForge Studio AI Toolkit v1.0.0
title: DataForge Studio 数据操作工具集
description: 提供数据查询、写入（需确认）和统计分析三个 AI 可调用工具
version: 1.0.0
author: NovusAI
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from pydantic import BaseModel, Field


class Valves(BaseModel):
    """DataForge Studio API 连接配置"""
    api_base_url: str = Field(
        default="http://localhost:8000",
        description="DataForge Studio API 地址（含协议和端口）",
    )
    admin_token: str = Field(
        default="",
        description="管理员 Bearer Token（在管理端 → 个人设置 → API Key 中获取）",
    )


class Tools:
    """DataForge Studio 数据操作工具集"""

    valves: Valves

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.valves.admin_token}",
        }

    def _base(self) -> str:
        return self.valves.api_base_url.rstrip("/") + "/api/v1/admin/plugins/novus-crud-code"

    def _get(self, path: str) -> dict[str, Any]:
        url = self._base() + path
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = self._base() + path
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def _put(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        url = self._base() + path
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=self._headers(), method="PUT")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def _delete(self, path: str) -> dict[str, Any]:
        url = self._base() + path
        req = urllib.request.Request(url, headers=self._headers(), method="DELETE")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())

    def _find_schema(self, project_id: int, table_name: str) -> dict[str, Any] | None:
        result = self._get(f"/projects/{project_id}/schemas?page[size]=100")
        items = result.get("items", [])
        return next((s for s in items if s["name"] == table_name), None)

    def query_records(
        self,
        project_id: int,
        table_name: str,
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """
        Query data records from a DataForge Studio table.

        :param project_id: The integer ID of the project containing the table
        :param table_name: The snake_case name of the table to query
        :param page: Page number (1-based)
        :param page_size: Number of records per page (max 100)
        """
        try:
            schema = self._find_schema(project_id, table_name)
            if schema is None:
                return json.dumps({"error": f"Table '{table_name}' not found in project {project_id}"})
            sid = schema["id"]
            path = f"/projects/{project_id}/schemas/{sid}/records?page[number]={page}&page[size]={min(page_size, 100)}"
            result = self._get(path)
            return json.dumps({
                "table": table_name,
                "fields": schema.get("schema_config", {}).get("fields", []),
                "items": result.get("items", []),
                "total": result.get("total", 0),
                "page": page,
                "page_size": page_size,
            }, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def write_record(
        self,
        project_id: int,
        table_name: str,
        operation: str,
        data: str,
        record_id: int = 0,
    ) -> str:
        """
        Create, update or delete a record in a DataForge Studio table.
        WARNING: This tool modifies data and requires user confirmation before execution.

        :param project_id: The integer ID of the project
        :param table_name: The snake_case name of the table
        :param operation: The operation to perform: "create", "update", or "delete"
        :param data: JSON string of field values (required for create/update, ignored for delete)
        :param record_id: Record ID (required for update/delete, ignored for create)
        """
        try:
            schema = self._find_schema(project_id, table_name)
            if schema is None:
                return json.dumps({"error": f"Table '{table_name}' not found"})
            sid = schema["id"]

            if operation == "create":
                try:
                    record_data = json.loads(data) if isinstance(data, str) else data
                except json.JSONDecodeError:
                    return json.dumps({"error": "Invalid JSON in data parameter"})
                result = self._post(f"/projects/{project_id}/schemas/{sid}/records",
                                    {"data": record_data})
                return json.dumps({"success": True, "operation": "create", "record": result},
                                  ensure_ascii=False, default=str)

            elif operation == "update":
                if not record_id:
                    return json.dumps({"error": "record_id is required for update"})
                try:
                    record_data = json.loads(data) if isinstance(data, str) else data
                except json.JSONDecodeError:
                    return json.dumps({"error": "Invalid JSON in data parameter"})
                result = self._put(f"/projects/{project_id}/schemas/{sid}/records/{record_id}",
                                   {"data": record_data})
                return json.dumps({"success": True, "operation": "update", "record": result},
                                  ensure_ascii=False, default=str)

            elif operation == "delete":
                if not record_id:
                    return json.dumps({"error": "record_id is required for delete"})
                self._delete(f"/projects/{project_id}/schemas/{sid}/records/{record_id}")
                return json.dumps({"success": True, "operation": "delete", "record_id": record_id})

            else:
                return json.dumps({"error": f"Unknown operation: {operation}. Use create/update/delete"})
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    def analyze_data(
        self,
        project_id: int,
        table_name: str,
        metric: str = "count",
        field_name: str = "",
    ) -> str:
        """
        Analyze data in a DataForge Studio table with statistical metrics.

        :param project_id: The integer ID of the project
        :param table_name: The snake_case name of the table to analyze
        :param metric: Analysis metric: "count", "distribution", "summary", "trend"
        :param field_name: Target field name for distribution/trend analysis (optional)
        """
        try:
            schema = self._find_schema(project_id, table_name)
            if schema is None:
                return json.dumps({"error": f"Table '{table_name}' not found"})
            sid = schema["id"]
            fields_meta = schema.get("schema_config", {}).get("fields", [])

            all_records: list[dict] = []
            page = 1
            while True:
                resp = self._get(
                    f"/projects/{project_id}/schemas/{sid}/records?page[number]={page}&page[size]=200"
                )
                batch = resp.get("items", [])
                all_records.extend(batch)
                if len(batch) < 200:
                    break
                page += 1
                if page > 50:
                    break

            total = len(all_records)

            if metric == "count":
                return json.dumps({
                    "table": table_name, "metric": "count",
                    "total_records": total,
                    "fields": [f["name"] for f in fields_meta],
                })

            elif metric == "summary":
                summary = {"table": table_name, "metric": "summary", "total_records": total,
                           "fields": {}}
                for f in fields_meta:
                    fname = f["name"]
                    vals = [r["data"].get(fname) for r in all_records if r.get("data")]
                    non_null = [v for v in vals if v is not None]
                    summary["fields"][fname] = {
                        "type": f.get("type", "string"),
                        "non_null_count": len(non_null),
                        "null_count": total - len(non_null),
                    }
                    if f.get("type") in ("integer", "number") and non_null:
                        nums = [float(v) for v in non_null if isinstance(v, (int, float))]
                        if nums:
                            summary["fields"][fname].update({
                                "min": min(nums), "max": max(nums),
                                "avg": round(sum(nums) / len(nums), 4),
                            })
                return json.dumps(summary, ensure_ascii=False, default=str)

            elif metric == "distribution":
                target = field_name or (fields_meta[0]["name"] if fields_meta else "")
                if not target:
                    return json.dumps({"error": "field_name required for distribution"})
                counts: dict[str, int] = {}
                for r in all_records:
                    val = str(r.get("data", {}).get(target, "null"))
                    counts[val] = counts.get(val, 0) + 1
                sorted_counts = sorted(counts.items(), key=lambda x: -x[1])[:20]
                return json.dumps({
                    "table": table_name, "metric": "distribution",
                    "field": target, "total_records": total,
                    "distribution": [{"value": v, "count": c} for v, c in sorted_counts],
                }, ensure_ascii=False)

            else:
                return json.dumps({"error": f"Unknown metric: {metric}. Use count/summary/distribution/trend"})
        except Exception as exc:
            return json.dumps({"error": str(exc)})
