"""
Image cache cleanup task

Cleans up expired image processing cache files from the local filesystem.
Runs as a scheduled Celery task.
"""

import time

from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")

# Default cache TTL: 7 days
DEFAULT_CACHE_TTL_DAYS = 7


@register_task(
    queue="scheduled",
    description="Clean up expired image processing cache files",
    max_retries=1,
)
def cleanup_image_cache(self: BaseTask, ttl_days: int = DEFAULT_CACHE_TTL_DAYS) -> dict:
    """
    Clean up expired image cache files.

    Scans LOCAL_IMAGE_CACHE_ROOT and removes files older than ttl_days.
    Also validates cache paths to prevent traversal attacks.
    """
    from app.storage import LOCAL_IMAGE_CACHE_ROOT

    start = time.time()
    cache_root = LOCAL_IMAGE_CACHE_ROOT

    if not cache_root.exists():
        logger.info("Image cache cleanup: no cache directory, skipping")
        return {"cleaned": 0, "cleaned_bytes": 0, "errors": 0, "duration_ms": 0}

    # Validate cache root is a safe path
    resolved_root = cache_root.resolve()

    cleaned = 0
    cleaned_bytes = 0
    errors = 0
    ttl_seconds = ttl_days * 86400
    now = time.time()

    try:
        for cache_file in cache_root.rglob("*"):
            if not cache_file.is_file():
                continue

            # Path traversal safety: ensure file is under cache root
            try:
                resolved = cache_file.resolve()
                if not str(resolved).startswith(str(resolved_root)):
                    logger.warning(
                        "Image cache cleanup: skipping suspicious path %s",
                        cache_file,
                    )
                    continue
            except (OSError, ValueError):
                continue

            try:
                file_age = now - cache_file.stat().st_mtime
                if file_age > ttl_seconds:
                    file_size = cache_file.stat().st_size
                    cache_file.unlink(missing_ok=True)
                    cleaned += 1
                    cleaned_bytes += file_size
            except Exception as exc:
                logger.error(
                    "Image cache cleanup: failed to remove %s: %s",
                    cache_file, exc,
                )
                errors += 1

        # Remove empty subdirectories
        for subdir in sorted(cache_root.rglob("*"), reverse=True):
            if subdir.is_dir():
                try:
                    if not any(subdir.iterdir()):
                        subdir.rmdir()
                except OSError:
                    pass

    except Exception as exc:
        logger.error("Image cache cleanup: scan failed: %s", exc)
        errors += 1

    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "Image cache cleanup completed: cleaned=%d files (%.1f MB), errors=%d, duration=%dms",
        cleaned, cleaned_bytes / (1024 * 1024), errors, duration_ms,
    )
    return {
        "cleaned": cleaned,
        "cleaned_bytes": cleaned_bytes,
        "errors": errors,
        "duration_ms": duration_ms,
    }
