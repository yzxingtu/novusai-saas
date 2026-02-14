"""
受控区域 Patch 引擎 — 单元测试

覆盖：
- 锚点查找（JS/Python 风格）
- 区域替换（保留用户手改）
- 锚点缺失降级（append/error/skip）
- 幂等性（重复执行不重复）
- 创建区域块
- 移除所有区域
- 多区域同时 patch
"""

import pytest

from app.codegen.region_patch import (
    FallbackStrategy,
    PatchResult,
    RegionPatch,
    apply_region_patch,
    create_region_block,
    find_regions,
    strip_regions,
)


# ============================================================
# find_regions
# ============================================================


class TestFindRegions:
    """锚点查找"""

    def test_js_style(self):
        content = (
            "// user code\n"
            "// BEGIN CRUD-GEN:routes\n"
            "import order from './order'\n"
            "// END CRUD-GEN:routes\n"
            "// more user code\n"
        )
        regions = find_regions(content)
        assert "routes" in regions

    def test_python_style(self):
        content = (
            "# user code\n"
            "# BEGIN CRUD-GEN:models\n"
            "from .order import Order\n"
            "# END CRUD-GEN:models\n"
        )
        regions = find_regions(content)
        assert "models" in regions

    def test_multiple_regions(self):
        content = (
            "// BEGIN CRUD-GEN:a\n"
            "content a\n"
            "// END CRUD-GEN:a\n"
            "// BEGIN CRUD-GEN:b\n"
            "content b\n"
            "// END CRUD-GEN:b\n"
        )
        regions = find_regions(content)
        assert len(regions) == 2
        assert "a" in regions
        assert "b" in regions

    def test_no_regions(self):
        regions = find_regions("just plain text\nno anchors\n")
        assert len(regions) == 0

    def test_unmatched_begin(self):
        """BEGIN 无对应 END → 不算有效 region"""
        content = "// BEGIN CRUD-GEN:orphan\ncontent\n"
        regions = find_regions(content)
        assert len(regions) == 0


# ============================================================
# apply_region_patch — 替换已有区域
# ============================================================


class TestApplyPatchReplace:
    """受控区域替换"""

    def test_replace_region(self):
        content = (
            "// user code above\n"
            "// BEGIN CRUD-GEN:routes\n"
            "import old from './old'\n"
            "// END CRUD-GEN:routes\n"
            "// user code below\n"
        )
        result = apply_region_patch(
            content,
            [RegionPatch(region_id="routes", content="import new from './new'")],
        )
        assert result.success is True
        assert "routes" in result.regions_updated
        assert "import new from './new'" in result.patched_content
        assert "import old from './old'" not in result.patched_content
        # 用户代码保留
        assert "// user code above" in result.patched_content
        assert "// user code below" in result.patched_content

    def test_preserve_anchors(self):
        """锚点行保留"""
        content = (
            "// BEGIN CRUD-GEN:test\n"
            "old content\n"
            "// END CRUD-GEN:test\n"
        )
        result = apply_region_patch(
            content,
            [RegionPatch(region_id="test", content="new content")],
        )
        assert "// BEGIN CRUD-GEN:test" in result.patched_content
        assert "// END CRUD-GEN:test" in result.patched_content
        assert "new content" in result.patched_content

    def test_idempotent(self):
        """重复执行幂等"""
        content = (
            "// BEGIN CRUD-GEN:routes\n"
            "import old from './old'\n"
            "// END CRUD-GEN:routes\n"
        )
        patch = [RegionPatch(region_id="routes", content="import new from './new'")]

        result1 = apply_region_patch(content, patch)
        result2 = apply_region_patch(result1.patched_content, patch)

        assert result1.patched_content == result2.patched_content
        assert result2.patched_content.count("import new") == 1


# ============================================================
# apply_region_patch — 降级策略
# ============================================================


