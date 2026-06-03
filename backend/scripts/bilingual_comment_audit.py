"""Detect monolingual comment blocks (heuristic) for manual review only. / 启发式检测单语注释块，仅供人工审阅。

Do not use automated bulk find-replace or machine-translation scripts to “fix” comments in batch — errors are
hard to review and may corrupt code. Fix comments line-by-line in the editor (or small, reviewed diffs).
禁止用脚本批量查找替换或机翻批量“修复”注释，易出错且难审阅；请在编辑器中逐行（或小范围已审阅的 diff）修改。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SKIP_DIR_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    ".git",
    ".pytest_cache",
    "coverage",
    "htmlcov",
    ".mypy_cache",
    ".ruff_cache",
    "mcps",
    "build",
    "out",
}

TEXT_EXT = {
    ".py",
    ".ts",
    ".tsx",
    ".vue",
    ".js",
    ".mjs",
    ".cjs",
    ".css",
    ".scss",
    ".less",
}

# Third-party / tool-only: do not translate / 第三方或工具向：不翻译
SKIP_SUBSTR = (
    "http://",
    "https://",
    "<reference types",  # TS `/// <reference … />` directive line / TS 三斜杠引用指令行
    "eslint",
    "prettier",
    "stylelint",
    "noinspection",
    "vitest",
    "cspell",
    "volar",
    "ts-ignore",
    "ts-expect-error",
    "noqa",
    "pragma",
    "fmt:",
    "Copyright",
    "License",
    "SPDX",
)


def has_cjk(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s))


def has_latin_word(s: str) -> bool:
    return bool(re.search(r"[a-zA-Z]{2,}", s))


def is_bilingual_text(s: str) -> bool:
    t = s.strip()
    if not t:
        return True
    if " / " in t and has_cjk(t) and has_latin_word(t):
        return True
    return bool(has_cjk(t) and has_latin_word(t))


def should_skip_comment_text(t: str) -> bool:
    t = t.strip()
    if len(t) < 2:
        return True
    low = t.lower()
    for s in SKIP_SUBSTR:
        if s.lower() in low:
            return True
    if t.startswith("#!"):
        return True
    return bool(re.fullmatch(r"[#=*\-_]{2,}", t))


def py_full_line_comment(line: str) -> str | None:
    s = line.strip()
    if not s.startswith("#"):
        return None
    return s[1:].strip()


def py_inline_tail(line: str) -> str | None:
    if "#" not in line:
        return None
    i = line.find("#")
    prev = line[:i]
    in_str = False
    q = None
    for ch in prev:
        if ch in "\"'":
            if not in_str:
                in_str, q = True, ch
            elif ch == q:
                in_str, q = False, None
    if in_str:
        return None
    return line[i + 1 :].strip()


def ts_full_line_comment(line: str) -> str | None:
    s = line.strip()
    if s.startswith("//"):
        return s[2:].strip()
    return None


def walk_files(root: Path) -> list[Path]:
    import os

    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES
            and not d.startswith(".")
            and d not in {"build", "out", "coverage"}
        ]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in TEXT_EXT:
                continue
            out.append(p)
    return out


def extract_vue_script_lines(raw: str) -> list[tuple[int, str]]:
    lines = raw.splitlines()
    out: list[tuple[int, str]] = []
    in_script = False
    for i, line in enumerate(lines, 1):
        if re.match(r"<script\b", line.strip()):
            in_script = True
            continue
        if in_script and line.strip() == "</script>":
            in_script = False
            continue
        if in_script:
            out.append((i, line))
    return out


def scan_py_blocks(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    hits: list[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        fl = py_full_line_comment(line)
        if fl is not None:
            block_lines: list[tuple[int, str]] = []
            j = i
            while j < n:
                lj = lines[j]
                fj = py_full_line_comment(lj)
                if fj is None:
                    break
                block_lines.append((j + 1, fj))
                j += 1
            combined = "\n".join(t for _, t in block_lines)
            if (
                should_skip_comment_text(combined.split("\n")[0])
                and len(block_lines) == 1
            ):
                i = j
                continue
            if is_bilingual_text(combined):
                i = j
                continue
            # single-language block
            if not has_cjk(combined) and has_latin_word(combined):
                kind = "en_block"
            elif has_cjk(combined) and not has_latin_word(combined):
                kind = "zh_block"
            else:
                i = j
                continue
            hits.append(
                {
                    "file": str(path),
                    "start_line": block_lines[0][0],
                    "end_line": block_lines[-1][0],
                    "kind": kind,
                    "text": combined[:2000],
                    "style": "py_full",
                }
            )
            i = j
            continue
        inl = py_inline_tail(line)
        if (
            inl is not None
            and not should_skip_comment_text(inl)
            and not is_bilingual_text(inl)
        ):
            if not has_cjk(inl) and has_latin_word(inl):
                k = "en_inline"
            elif has_cjk(inl) and not has_latin_word(inl):
                k = "zh_inline"
            else:
                i += 1
                continue
            hits.append(
                {
                    "file": str(path),
                    "start_line": i + 1,
                    "end_line": i + 1,
                    "kind": k,
                    "text": inl[:2000],
                    "style": "py_inline",
                }
            )
        i += 1
    return hits


def scan_ts_like_blocks(
    lines: list[str] | list[tuple[int, str]], path: str
) -> list[dict]:
    """If lines are (file_line_no, text) tuples, use first as physical line number. / 若为 (行号, 文本) 元组则使用真实行号。"""
    hits: list[dict] = []
    if not lines:
        return hits
    if isinstance(lines[0], tuple):
        indexed: list[tuple[int, str]] = lines  # type: ignore[assignment]
        raw_lines = [t[1] for t in indexed]
        line_map = [t[0] for t in indexed]
    else:
        raw_lines = lines  # type: ignore[assignment]
        line_map = list(range(1, len(raw_lines) + 1))
    i = 0
    n = len(raw_lines)
    while i < n:
        line = raw_lines[i]
        fl = ts_full_line_comment(line)
        if fl is not None:
            block_lines: list[tuple[int, str]] = []
            j = i
            while j < n:
                lj = raw_lines[j]
                fj = ts_full_line_comment(lj)
                if fj is None:
                    break
                block_lines.append((line_map[j], fj))
                j += 1
            combined = "\n".join(t for _, t in block_lines)
            if (
                should_skip_comment_text(combined.split("\n")[0])
                and len(block_lines) == 1
            ):
                i = j
                continue
            if is_bilingual_text(combined):
                i = j
                continue
            if not has_cjk(combined) and has_latin_word(combined):
                kind = "en_block"
            elif has_cjk(combined) and not has_latin_word(combined):
                kind = "zh_block"
            else:
                i = j
                continue
            hits.append(
                {
                    "file": path,
                    "start_line": block_lines[0][0],
                    "end_line": block_lines[-1][0],
                    "kind": kind,
                    "text": combined[:2000],
                    "style": "ts_full",
                }
            )
            i = j
            continue
        i += 1
    return hits


def scan_file(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".py":
        return scan_py_blocks(path)
    if ext == ".vue":
        slines = extract_vue_script_lines(path.read_text(encoding="utf-8"))
        return scan_ts_like_blocks(slines, str(path))
    if ext in {".ts", ".tsx", ".js", ".mjs", ".cjs"}:
        return scan_ts_like_blocks(
            path.read_text(encoding="utf-8").splitlines(), str(path)
        )
    return []


def main() -> None:
    ap = argparse.ArgumentParser(
        epilog=(
            "Audit only — fix comments line-by-line in the editor; no bulk script replacement, "
            "no auto-apply from JSON, no machine-translation batch writers. / "
            "仅审计；请在编辑器逐行或小范围已审阅 diff 修改；禁止脚本批量替换、禁止按审计 JSON 自动写回、禁止机翻批量写入。"
        ),
    )
    ap.add_argument(
        "roots", nargs="*", default=["backend/app", "frontend", "backend/plugins"]
    )
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--count", action="store_true")
    args = ap.parse_args()
    root_path = Path(__file__).resolve().parents[2]
    all_hits: list[dict] = []
    for r in args.roots:
        rp = root_path / r
        if not rp.is_dir():
            continue
        for f in walk_files(rp):
            all_hits.extend(scan_file(f))
    if args.json:
        print(json.dumps(all_hits, ensure_ascii=False, indent=2))
    elif args.count:
        from collections import Counter

        c = Counter(h["kind"] for h in all_hits)
        print("total", len(all_hits), dict(c))
    else:
        print("total", len(all_hits))
        for h in all_hits[:80]:
            print(
                f"{h['kind']}\t{h['file']}:{h['start_line']}-{h['end_line']}\t{h['text'][:100].replace(chr(10), ' | ')}"
            )


if __name__ == "__main__":
    main()
