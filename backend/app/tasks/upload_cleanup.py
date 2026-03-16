"""
Chunk upload temporary file cleanup task / 分片上传临时文件清理任务

Cleans up chunk upload sessions and temporary files exceeding retention time.
清理超过保留时间的分片上传会话及临时文件
"""

import json
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")

# Default retention time: 24 hours / 默认保留时间：24 小时
DEFAULT_RETENTION_HOURS = 24


@register_task(
    queue="scheduled",
    description="Clean up chunk upload temp files (sessions exceeding retention time) / 清理分片上传临时文件（清理超过保留时间的分片上传会话）",
    max_retries=1,
)
def cleanup_chunk_uploads(self: BaseTask, retention_hours: int = DEFAULT_RETENTION_HOURS) -> dict:
    """
    Clean up expired chunk upload sessions / 清理过期的分片上传会话

    Scans all session directories under tempdir/novusai_uploads/,
    checks if created_at in session.json exceeds retention time,
    and deletes the entire session directory (including chunk files) if expired.
    扫描 tempdir/novusai_uploads/ 下所有会话目录，
    检查 session.json 中的 created_at 是否超过保留时间，
    超过则删除整个会话目录（含分片文件）。
    """
    start = time.time()
    upload_root = Path(tempfile.gettempdir()) / "novusai_uploads"

    if not upload_root.exists():
        logger.info("Upload cleanup: no upload root directory, skipping")
        return {"cleaned": 0, "errors": 0, "duration_ms": 0}

    cleaned = 0
    errors = 0
    now = utc_now()

    # Iterate all tenant/admin subdirectories / 遍历所有企业/admin 子目录
    for tenant_dir in upload_root.iterdir():
        if not tenant_dir.is_dir():
            continue

        for session_dir in tenant_dir.iterdir():
            if not session_dir.is_dir():
                continue

            session_file = session_dir / "session.json"
            if not session_file.exists():
                # Orphan directory without session.json, clean up directly / 无 session.json 的孤立目录，直接清理
                try:
                    shutil.rmtree(session_dir, ignore_errors=True)
                    cleaned += 1
                except Exception as e:
                    logger.error(
                        "Upload cleanup: failed to remove orphan dir {}: {}",
                        session_dir, e,
                    )
                    errors += 1
                continue

            try:
                session = json.loads(session_file.read_text(encoding="utf-8"))
                created_at_str = session.get("created_at", "")
                if not created_at_str:
                    # No timestamp, treat as expired / 无时间戳，视为过期
                    shutil.rmtree(session_dir, ignore_errors=True)
                    cleaned += 1
                    continue

                created_at = datetime.fromisoformat(created_at_str)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                age_hours = (now - created_at).total_seconds() / 3600
                if age_hours > retention_hours:
                    shutil.rmtree(session_dir, ignore_errors=True)
                    cleaned += 1
                    logger.info(
                        "Upload cleanup: removed expired session {} (age: {}h)",
                        session_dir.name, age_hours,
                    )
            except Exception as e:
                logger.error(
                    "Upload cleanup: failed to process {}: {}",
                    session_dir, e,
                )
                errors += 1

        # Clean up empty tenant directories too / 如果企业目录为空，也清理掉
        try:
            if tenant_dir.exists() and not any(tenant_dir.iterdir()):
                tenant_dir.rmdir()
        except OSError:
            pass

    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "Upload cleanup completed: cleaned={}, errors={}, duration={}ms",
        cleaned, errors, duration_ms,
    )
    return {"cleaned": cleaned, "errors": errors, "duration_ms": duration_ms}
