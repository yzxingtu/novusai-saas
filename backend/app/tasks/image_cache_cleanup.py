"""
Image cache cleanup task / 图片缓存清理任务

Cleans up expired image processing cache files from the local filesystem.
Runs as a scheduled Celery task.
清理本地文件系统中过期的图片处理缓存文件。
作为 Celery 定时任务运行。
"""

import time

from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")

# Default cache TTL: 7 days / 默认缓存 TTL：7 天
DEFAULT_CACHE_TTL_DAYS = 7


@register_task(
    queue="scheduled",
    description="Clean up expired image processing cache files / 清理过期图片处理缓存文件",
    max_retries=1,
)
def cleanup_image_cache(self: BaseTask, ttl_days: int = DEFAULT_CACHE_TTL_DAYS) -> dict:
    """
    清理过期的图片缓存文件 / Clean up expired image cache files.

    Scans LOCAL_IMAGE_CACHE_ROOT and removes files older than ttl_days.
    Also validates cache paths to prevent traversal attacks.
    扫描 LOCAL_IMAGE_CACHE_ROOT 并删除超过 ttl_days 的文件。
    同时校验缓存路径以防止路径遍历攻击。
    """
    from app.storage import LOCAL_IMAGE_CACHE_ROOT

    start = time.time()
    cache_root = LOCAL_IMAGE_CACHE_ROOT

    if not cache_root.exists():
        logger.info("Image cache cleanup: no cache directory, skipping")
        return {"cleaned": 0, "cleaned_bytes": 0, "errors": 0, "duration_ms": 0}

    # Validate cache root is a safe path / 校验缓存根路径是否安全
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

            # Path traversal safety: ensure file is under cache root / 路径遍历安全检查：确保文件在缓存根目录下
            try:
                resolved = cache_file.resolve()
                if not str(resolved).startswith(str(resolved_root)):
                    logger.warning(
                        "Image cache cleanup: skipping suspicious path {}",
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
                    "Image cache cleanup: failed to remove {}: {}",
                    cache_file,
                    exc,
                )
                errors += 1

        # Remove empty subdirectories / 移除空子目录
        for subdir in sorted(cache_root.rglob("*"), reverse=True):
            if subdir.is_dir():
                try:
                    if not any(subdir.iterdir()):
                        subdir.rmdir()
                except OSError:
                    pass

    except Exception as exc:
        logger.error("Image cache cleanup: scan failed: {}", exc)
        errors += 1

    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        "Image cache cleanup completed: cleaned={} files ({} MB), errors={}, duration={}ms",
        cleaned,
        cleaned_bytes / (1024 * 1024),
        errors,
        duration_ms,
    )
    return {
        "cleaned": cleaned,
        "cleaned_bytes": cleaned_bytes,
        "errors": errors,
        "duration_ms": duration_ms,
    }
