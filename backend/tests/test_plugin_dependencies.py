"""
插件依赖管理单元测试

覆盖：
- _parse_version: semver 解析
- _check_version_constraint: 各操作符 (>=, <=, ==, !=, >, <, ~=)
- check_platform_version: 平台版本校验
- check_platform_version_or_raise: 异常抛出
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.plugins.dependencies import (
    _check_version_constraint,
    _parse_version,
    check_platform_version,
    check_platform_version_or_raise,
)


# ========================================
# _parse_version
# ========================================

class TestParseVersion:
    def test_standard(self) -> None:
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_zeros(self) -> None:
        assert _parse_version("0.0.0") == (0, 0, 0)

    def test_large_numbers(self) -> None:
        assert _parse_version("10.20.300") == (10, 20, 300)

    def test_prerelease_ignored(self) -> None:
        assert _parse_version("1.2.3-beta.1") == (1, 2, 3)

    def test_invalid_returns_zeros(self) -> None:
        assert _parse_version("invalid") == (0, 0, 0)

    def test_empty_returns_zeros(self) -> None:
        assert _parse_version("") == (0, 0, 0)


# ========================================
# _check_version_constraint
# ========================================

class TestCheckVersionConstraint:
    def test_gte_pass(self) -> None:
        assert _check_version_constraint("2.0.0", ">=1.0.0") is True

    def test_gte_equal(self) -> None:
        assert _check_version_constraint("1.0.0", ">=1.0.0") is True

    def test_gte_fail(self) -> None:
        assert _check_version_constraint("0.9.0", ">=1.0.0") is False

    def test_lte_pass(self) -> None:
        assert _check_version_constraint("1.0.0", "<=2.0.0") is True

    def test_lte_fail(self) -> None:
        assert _check_version_constraint("3.0.0", "<=2.0.0") is False

    def test_eq_pass(self) -> None:
        assert _check_version_constraint("1.0.0", "==1.0.0") is True

    def test_eq_fail(self) -> None:
        assert _check_version_constraint("1.0.1", "==1.0.0") is False

    def test_ne_pass(self) -> None:
        assert _check_version_constraint("1.0.1", "!=1.0.0") is True

    def test_ne_fail(self) -> None:
        assert _check_version_constraint("1.0.0", "!=1.0.0") is False

    def test_gt_pass(self) -> None:
        assert _check_version_constraint("2.0.0", ">1.0.0") is True

    def test_gt_equal_fail(self) -> None:
        assert _check_version_constraint("1.0.0", ">1.0.0") is False

    def test_lt_pass(self) -> None:
        assert _check_version_constraint("0.9.0", "<1.0.0") is True

    def test_lt_fail(self) -> None:
        assert _check_version_constraint("1.0.0", "<1.0.0") is False

    def test_compatible_same_minor(self) -> None:
        assert _check_version_constraint("1.2.5", "~=1.2.0") is True

    def test_compatible_different_minor(self) -> None:
        assert _check_version_constraint("1.3.0", "~=1.2.0") is False

    def test_compatible_lower(self) -> None:
        assert _check_version_constraint("1.1.0", "~=1.2.0") is False

    def test_no_operator_exact_match(self) -> None:
        assert _check_version_constraint("1.0.0", "1.0.0") is True

    def test_no_operator_no_match(self) -> None:
        assert _check_version_constraint("1.0.1", "1.0.0") is False

    def test_whitespace_handling(self) -> None:
        assert _check_version_constraint("2.0.0", ">= 1.0.0") is True


# ========================================
# check_platform_version
# ========================================

class TestCheckPlatformVersion:
    def test_no_requirement(self) -> None:
        assert check_platform_version(None) is True

    def test_requirement_met(self) -> None:
        assert check_platform_version(">=1.0.0", "2.0.0") is True

    def test_requirement_not_met(self) -> None:
        assert check_platform_version(">=3.0.0", "2.0.0") is False

    def test_exact_version(self) -> None:
        assert check_platform_version("==1.5.0", "1.5.0") is True
        assert check_platform_version("==1.5.0", "1.5.1") is False


# ========================================
# check_platform_version_or_raise
# ========================================

class TestCheckPlatformVersionOrRaise:
    def test_met_does_not_raise(self) -> None:
        check_platform_version_or_raise(">=1.0.0", "2.0.0")

    def test_not_met_raises(self) -> None:
        from app.exceptions import BusinessException
        with pytest.raises(BusinessException):
            check_platform_version_or_raise(">=5.0.0", "1.0.0")

    def test_none_does_not_raise(self) -> None:
        check_platform_version_or_raise(None)
