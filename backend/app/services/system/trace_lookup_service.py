"""
Trace lookup service / Trace ID 查询服务。

Aggregates operation logs (DB) and plain log files by trace_id for CLI usage.
按 trace_id 聚合数据库操作日志与文件日志，供 CLI 使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.response import serialize_datetime_for_api
from app.models.system.operation_log import OperationLog


@dataclass(slots=True)
class TraceLookupResult:
    """Trace lookup result container / Trace 查询结果。"""

    trace_id: str
    operation_logs: list[dict[str, Any]]
    log_matches: list[dict[str, Any]]
    primary_error: dict[str, Any] | None
    summary: dict[str, Any]
    redacted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "summary": self.summary,
            "primary_error": self.primary_error,
            "operation_logs": self.operation_logs,
            "log_matches": self.log_matches,
            "redacted": self.redacted,
        }


class TraceLookupService:
    """Lookup trace info from DB + log files / 从 DB + 日志文件定位 trace。"""

    _LOG_PATTERN = "*.log*"
    _TRACE_TEMPLATE = "[trace_id={trace_id}]"
    _SENSITIVE_KEYS = (
        "authorization",
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "apikey",
        "cookie",
        "set-cookie",
        "dsn",
    )
    _SENSITIVE_VALUE_PATTERNS = [
        re.compile(r"(?i)\b(bearer)\s+[a-z0-9\-\._~\+/]+=*"),
        re.compile(
            r"(?i)\b(password|passwd|token|api_key|apikey|secret)\s*[:=]\s*['\"]?[^'\"\s,;]+"
        ),
        re.compile(r"(?i)\b(cookie|set-cookie)\s*[:=]\s*[^;,\n]+"),
        re.compile(r"(?i)\b(postgresql(?:\+asyncpg)?://)[^\s]+"),
    ]

    def __init__(
        self,
        db: AsyncSession | None = None,
        *,
        log_dir: Path | None = None,
    ) -> None:
        self.db = db
        self.log_dir = (log_dir or self._resolve_log_dir()).resolve()

    @staticmethod
    def _resolve_log_dir() -> Path:
        backend_dir = Path(__file__).resolve().parents[3]
        configured = Path(settings.LOG_DIR)
        return configured if configured.is_absolute() else (backend_dir / configured)

    async def lookup(
        self,
        trace_id: str,
        *,
        source: str = "auto",
        context: int = 20,
        max_blocks: int = 10,
        since_hours: int | None = 72,
        redact: bool = True,
    ) -> TraceLookupResult:
        source = source.lower()
        operation_logs: list[dict[str, Any]] = []
        log_matches: list[dict[str, Any]] = []

        need_db = source in {"auto", "db", "all"}
        need_logs = source in {"auto", "logs", "all"}

        if need_db and self.db is not None:
            operation_logs = await self._query_operation_logs(
                trace_id=trace_id, redact=redact
            )

        if need_logs:
            log_matches = self._scan_log_files(
                trace_id=trace_id,
                context=context,
                max_blocks=max_blocks,
                since_hours=since_hours,
                redact=redact,
            )

        primary_error = self._pick_primary_error(log_matches)
        summary = {
            "operation_logs": len(operation_logs),
            "log_matches": len(log_matches),
            "log_files": sorted({item["file"] for item in log_matches}),
            "source": source,
        }

        return TraceLookupResult(
            trace_id=trace_id,
            operation_logs=operation_logs,
            log_matches=log_matches,
            primary_error=primary_error,
            summary=summary,
            redacted=redact,
        )

    async def _query_operation_logs(
        self,
        *,
        trace_id: str,
        redact: bool,
    ) -> list[dict[str, Any]]:
        if self.db is None:
            return []

        stmt = (
            select(OperationLog)
            .where(OperationLog.trace_id == trace_id)
            .order_by(OperationLog.created_at.desc())
            .limit(20)
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [self._serialize_operation_log(item, redact=redact) for item in rows]

    def _serialize_operation_log(
        self, item: OperationLog, *, redact: bool
    ) -> dict[str, Any]:
        payload = {
            "id": item.id,
            "created_at": serialize_datetime_for_api(item.created_at),
            "tenant_id": item.tenant_id,
            "user_type": item.user_type,
            "user_id": item.user_id,
            "username": item.username,
            "module": item.module,
            "action": item.action,
            "method": item.method,
            "path": item.path,
            "status_code": item.status_code,
            "response_code": item.response_code,
            "response_message": item.response_message,
            "duration_ms": item.duration_ms,
            "query_params": item.query_params,
            "request_body": item.request_body,
        }
        return self._redact_value(payload) if redact else payload

    def _scan_log_files(
        self,
        *,
        trace_id: str,
        context: int,
        max_blocks: int,
        since_hours: int | None,
        redact: bool,
    ) -> list[dict[str, Any]]:
        if not self.log_dir.exists() or not self.log_dir.is_dir():
            return []

        marker = self._TRACE_TEMPLATE.format(trace_id=trace_id)
        files = self._list_log_files(since_hours=since_hours)
        matches: list[dict[str, Any]] = []
        for file_path in files:
            if len(matches) >= max_blocks:
                break
            matches.extend(
                self._collect_file_matches(
                    file_path=file_path,
                    marker=marker,
                    context=context,
                    remaining=max_blocks - len(matches),
                    redact=redact,
                )
            )
        return matches

    def _list_log_files(self, *, since_hours: int | None) -> list[Path]:
        files = [f for f in self.log_dir.glob(self._LOG_PATTERN) if f.is_file()]
        # Prefer high-signal categories first for primary error extraction. / 优先高信号分类提取主错误 / prefer high-signal categories
        preferred = ["error.log", "queue.log", "task.log", "app.log", "db.log"]
        files.sort(
            key=lambda f: (
                preferred.index(f.name) if f.name in preferred else len(preferred),
                -f.stat().st_mtime,
            )
        )
        if since_hours is None:
            return files
        cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        return [
            f
            for f in files
            if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) >= cutoff
        ]

    def _collect_file_matches(
        self,
        *,
        file_path: Path,
        marker: str,
        context: int,
        remaining: int,
        redact: bool,
    ) -> list[dict[str, Any]]:
        try:
            with open(file_path, encoding="utf-8", errors="replace") as fp:
                lines = fp.readlines()
        except OSError:
            return []

        rows: list[dict[str, Any]] = []
        for idx, line in enumerate(lines):
            if marker not in line:
                continue
            if len(rows) >= remaining:
                break
            start = max(0, idx - max(0, context))
            end = min(len(lines), idx + max(0, context) + 1)
            block_lines = [ln.rstrip("\r\n") for ln in lines[start:end]]
            if redact:
                block_lines = [self._redact_line(ln) for ln in block_lines]
            rows.append(
                {
                    "file": file_path.name,
                    "line": idx + 1,
                    "start_line": start + 1,
                    "end_line": end,
                    "block": block_lines,
                }
            )
        return rows

    def _pick_primary_error(
        self, matches: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        for item in matches:
            joined = "\n".join(item["block"])
            if "Traceback" in joined:
                return item
            if "ERROR" in joined or "CRITICAL" in joined:
                return item
        return matches[0] if matches else None

    def _redact_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            for k, v in value.items():
                key = str(k).lower()
                if any(token in key for token in self._SENSITIVE_KEYS):
                    out[k] = "***REDACTED***"
                else:
                    out[k] = self._redact_value(v)
            return out
        if isinstance(value, list):
            return [self._redact_value(item) for item in value]
        if isinstance(value, str):
            return self._redact_line(value)
        return value

    def _redact_line(self, line: str) -> str:
        redacted = line
        for pattern in self._SENSITIVE_VALUE_PATTERNS:
            redacted = pattern.sub(
                lambda m: (
                    f"{m.group(1)} ***REDACTED***" if m.lastindex else "***REDACTED***"
                ),
                redacted,
            )
        return redacted


__all__ = ["TraceLookupResult", "TraceLookupService"]
