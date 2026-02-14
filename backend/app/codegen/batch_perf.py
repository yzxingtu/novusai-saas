"""
批量生成性能优化与并发控制

M58-T29: workspace 锁 / 限流 / 缓存 / 可观测性指标

模块职责：
- WorkspaceLock: 按 base_dir 串行化写盘操作
- BatchLimits: 单次生成的上限配置与校验
- RunCache: 同一 run 内的文件读取缓存
- PerfMetrics: 性能指标采集与输出
"""

from __future__ import annotations

import asyncio
import os
import time
import weakref
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# Workspace 写盘锁
# ============================================================


class WorkspaceLock:
    """按 base_dir 串行化写盘操作

    同一 workspace 的写盘必须串行执行，不同 workspace 可并行。
    使用 WeakValueDictionary 自动清理不再引用的锁，避免内存泄漏。
    """

    _locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
        weakref.WeakValueDictionary()
    )
    _lock_guard = asyncio.Lock()  # 保护 _locks 字典本身

    @classmethod
    async def acquire(cls, base_dir: str) -> asyncio.Lock:
        """获取指定 workspace 的锁

        Args:
            base_dir: 项目根目录路径（规范化后作为 key）

        Returns:
            asyncio.Lock（已 acquire）
        """
        key = os.path.normpath(os.path.abspath(base_dir))

        async with cls._lock_guard:
            if key not in cls._locks:
                cls._locks[key] = asyncio.Lock()
            lock = cls._locks[key]

        await lock.acquire()
        return lock

    @classmethod
    async def release(cls, base_dir: str) -> None:
        """释放指定 workspace 的锁"""
        key = os.path.normpath(os.path.abspath(base_dir))

        async with cls._lock_guard:
            lock = cls._locks.get(key)
            if lock and lock.locked():
                lock.release()

    @classmethod
    async def cleanup(cls) -> None:
        """清理所有未锁定的锁（避免内存泄漏）"""
        async with cls._lock_guard:
            to_remove = [
                k for k, v in cls._locks.items()
                if not v.locked()
            ]
            for k in to_remove:
                del cls._locks[k]

    @classmethod
    def active_count(cls) -> int:
        """当前活跃锁数量"""
        return sum(1 for v in cls._locks.values() if v.locked())


# ============================================================
# 批量生成限流
# ============================================================


class BatchLimits(BaseModel):
    """批量生成上限配置"""

    max_entities: int = Field(20, description="单次最大实体数")
    max_files: int = Field(500, description="单次最大文件数")
    max_total_bytes: int = Field(
        10 * 1024 * 1024,  # 10 MB
        description="单次最大总字节数",
    )


# 默认限制
DEFAULT_LIMITS = BatchLimits()


class LimitExceeded(BaseModel):
    """超限错误"""

    limit_type: str = Field(..., description="超限类型")
    current: int = Field(..., description="当前值")
    maximum: int = Field(..., description="最大允许值")
    message: str = Field("", description="人类可读信息")


def check_batch_limits(
    entity_count: int,
    file_count: int = 0,
    total_bytes: int = 0,
    limits: BatchLimits | None = None,
) -> list[LimitExceeded]:
    """检查批量生成是否超限

    Args:
        entity_count: 实体数量
        file_count: 文件数量
        total_bytes: 总字节数
        limits: 限制配置（默认使用 DEFAULT_LIMITS）

    Returns:
        超限错误列表（空 = 通过）
    """
    limits = limits or DEFAULT_LIMITS
    exceeded: list[LimitExceeded] = []

    if entity_count > limits.max_entities:
        exceeded.append(LimitExceeded(
            limit_type="max_entities",
            current=entity_count,
            maximum=limits.max_entities,
            message=(
                f"Entity count {entity_count} exceeds maximum "
                f"{limits.max_entities}"
            ),
        ))

    if file_count > 0 and file_count > limits.max_files:
        exceeded.append(LimitExceeded(
            limit_type="max_files",
            current=file_count,
            maximum=limits.max_files,
            message=(
                f"File count {file_count} exceeds maximum "
                f"{limits.max_files}"
            ),
        ))

    if total_bytes > 0 and total_bytes > limits.max_total_bytes:
        exceeded.append(LimitExceeded(
            limit_type="max_total_bytes",
            current=total_bytes,
            maximum=limits.max_total_bytes,
            message=(
                f"Total size {total_bytes} bytes exceeds maximum "
                f"{limits.max_total_bytes} bytes"
            ),
        ))

    return exceeded


