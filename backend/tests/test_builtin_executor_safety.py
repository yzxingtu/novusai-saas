"""
Tests for builtin_executor safe math expression evaluator.

Covers:
- _safe_eval_math: valid arithmetic expressions
- _safe_eval_math: rejects dangerous expressions (imports, function calls, etc.)
- Edge cases: division by zero, large exponents, empty/whitespace
"""

from __future__ import annotations

import pytest

from app.ai.tools.executors.builtin_executor import _safe_eval_math


class TestSafeEvalMathValid:
    """Test valid math expressions."""

    @pytest.mark.parametrize("expr, expected", [
        ("1 + 2", 3),
        ("10 - 3", 7),
        ("4 * 5", 20),
        ("10 / 3", 10 / 3),
        ("10 // 3", 3),
        ("10 % 3", 1),
        ("2 ** 10", 1024),
        ("(1 + 2) * 3", 9),
        ("-5", -5),
        ("+5", 5),
        ("3.14 * 2", 6.28),
        ("0.1 + 0.2", 0.1 + 0.2),
        ("100", 100),
        ("  42  ", 42),
        ("(-3) * (-4)", 12),
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("1.5e2", 150.0),
        ("2 ** 0", 1),
        ("0 * 999", 0),
    ])
    def test_valid_expressions(self, expr: str, expected: int | float) -> None:
        result = _safe_eval_math(expr)
        assert result == pytest.approx(expected)


class TestSafeEvalMathDangerous:
    """Test that dangerous expressions are rejected."""

    @pytest.mark.parametrize("expr", [
        "__import__('os').system('ls')",
        "import os",
        "eval('1+1')",
        "exec('print(1)')",
        "open('/etc/passwd')",
        "os.system('rm -rf /')",
        "lambda: 1",
        "[x for x in range(10)]",
        "{'a': 1}",
        "[1, 2, 3]",
        "print('hello')",
        "type(1)",
        "dir()",
        "globals()",
        "locals()",
        "1 if True else 0",
        "x = 5",
        "a + b",           # variables not allowed
        "math.sqrt(4)",    # attribute access not allowed
        "int('5')",        # function calls not allowed
        "'hello'",         # strings not allowed
        "True",            # booleans not allowed
        "None",            # None not allowed
    ])
    def test_dangerous_expressions_rejected(self, expr: str) -> None:
        with pytest.raises((ValueError, SyntaxError, TypeError)):
            _safe_eval_math(expr)

    def test_large_exponent_rejected(self) -> None:
        """Prevent DoS via large exponents like 10**10000."""
        with pytest.raises(ValueError, match="Exponent too large"):
            _safe_eval_math("10 ** 10000")

    def test_negative_large_exponent_rejected(self) -> None:
        with pytest.raises(ValueError, match="Exponent too large"):
            _safe_eval_math("2 ** -5000")


class TestSafeEvalMathEdgeCases:
    """Test edge cases."""

    def test_division_by_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            _safe_eval_math("1 / 0")

    def test_floor_division_by_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            _safe_eval_math("1 // 0")

    def test_modulo_by_zero(self) -> None:
        with pytest.raises(ZeroDivisionError):
            _safe_eval_math("1 % 0")

    def test_empty_string(self) -> None:
        with pytest.raises(SyntaxError):
            _safe_eval_math("")

    def test_whitespace_only(self) -> None:
        with pytest.raises(SyntaxError):
            _safe_eval_math("   ")

    def test_syntax_error(self) -> None:
        with pytest.raises(SyntaxError):
            _safe_eval_math("1 +")

    def test_boundary_exponent_allowed(self) -> None:
        """Exponent exactly 1000 should be allowed."""
        result = _safe_eval_math("2 ** 1000")
        assert result == 2 ** 1000

    def test_nested_parentheses(self) -> None:
        result = _safe_eval_math("((1 + 2) * (3 + 4))")
        assert result == 21
