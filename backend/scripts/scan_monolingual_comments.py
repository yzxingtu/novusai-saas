"""Scan source for likely monolingual line comments (heuristic). / 扫描疑似单语行注释（启发式）。

Output is for human review only — do not pipe into automated replacement. Prefer bilingual_comment_audit.py
for block-aware listing. / 输出仅供人工对照，勿接自动替换；需要块级清单时优先用 bilingual_comment_audit.py。
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
}

SKIP_DIR_PREFIXES = (".",)

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


def has_cjk(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s))


def has_latin_word(s: str) -> bool:
    return bool(re.search(r"[a-zA-Z]{2,}", s))


def is_bilingual_comment(s: str) -> bool:
    s = s.strip()
    return bool(has_cjk(s) and has_latin_word(s))


def skip_comment_text(t: str) -> bool:
    t = t.strip()
    if len(t) < 2:
        return True
    if t.startswith("http") or "://" in t:
        return True
    if re.match(r"^#!", t):
        return True
    low = t.lower()
    if low.startswith(
        (
            "eslint",
            "prettier",
            "stylelint",
            "noinspection",
            "type:",
            "vitest",
            "cspell",
            "volar",
            "ts-ignore",
        )
    ):
        return True
    if t in ("-", "*", "---", "...", "fmt:", "noqa", "noqa:"):
        return True
    return bool(re.fullmatch(r"[#=*\-]{2,}", t))


def py_inline_comment(line: str) -> str | None:
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


def ts_inline_comment(line: str) -> str | None:
    s = line.strip()
    if s.startswith("//"):
        return s[2:].strip()
    return None


def classify_comment(text: str) -> str | None:
    if skip_comment_text(text):
        return None
    if is_bilingual_comment(text):
        return None
    if has_cjk(text) and not has_latin_word(text):
        return "zh_only"
    if has_latin_word(text) and not has_cjk(text):
        return "en_only"
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


def scan_file(path: Path) -> list[dict]:
    hits: list[dict] = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return hits
    ext = path.suffix.lower()
    lines = raw.splitlines()
    if ext == ".vue":
        # only <script> and <script setup> blocks, skip template/style for line // scan
        in_script = False
        script_lines: list[tuple[int, str]] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"<script\b", line.strip()):
                in_script = True
                i += 1
                continue
            if in_script and line.strip() == "</script>":
                in_script = False
                i += 1
                continue
            if in_script:
                script_lines.append((i + 1, line))
            i += 1
        for no, line in script_lines:
            c = ts_inline_comment(line)
            if not c:
                continue
            kind = classify_comment(c)
            if kind:
                hits.append(
                    {"file": str(path), "line": no, "kind": kind, "text": c[:500]}
                )
        return hits
    if ext in {".ts", ".tsx", ".js", ".mjs", ".cjs"}:
        for no, line in enumerate(lines, 1):
            c = ts_inline_comment(line)
            if not c:
                continue
            kind = classify_comment(c)
            if kind:
                hits.append(
                    {"file": str(path), "line": no, "kind": kind, "text": c[:500]}
                )
        return hits
    if ext == ".py":
        for no, line in enumerate(lines, 1):
            c = py_inline_comment(line)
            if not c:
                continue
            kind = classify_comment(c)
            if kind:
                hits.append(
                    {"file": str(path), "line": no, "kind": kind, "text": c[:500]}
                )
        return hits
    if ext in {".css", ".scss", ".less"}:
        for no, line in enumerate(lines, 1):
            s = line.strip()
            if not s.startswith("/*") and not s.endswith("*/") and "/*" not in s:
                # single-line /* ... */ only
                m = re.match(r"/\*\s*(.+?)\s*\*/", s)
                if m:
                    c = m.group(1)
                    kind = classify_comment(c)
                    if kind:
                        hits.append(
                            {
                                "file": str(path),
                                "line": no,
                                "kind": kind,
                                "text": c[:500],
                            }
                        )
        return hits
    return hits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "roots", nargs="*", default=["backend/app", "frontend", "backend/plugins"]
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    all_hits: list[dict] = []
    root_path = Path(__file__).resolve().parents[2]
    for r in args.roots:
        rp = root_path / r
        if not rp.is_dir():
            continue
        for f in walk_files(rp):
            all_hits.extend(scan_file(f))
    if args.json:
        print(json.dumps(all_hits, ensure_ascii=False, indent=2))
    else:
        print("total", len(all_hits))
        for h in all_hits[:200]:
            print(f"{h['kind']}\t{h['file']}:{h['line']}\t{h['text'][:120]}")


if __name__ == "__main__":
    main()