# ============================================================
# Run 内缓存
# ============================================================


class RunCache:
    """同一 run 内的文件读取缓存

    减少重复 I/O：
    - 文件内容缓存（read_file）
    - 文件存在性缓存（exists）
    - 路径规范化缓存（normpath）
    """

    def __init__(self) -> None:
        self._file_cache: dict[str, str] = {}
        self._exists_cache: dict[str, bool] = {}
        self._normpath_cache: dict[str, str] = {}
        self._hit_count: int = 0
        self._miss_count: int = 0

    def read_file(self, path: str) -> str | None:
        """读取文件（带缓存）

        Returns:
            文件内容，文件不存在返回 None
        """
        norm = self.normpath(path)
        if norm in self._file_cache:
            self._hit_count += 1
            return self._file_cache[norm]

        self._miss_count += 1
        try:
            with open(norm, "r", encoding="utf-8") as f:
                content = f.read()
            self._file_cache[norm] = content
            self._exists_cache[norm] = True
            return content
        except (OSError, UnicodeDecodeError):
            self._exists_cache[norm] = False
            return None

    def exists(self, path: str) -> bool:
        """检查文件是否存在（带缓存）"""
        norm = self.normpath(path)
        if norm in self._exists_cache:
            return self._exists_cache[norm]

        result = os.path.exists(norm)
        self._exists_cache[norm] = result
        return result

    def normpath(self, path: str) -> str:
        """路径规范化（带缓存）"""
        if path in self._normpath_cache:
            return self._normpath_cache[path]

        result = os.path.normpath(path)
        self._normpath_cache[path] = result
        return result

    def invalidate(self, path: str) -> None:
        """写入后使缓存失效"""
        norm = self.normpath(path)
        self._file_cache.pop(norm, None)
        self._exists_cache.pop(norm, None)

    def stats(self) -> dict[str, int]:
        """缓存统计"""
        return {
            "cache_hits": self._hit_count,
            "cache_misses": self._miss_count,
            "cached_files": len(self._file_cache),
            "cached_paths": len(self._normpath_cache),
        }

    def clear(self) -> None:
        """清空缓存"""
        self._file_cache.clear()
        self._exists_cache.clear()
        self._normpath_cache.clear()
        self._hit_count = 0
        self._miss_count = 0


# ============================================================
# 性能指标
# ============================================================


class PerfMetrics:
    """批量生成性能指标采集

    通过 context manager 计时各阶段耗时。
    """

    def __init__(self) -> None:
        self._timers: dict[str, float] = {}
        self._starts: dict[str, float] = {}
        self._counters: dict[str, int] = {}
        self._start_time: float = time.perf_counter()

    def start_timer(self, name: str) -> None:
        """开始计时"""
        self._starts[name] = time.perf_counter()

    def stop_timer(self, name: str) -> None:
        """停止计时并记录"""
        if name in self._starts:
            elapsed = time.perf_counter() - self._starts[name]
            self._timers[name] = self._timers.get(name, 0) + elapsed
            del self._starts[name]

    def increment(self, name: str, value: int = 1) -> None:
        """递增计数器"""
        self._counters[name] = self._counters.get(name, 0) + value

    def set_counter(self, name: str, value: int) -> None:
        """设置计数器"""
        self._counters[name] = value

    def to_dict(self) -> dict[str, Any]:
        """输出指标字典"""
        total_ms = int((time.perf_counter() - self._start_time) * 1000)
        timers_ms = {
            f"{k}_ms": int(v * 1000)
            for k, v in self._timers.items()
        }
        return {
            "total_ms": total_ms,
            **timers_ms,
            **self._counters,
        }

    class Timer:
        """Context manager for timing a block"""

        def __init__(self, metrics: PerfMetrics, name: str) -> None:
            self._metrics = metrics
            self._name = name

        def __enter__(self) -> PerfMetrics.Timer:
            self._metrics.start_timer(self._name)
            return self

        def __exit__(self, *args: Any) -> None:
            self._metrics.stop_timer(self._name)

    def timer(self, name: str) -> Timer:
        """获取计时 context manager

        Usage:
            with metrics.timer("render"):
                # ... rendering code
        """
        return self.Timer(self, name)


__all__ = [
    "WorkspaceLock",
    "BatchLimits",
    "DEFAULT_LIMITS",
    "LimitExceeded",
    "check_batch_limits",
    "RunCache",
    "PerfMetrics",
]
