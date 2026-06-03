"""Tests for pip install security restrictions. / 测试

Covers:
- _parse_package_name: extracts package name from requirement specifiers
- validate_requirements: whitelist validation
- ALLOWED_PACKAGES: common packages are included"""

from __future__ import annotations

import pytest

from app.plugins.security import (
    ALLOWED_PACKAGES,
    _parse_package_name,
    validate_requirements,
)


class TestParsePackageName:
    """Test requirement line parsing. / 测试"""

    @pytest.mark.parametrize(
        "line, expected",
        [
            ("requests", "requests"),
            ("requests>=2.28.0", "requests"),
            ("requests==2.28.0", "requests"),
            ("requests~=2.28", "requests"),
            ("requests<=3.0", "requests"),
            ("requests!=2.25", "requests"),
            ("requests>2.0", "requests"),
            ("requests<3.0", "requests"),
            ("pydantic[email]>=2.0", "pydantic"),
            ("pydantic[email,dotenv]~=2.0", "pydantic"),
            ("beautifulsoup4==4.12.2", "beautifulsoup4"),
            ("  httpx  ", "httpx"),
            ("numpy;python_version>='3.8'", "numpy"),
            ("PyYAML>=6.0", "pyyaml"),
            ("Pillow>=9.0", "pillow"),
        ],
    )
    def test_parse_valid(self, line: str, expected: str) -> None:
        assert _parse_package_name(line) == expected

    def test_empty_line(self) -> None:
        assert _parse_package_name("") == ""

    def test_whitespace(self) -> None:
        assert _parse_package_name("   ") == ""


class TestValidateRequirements:
    """Test whitelist validation. / 测试"""

    def test_all_allowed(self) -> None:
        deps = ["requests>=2.28", "httpx~=0.24", "pydantic>=2.0"]
        allowed, rejected = validate_requirements(deps)
        assert len(allowed) == 3
        assert len(rejected) == 0
        assert deps == allowed

    def test_all_rejected(self) -> None:
        deps = ["evil-package>=1.0", "malware==0.1"]
        allowed, rejected = validate_requirements(deps)
        assert len(allowed) == 0
        assert len(rejected) == 2
        assert "evil-package" in rejected
        assert "malware" in rejected

    def test_mixed(self) -> None:
        deps = ["requests>=2.28", "evil-package>=1.0", "numpy"]
        allowed, rejected = validate_requirements(deps)
        assert len(allowed) == 2
        assert len(rejected) == 1
        assert "requests>=2.28" in allowed
        assert "numpy" in allowed
        assert "evil-package" in rejected

    def test_empty_list(self) -> None:
        allowed, rejected = validate_requirements([])
        assert allowed == []
        assert rejected == []

    def test_with_version_specifiers(self) -> None:
        deps = ["requests>=2.28,<3.0", "openai~=1.0"]
        allowed, rejected = validate_requirements(deps)
        assert len(allowed) == 2
        assert len(rejected) == 0

    def test_case_insensitive(self) -> None:
        """Package names are normalized to lowercase. / 说明"""
        deps = ["PyYAML>=6.0", "Pillow>=9.0"]
        allowed, rejected = validate_requirements(deps)
        assert len(allowed) == 2
        assert len(rejected) == 0

    def test_extras_handled(self) -> None:
        """Packages with extras are correctly parsed. / 解析/提取"""
        deps = ["pydantic[email]>=2.0"]
        allowed, rejected = validate_requirements(deps)
        assert len(allowed) == 1
        assert len(rejected) == 0


class TestAllowedPackages:
    """Test that common packages are in the whitelist. / 测试"""

    @pytest.mark.parametrize(
        "pkg",
        [
            "requests",
            "httpx",
            "aiohttp",
            "beautifulsoup4",
            "pydantic",
            "numpy",
            "pandas",
            "openai",
            "anthropic",
            "redis",
            "boto3",
            "pillow",
            "jinja2",
            "cryptography",
            "pyjwt",
            "tenacity",
            "click",
        ],
    )
    def test_common_packages_allowed(self, pkg: str) -> None:
        assert pkg in ALLOWED_PACKAGES

    @pytest.mark.parametrize(
        "pkg",
        [
            "os",
            "sys",
            "subprocess",
            "pickle",
            "marshal",
            "ctypes",
            "socket",
        ],
    )
    def test_dangerous_packages_not_allowed(self, pkg: str) -> None:
        assert pkg not in ALLOWED_PACKAGES
