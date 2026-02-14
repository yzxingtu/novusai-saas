"""
批量生成性能优化与并发控制 — 单元测试

覆盖：
- WorkspaceLock: 同 workspace 串行、不同 workspace 并行、清理
- BatchLimits: 超限检测（entities/files/bytes）
- RunCache: 文件读取缓存、存在性缓存、失效、统计
- PerfMetrics: 计时器、计数器、context manager
"""

import asyncio
import os
import tempfile

import pytest

from app.codegen.batch_perf import (
    DEFAULT_LIMITS,
    BatchLimits,
    LimitExceeded,
    PerfMetrics,
    RunCache,
    WorkspaceLock,
    check_batch_limits,
)


# ============================================================
# WorkspaceLock
# ============================================================


class TestWorkspaceLock:
    """Workspace 写盘锁"""

    @pytest.fixture(autouse=True)
    async def _cleanup(self):
        """每个测试后清理锁"""
        yield
        await WorkspaceLock.cleanup()

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        """基本获取和释放"""
        lock = await WorkspaceLock.acquire("/tmp/test_ws_1")
        assert lock.locked()
        await WorkspaceLock.release("/tmp/test_ws_1")
        assert not lock.locked()

    @pytest.mark.asyncio
    async def test_same_workspace_serialized(self):
        """同一 workspace 写盘串行"""
        order: list[int] = []

        async def worker(idx: int, delay: float):
            lock = await WorkspaceLock.acquire("/tmp/serial_ws")
            try:
                order.append(idx)
                await asyncio.sleep(delay)
            finally:
                await WorkspaceLock.release("/tmp/serial_ws")

        # worker 0 先获取锁，worker 1 必须等待
        t0 = asyncio.create_task(worker(0, 0.05))
        await asyncio.sleep(0.01)  # 确保 t0 先 acquire
        t1 = asyncio.create_task(worker(1, 0.01))

        await asyncio.gather(t0, t1)
        assert order == [0, 1]

    @pytest.mark.asyncio
    async def test_different_workspaces_parallel(self):
        """不同 workspace 可并行"""
        active: list[int] = []
        max_concurrent = 0

        async def worker(ws: str, idx: int):
            nonlocal max_concurrent
            lock = await WorkspaceLock.acquire(ws)
            try:
                active.append(idx)
                if len(active) > max_concurrent:
                    max_concurrent = len(active)
                await asyncio.sleep(0.02)
                active.remove(idx)
            finally:
                await WorkspaceLock.release(ws)

        tasks = [
            asyncio.create_task(worker("/tmp/ws_a", 0)),
            asyncio.create_task(worker("/tmp/ws_b", 1)),
        ]
        await asyncio.gather(*tasks)
        assert max_concurrent == 2  # 两个不同 workspace 同时活跃

    @pytest.mark.asyncio
    async def test_cleanup_removes_unlocked(self):
        """cleanup 移除未锁定的锁"""
        lock = await WorkspaceLock.acquire("/tmp/cleanup_ws")
        await WorkspaceLock.release("/tmp/cleanup_ws")
        assert not lock.locked()

        await WorkspaceLock.cleanup()
        assert WorkspaceLock.active_count() == 0

    @pytest.mark.asyncio
    async def test_active_count(self):
        """活跃锁计数"""
        lock1 = await WorkspaceLock.acquire("/tmp/count_ws_1")
        assert WorkspaceLock.active_count() >= 1

        await WorkspaceLock.release("/tmp/count_ws_1")


# ============================================================
# BatchLimits
# ============================================================


class TestBatchLimits:
    """批量生成限流"""

    def test_within_limits(self):
        """在限制内不报错"""
        exceeded = check_batch_limits(
            entity_count=5, file_count=50, total_bytes=1000,
        )
        assert len(exceeded) == 0

    def test_exceed_max_entities(self):
        """超过最大实体数"""
        exceeded = check_batch_limits(entity_count=25)
        assert len(exceeded) == 1
        assert exceeded[0].limit_type == "max_entities"
        assert exceeded[0].current == 25
        assert exceeded[0].maximum == DEFAULT_LIMITS.max_entities

    def test_exceed_max_files(self):
        """超过最大文件数"""
        exceeded = check_batch_limits(entity_count=1, file_count=600)
        assert len(exceeded) == 1
        assert exceeded[0].limit_type == "max_files"

    def test_exceed_max_bytes(self):
        """超过最大字节数"""
        exceeded = check_batch_limits(
            entity_count=1,
            total_bytes=20 * 1024 * 1024,  # 20 MB
        )
        assert len(exceeded) == 1
        assert exceeded[0].limit_type == "max_total_bytes"

    def test_multiple_exceeded(self):
        """多个限制同时超出"""
        exceeded = check_batch_limits(
            entity_count=25,
            file_count=600,
            total_bytes=20 * 1024 * 1024,
        )
        assert len(exceeded) == 3

    def test_custom_limits(self):
        """自定义限制"""
        custom = BatchLimits(max_entities=5)
        exceeded = check_batch_limits(entity_count=6, limits=custom)
        assert len(exceeded) == 1
        assert exceeded[0].maximum == 5

    def test_zero_counts_skip_check(self):
        """file_count=0 和 total_bytes=0 时跳过检查"""
        exceeded = check_batch_limits(entity_count=1, file_count=0, total_bytes=0)
        assert len(exceeded) == 0


