#!/usr/bin/env bash
# scripts/release.sh — 版本发布脚本
# 用法: ./scripts/release.sh [patch|minor|major|X.Y.Z]
#
# 功能:
#   1. 读取 VERSION 文件中的当前版本号
#   2. 按参数计算新版本号（patch/minor/major 或直接指定 X.Y.Z）
#   3. 同步更新 VERSION 和 backend/pyproject.toml
#   4. 提交变更并创建 vX.Y.Z 标签
#   5. 推送到远端（推送标签自动触发 docker-images.yml 构建 + 发布）

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION_FILE="$REPO_ROOT/VERSION"
PYPROJECT="$REPO_ROOT/backend/pyproject.toml"
REMOTE="${RELEASE_REMOTE:-$(git remote | head -1)}"

# ── 颜色输出 ─────────────────────────────────────────
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
cyan()  { printf '\033[36m%s\033[0m\n' "$*"; }

# ── 版本计算 ──────────────────────────────────────────
if [[ $# -lt 1 ]]; then
  echo "用法: $0 [patch|minor|major|X.Y.Z]"
  echo "当前版本: $(cat "$VERSION_FILE")"
  exit 1
fi

CURRENT=$(cat "$VERSION_FILE" | tr -d '[:space:]')

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

case "$1" in
  patch) PATCH=$((PATCH + 1)) ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  [0-9]*.[0-9]*.[0-9]*)
    IFS='.' read -r MAJOR MINOR PATCH <<< "$1"
    ;;
  *)
    red "错误: 参数必须是 patch|minor|major 或 X.Y.Z 格式"
    exit 1
    ;;
esac

NEW_VERSION="${MAJOR}.${MINOR}.${PATCH}"

if [[ "$NEW_VERSION" == "$CURRENT" ]]; then
  red "错误: 新版本号 $NEW_VERSION 与当前版本号相同"
  exit 1
fi

# ── 预检查 ────────────────────────────────────────────
cd "$REPO_ROOT"

if [[ -n "$(git status --porcelain)" ]]; then
  red "错误: 工作区有未提交的变更，请先 git commit 或 git stash"
  exit 1
fi

EXISTING_TAG="v${NEW_VERSION}"
if git rev-parse "$EXISTING_TAG" >/dev/null 2>&1; then
  red "错误: 标签 $EXISTING_TAG 已存在"
  exit 1
fi

# ── 更新版本号 ────────────────────────────────────────
cyan "当前版本: $CURRENT → 新版本: $NEW_VERSION"

echo "$NEW_VERSION" > "$VERSION_FILE"
cyan "✓ 已更新 VERSION"

# 更新 backend/pyproject.toml
if command -v sed >/dev/null 2>&1; then
  sed -i.bak "s/^version = \"[^\"]*\"/version = \"${NEW_VERSION}\"/" "$PYPROJECT"
  rm -f "${PYPROJECT}.bak"
else
  red "错误: 需要 sed 命令"
  exit 1
fi
cyan "✓ 已更新 backend/pyproject.toml"

# ── 提交 & 打标签 ─────────────────────────────────────
git add "$VERSION_FILE" "$PYPROJECT"
git commit -m "release: v${NEW_VERSION}"
git tag -a "v${NEW_VERSION}" -m "Release v${NEW_VERSION}"

green "✓ 已提交并创建标签 v${NEW_VERSION}"

# ── 推送 ─────────────────────────────────────────────
printf '%s' "是否推送到远端 ${REMOTE}？[Y/n] "
CONFIRM="Y"
read -r CONFIRM || true
CONFIRM="${CONFIRM:-Y}"

if [[ "$CONFIRM" =~ ^[Yy] ]]; then
  git push "$REMOTE" HEAD
  git push "$REMOTE" "v${NEW_VERSION}"
  green "✓ 已推送提交和标签到 $REMOTE"
  echo ""
  green "GitHub Actions 将自动构建 Docker 镜像并发布 Release。"
  green "查看进度: https://github.com/yzxingtu/novusai-saas/actions"
else
  cyan "跳过推送。稍后可手动执行:"
  echo "  git push $REMOTE HEAD"
  echo "  git push $REMOTE v${NEW_VERSION}"
fi
