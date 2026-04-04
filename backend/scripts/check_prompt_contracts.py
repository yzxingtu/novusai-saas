"""
Prompt contract guard / Prompt contract 自检脚本

Detect fixed model-facing prompt text that is written directly in Python under
`backend/app/ai` or `backend/app/services/ai` instead of using
`backend/app/ai/prompt_contracts/resources/`.
检测 `backend/app/ai` 与 `backend/app/services/ai` 下直接写在 Python 里的固定模型侧提示词，
要求统一改为 `backend/app/ai/prompt_contracts/resources/` 资源文件。
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

PROMPT_NAME_MARKERS = ("prompt", "hint", "guidance", "instruction", "preamble")
PROMPT_SIGNAL_MARKERS = (
    "do not",
    "must ",
    "must\n",
    "respond only",
    "output only",
    "current page",
    "available operations",
    "workflow",
    "agent loop",
    "you are ",
)
DEFAULT_SCAN_DIRS = ("app/ai", "app/services/ai")
EXCLUDED_PATH_PARTS = ("__pycache__", "prompt_contracts")


class LiteralInfo(NamedTuple):
    """Collected literal summary / 收集到的字面量摘要"""

    text: str
    uses_prompt_contract: bool


@dataclass(frozen=True)
class PromptContractViolation:
    """Violation payload / 违规信息"""

    path: Path
    line: int
    column: int
    context: str
    preview: str


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _looks_like_prompt_text(
    text: str,
    *,
    min_chars: int,
    require_signal: bool,
) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    if len(normalized) < min_chars and "\n" not in text:
        return False
    lowered = normalized.lower()
    if any(marker in lowered for marker in PROMPT_SIGNAL_MARKERS):
        return True
    if require_signal:
        return False
    return len(normalized) >= max(min_chars * 2, 180)


def _called_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _literal_info(node: ast.AST | None) -> LiteralInfo | None:
    if node is None:
        return None

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return LiteralInfo(node.value, False)

    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("{}")
            else:
                return None
        return LiteralInfo("".join(parts), False)

    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_info(node.left)
        right = _literal_info(node.right)
        if left is None or right is None:
            return None
        return LiteralInfo(
            left.text + right.text,
            left.uses_prompt_contract or right.uses_prompt_contract,
        )

    if isinstance(node, ast.Call):
        callee = _called_name(node.func)
        if callee == "render_prompt_contract":
            return LiteralInfo("", True)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            base = _literal_info(node.func.value)
            if base is None:
                return None
            return LiteralInfo(base.text, base.uses_prompt_contract)

    return None


def _keyword_value(node: ast.Call, name: str) -> ast.AST | None:
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


class PromptContractVisitor(ast.NodeVisitor):
    """AST visitor for prompt contract violations / prompt contract 违规 AST 访问器"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[PromptContractViolation] = []
        self._function_stack: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: D401
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: D401
        self._function_stack.append(node.name)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: D401
        literal = _literal_info(node.value)
        if literal and not literal.uses_prompt_contract:
            target_names = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]
            if any(
                any(marker in name.lower() for marker in PROMPT_NAME_MARKERS)
                for name in target_names
            ) and _looks_like_prompt_text(
                literal.text,
                min_chars=24,
                require_signal=False,
            ):
                self._add_violation(
                    node,
                    context=f"assignment:{','.join(target_names)}",
                    text=literal.text,
                )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: D401
        literal = _literal_info(node.value)
        target_name = node.target.id if isinstance(node.target, ast.Name) else ""
        if (
            literal
            and not literal.uses_prompt_contract
            and target_name
            and any(marker in target_name.lower() for marker in PROMPT_NAME_MARKERS)
            and _looks_like_prompt_text(literal.text, min_chars=24, require_signal=False)
        ):
            self._add_violation(
                node,
                context=f"assignment:{target_name}",
                text=literal.text,
            )
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:  # noqa: D401
        literal = _literal_info(node.value)
        fn_name = self._function_stack[-1] if self._function_stack else ""
        if (
            literal
            and not literal.uses_prompt_contract
            and fn_name
            and any(marker in fn_name.lower() for marker in PROMPT_NAME_MARKERS)
            and _looks_like_prompt_text(literal.text, min_chars=48, require_signal=False)
        ):
            self._add_violation(
                node,
                context=f"return:{fn_name}",
                text=literal.text,
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: D401
        callee = _called_name(node.func)

        if callee == "ChatMessage":
            role_value = _keyword_value(node, "role")
            content_value = _keyword_value(node, "content")
            role_literal = (
                role_value.value
                if isinstance(role_value, ast.Constant)
                and isinstance(role_value.value, str)
                else None
            )
            content_literal = _literal_info(content_value)
            if (
                role_literal in {"system", "user"}
                and content_literal
                and not content_literal.uses_prompt_contract
                and _looks_like_prompt_text(
                    content_literal.text,
                    min_chars=56,
                    require_signal=True,
                )
            ):
                self._add_violation(
                    node,
                    context=f"chatmessage:{role_literal}",
                    text=content_literal.text,
                )

        if callee == "ToolDefinition":
            description_value = _keyword_value(node, "description")
            literal = _literal_info(description_value)
            if (
                literal
                and not literal.uses_prompt_contract
                and _looks_like_prompt_text(
                    literal.text,
                    min_chars=72,
                    require_signal=False,
                )
            ):
                self._add_violation(
                    node,
                    context="tool_definition:description",
                    text=literal.text,
                )

        self.generic_visit(node)

    def _add_violation(self, node: ast.AST, *, context: str, text: str) -> None:
        preview = _normalize_text(text)[:160]
        self.violations.append(
            PromptContractViolation(
                path=self.path,
                line=getattr(node, "lineno", 1),
                column=getattr(node, "col_offset", 0) + 1,
                context=context,
                preview=preview,
            )
        )


def scan_python_file(path: Path) -> list[PromptContractViolation]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    visitor = PromptContractVisitor(path)
    visitor.visit(tree)
    return visitor.violations


def scan_paths(root: Path, relative_dirs: list[str] | None = None) -> list[PromptContractViolation]:
    violations: list[PromptContractViolation] = []
    scan_dirs = relative_dirs or list(DEFAULT_SCAN_DIRS)
    for relative_dir in scan_dirs:
        base_dir = (root / relative_dir).resolve()
        if not base_dir.exists():
            continue
        for path in base_dir.rglob("*.py"):
            if any(part in EXCLUDED_PATH_PARTS for part in path.parts):
                continue
            violations.extend(scan_python_file(path))
    return sorted(violations, key=lambda item: (str(item.path), item.line, item.column))


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when fixed model-facing prompt text is hardcoded directly in "
            "Python under app/ai or app/services/ai."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Backend root directory / backend 根目录",
    )
    parser.add_argument(
        "--dir",
        dest="scan_dirs",
        action="append",
        default=[],
        help="Relative directory to scan (can be passed multiple times) / 要扫描的相对目录",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    root = args.root.resolve()
    scan_dirs = args.scan_dirs or list(DEFAULT_SCAN_DIRS)
    violations = scan_paths(root, scan_dirs)

    if not violations:
        print("Prompt contract check passed.")
        return 0

    print("Prompt contract check failed. Move fixed model-facing prompt text into backend/app/ai/prompt_contracts/resources/.")
    for violation in violations:
        print(
            f"- {violation.path.relative_to(root)}:{violation.line}:{violation.column} "
            f"[{violation.context}] {violation.preview}"
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
