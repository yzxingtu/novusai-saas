#!/usr/bin/env python3
"""scripts/generate_release_notes.py

根据上一个版本标签到当前标签之间的 Git 提交记录，调用 OpenAI 兼容接口
自动生成结构化的 Release Notes，输出为 Markdown 文件。

用法:
    python scripts/generate_release_notes.py --tag v0.2.0 --output /tmp/release_notes.md

环境变量:
    AI_API_BASE   OpenAI 兼容接口地址（如 https://api.openai.com/v1）
    AI_API_KEY    接口密钥
    AI_MODEL      模型名称（默认 gpt-4o-mini）
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_git(*args: str) -> str:
    """运行 git 命令并返回 stdout。"""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def get_previous_tag(current_tag: str) -> str | None:
    """获取当前标签之前的上一个版本标签。"""
    try:
        all_tags = run_git("tag", "--sort=-v:refname")
    except subprocess.CalledProcessError:
        return None

    tags = [t for t in all_tags.splitlines() if t.startswith("v")]
    # 找到当前标签在列表中的位置，返回它前一个
    try:
        idx = tags.index(current_tag)
        return tags[idx + 1] if idx + 1 < len(tags) else None
    except ValueError:
        # 当前标签可能还没推上去，直接返回第一个
        return tags[0] if tags else None


def get_commits(prev_tag: str | None, current_tag: str) -> str:
    """获取两个标签之间的提交日志。"""
    if prev_tag:
        log_range = f"{prev_tag}..{current_tag}"
    else:
        log_range = current_tag

    try:
        return run_git(
            "log",
            log_range,
            "--pretty=format:%h %s",
            "--no-merges",
        )
    except subprocess.CalledProcessError:
        # 标签可能尚未 fetch，回退到最近 50 条
        return run_git(
            "log",
            "-50",
            "--pretty=format:%h %s",
            "--no-merges",
        )


def get_diff_stat(prev_tag: str | None, current_tag: str) -> str:
    """获取两个标签之间的文件变更统计。"""
    if not prev_tag:
        return ""
    try:
        return run_git("diff", "--stat", f"{prev_tag}...{current_tag}")
    except subprocess.CalledProcessError:
        return ""


def generate_notes_ai(
    commits: str,
    diff_stat: str,
    prev_tag: str | None,
    current_tag: str,
) -> str:
    """调用 OpenAI 兼容接口生成 Release Notes。"""
    try:
        from openai import OpenAI
    except ImportError:
        print("警告: openai 包未安装，使用回退模板", file=sys.stderr)
        return generate_notes_fallback(commits, prev_tag, current_tag)

    api_base = os.environ.get("AI_API_BASE", "")
    api_key = os.environ.get("AI_API_KEY", "")
    model = os.environ.get("AI_MODEL", "gpt-4o-mini")

    if not api_base or not api_key:
        print("警告: AI_API_BASE 或 AI_API_KEY 未配置，使用回退模板", file=sys.stderr)
        return generate_notes_fallback(commits, prev_tag, current_tag)

    version_range = f"{prev_tag or 'initial'}...{current_tag}" if prev_tag else current_tag

    prompt = f"""\
You are a release notes writer for the NovusAI SaaS project (a multi-tenant AI SaaS framework).

Generate structured, professional release notes in **Chinese** (简体中文) based on the git commit log below.

Version range: {version_range}

## Commit log
{commits}

## Diff stat
{diff_stat}

## Rules
- Group changes into categories: 🚀 新功能, 🐛 修复, ⚡ 优化, 🔧 重构, 📦 依赖, 📝 文档, 🧪 测试
- Skip categories with no relevant changes
- Each item should be one concise line
- Add a one-paragraph summary at the top describing the highlights of this release
- Do NOT invent features that don't appear in the commits
- Keep the tone professional but approachable
- Output raw Markdown, no code fences
"""

    try:
        client = OpenAI(base_url=api_base, api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that writes release notes."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"警告: AI 调用失败 ({e})，使用回退模板", file=sys.stderr)
        return generate_notes_fallback(commits, prev_tag, current_tag)


def generate_notes_fallback(
    commits: str,
    prev_tag: str | None,
    current_tag: str,
) -> str:
    """AI 不可用时的回退方案：直接列出提交。"""
    version_range = f"{prev_tag} → {current_tag}" if prev_tag else current_tag

    lines = [
        f"## 版本变更：{version_range}",
        "",
        "### 提交记录",
        "",
    ]
    for line in commits.splitlines():
        if line.strip():
            lines.append(f"- `{line.strip()}`")

    if not commits.strip():
        lines.append("- _无提交记录_")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 AI Release Notes")
    parser.add_argument("--tag", required=True, help="当前版本标签 (如 v0.2.0)")
    parser.add_argument("--output", required=True, help="输出文件路径")
    args = parser.parse_args()

    current_tag = args.tag
    prev_tag = get_previous_tag(current_tag)

    print(f"版本范围: {prev_tag or '(初始)'}...{current_tag}", file=sys.stderr)

    commits = get_commits(prev_tag, current_tag)
    diff_stat = get_diff_stat(prev_tag, current_tag)

    if not commits.strip():
        print("警告: 未找到提交记录", file=sys.stderr)

    notes = generate_notes_ai(commits, diff_stat, prev_tag, current_tag)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(notes, encoding="utf-8")

    print(f"✓ Release Notes 已写入: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
