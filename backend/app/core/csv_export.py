"""Shared CSV export helpers."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from io import StringIO
from typing import Any

from fastapi.responses import StreamingResponse

MAX_EXPORT_ROWS = 10_000


def csv_streaming_response(
    rows: Sequence[dict[str, Any]] | Iterable[dict[str, Any]],
    columns: Sequence[dict[str, str]],
    filename: str,
) -> StreamingResponse:
    """Build a UTF-8 BOM CSV response from simple row/column definitions."""
    headers = [column["header"] for column in columns]
    fields = [column["field"] for column in columns]

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writerow(dict(zip(fields, headers, strict=True)))

    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})

    content = "\ufeff" + buffer.getvalue()
    response_headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
    }
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers=response_headers,
    )


__all__ = ["MAX_EXPORT_ROWS", "csv_streaming_response"]