class TestApplyPatchFallback:
    """锚点缺失降级"""

    def test_append_fallback(self):
        """默认 append：追加新区域"""
        content = "// existing code\n"
        result = apply_region_patch(
            content,
            [RegionPatch(region_id="routes", content="import order")],
            fallback=FallbackStrategy.APPEND,
        )
        assert result.success is True
        assert "routes" in result.regions_appended
        assert "// BEGIN CRUD-GEN:routes" in result.patched_content
        assert "// END CRUD-GEN:routes" in result.patched_content
        assert "import order" in result.patched_content

    def test_error_fallback(self):
        """error：报错"""
        result = apply_region_patch(
            "// no anchors\n",
            [RegionPatch(region_id="routes", content="import order")],
            fallback=FallbackStrategy.ERROR,
        )
        assert result.success is False
        assert len(result.errors) == 1

    def test_skip_fallback(self):
        """skip：跳过"""
        result = apply_region_patch(
            "// no anchors\n",
            [RegionPatch(region_id="routes", content="import order")],
            fallback=FallbackStrategy.SKIP,
        )
        assert result.success is True
        assert "routes" in result.regions_skipped
        assert "import order" not in result.patched_content


# ============================================================
# apply_region_patch — 多区域
# ============================================================


class TestMultiRegionPatch:
    """多区域同时 patch"""

    def test_patch_two_regions(self):
        content = (
            "// BEGIN CRUD-GEN:routes\n"
            "old routes\n"
            "// END CRUD-GEN:routes\n"
            "\n"
            "// BEGIN CRUD-GEN:exports\n"
            "old exports\n"
            "// END CRUD-GEN:exports\n"
        )
        result = apply_region_patch(content, [
            RegionPatch(region_id="routes", content="new routes"),
            RegionPatch(region_id="exports", content="new exports"),
        ])
        assert result.success is True
        assert len(result.regions_updated) == 2
        assert "new routes" in result.patched_content
        assert "new exports" in result.patched_content
        assert "old routes" not in result.patched_content


# ============================================================
# create_region_block
# ============================================================


class TestCreateRegionBlock:
    """创建区域块"""

    def test_js_style(self):
        block = create_region_block("routes", "import order", "//")
        assert "// BEGIN CRUD-GEN:routes" in block
        assert "// END CRUD-GEN:routes" in block
        assert "import order" in block

    def test_python_style(self):
        block = create_region_block("models", "from .order import Order", "#")
        assert "# BEGIN CRUD-GEN:models" in block
        assert "# END CRUD-GEN:models" in block


# ============================================================
# strip_regions
# ============================================================


class TestStripRegions:
    """移除所有区域"""

    def test_strip_single(self):
        content = (
            "before\n"
            "// BEGIN CRUD-GEN:routes\n"
            "generated\n"
            "// END CRUD-GEN:routes\n"
            "after\n"
        )
        stripped = strip_regions(content)
        assert "generated" not in stripped
        assert "BEGIN CRUD-GEN" not in stripped
        assert "before" in stripped
        assert "after" in stripped

    def test_strip_multiple(self):
        content = (
            "// BEGIN CRUD-GEN:a\naa\n// END CRUD-GEN:a\n"
            "middle\n"
            "// BEGIN CRUD-GEN:b\nbb\n// END CRUD-GEN:b\n"
        )
        stripped = strip_regions(content)
        assert "aa" not in stripped
        assert "bb" not in stripped
        assert "middle" in stripped

    def test_strip_none(self):
        content = "no regions here\n"
        assert strip_regions(content) == content


# ============================================================
# Python 风格注释
# ============================================================


class TestPythonCommentStyle:
    """Python # 注释风格"""

    def test_python_patch(self):
        content = (
            "# BEGIN CRUD-GEN:imports\n"
            "from .old import Model\n"
            "# END CRUD-GEN:imports\n"
        )
        result = apply_region_patch(
            content,
            [RegionPatch(region_id="imports", content="from .new import Model")],
        )
        assert result.success is True
        assert "from .new import Model" in result.patched_content

    def test_python_append(self):
        result = apply_region_patch(
            "# existing\n",
            [RegionPatch(region_id="imports", content="from .order import Order")],
            fallback=FallbackStrategy.APPEND,
            comment_style="#",
        )
        assert "# BEGIN CRUD-GEN:imports" in result.patched_content
        assert "# END CRUD-GEN:imports" in result.patched_content