# ============================================================
# RunCache
# ============================================================


class TestRunCache:
    """Run 内文件缓存"""

    def test_read_and_cache(self):
        """读取文件并缓存"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8",
        ) as f:
            f.write("hello")
            path = f.name

        try:
            cache = RunCache()
            content = cache.read_file(path)
            assert content == "hello"

            # 第二次应命中缓存
            content2 = cache.read_file(path)
            assert content2 == "hello"

            stats = cache.stats()
            assert stats["cache_hits"] == 1
            assert stats["cache_misses"] == 1
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        """不存在的文件返回 None"""
        cache = RunCache()
        result = cache.read_file("/nonexistent/file.txt")
        assert result is None

    def test_exists_cache(self):
        """exists 带缓存"""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name

        try:
            cache = RunCache()
            assert cache.exists(path) is True
            # 第二次应命中缓存
            assert cache.exists(path) is True
        finally:
            os.unlink(path)

    def test_exists_nonexistent(self):
        """不存在的文件 exists=False"""
        cache = RunCache()
        assert cache.exists("/nonexistent/path") is False

    def test_invalidate(self):
        """写入后使缓存失效"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8",
        ) as f:
            f.write("v1")
            path = f.name

        try:
            cache = RunCache()
            assert cache.read_file(path) == "v1"

            # 模拟写入
            with open(path, "w", encoding="utf-8") as f:
                f.write("v2")
            cache.invalidate(path)

            # 重新读取应得到新内容
            assert cache.read_file(path) == "v2"
        finally:
            os.unlink(path)

    def test_normpath_cache(self):
        """路径规范化缓存"""
        cache = RunCache()
        p1 = cache.normpath("a/b/../c")
        p2 = cache.normpath("a/b/../c")
        assert p1 == p2
        assert cache.stats()["cached_paths"] >= 1

    def test_clear(self):
        """清空缓存"""
        cache = RunCache()
        cache.read_file(__file__)  # 读取当前测试文件
        assert cache.stats()["cached_files"] > 0

        cache.clear()
        assert cache.stats()["cached_files"] == 0
        assert cache.stats()["cache_hits"] == 0


# ============================================================
# PerfMetrics
# ============================================================


class TestPerfMetrics:
    """性能指标"""

    def test_timer(self):
        """计时器"""
        metrics = PerfMetrics()
        metrics.start_timer("render")
        # 模拟一些工作
        metrics.stop_timer("render")

        result = metrics.to_dict()
        assert "render_ms" in result
        assert result["render_ms"] >= 0

    def test_counter(self):
        """计数器"""
        metrics = PerfMetrics()
        metrics.increment("file_count", 5)
        metrics.increment("file_count", 3)
        metrics.set_counter("conflict_count", 2)

        result = metrics.to_dict()
        assert result["file_count"] == 8
        assert result["conflict_count"] == 2

    def test_context_manager_timer(self):
        """context manager 计时"""
        metrics = PerfMetrics()

        with metrics.timer("write"):
            pass  # 模拟写入

        result = metrics.to_dict()
        assert "write_ms" in result
        assert result["write_ms"] >= 0

    def test_total_ms(self):
        """总耗时"""
        metrics = PerfMetrics()
        result = metrics.to_dict()
        assert "total_ms" in result
        assert result["total_ms"] >= 0

    def test_accumulating_timer(self):
        """计时器累加"""
        metrics = PerfMetrics()
        with metrics.timer("render"):
            pass
        with metrics.timer("render"):
            pass

        result = metrics.to_dict()
        assert "render_ms" in result

    def test_empty_metrics(self):
        """空指标"""
        metrics = PerfMetrics()
        result = metrics.to_dict()
        assert "total_ms" in result
        assert len(result) == 1  # 只有 total_ms
