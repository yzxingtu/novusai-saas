#!/usr/bin/env bash
# scripts/release.sh — 版本发布脚本（适配受保护分支）
# 用法: ./scripts/release.sh [patch|minor|major|X.Y.Z]
#
# 功能:
#   1. 读取 VERSION 文件中的当前版本号
#   2. 按参数计算新版本号（patch/minor/major 或直接指定 X.Y.Z）
#   3. 同步更新 VERSION 和 backend/pyproject.toml
#   4. 创建 release/vX.Y.Z 分支并提交版本变更
#   5. 通过 GitHub CLI 创建 Release PR
#   6. PR 合并到 main 后，CI (auto-tag-release.yml) 自动打标签
#      → 标签推送触发 docker-images.yml 构建镜像 + GitHub Release

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

# ── 创建 Release 分支并提交 ─────────────────────────
RELEASE_BRANCH="release/v${NEW_VERSION}"

# 检查远端是否已存在同名分支
if git ls-remote --exit-code --heads "$REMOTE" "$RELEASE_BRANCH" >/dev/null 2>&1; then
  red "错误: 远端分支 $RELEASE_BRANCH 已存在，请先删除或手动处理"
  exit 1
fi

cyan "当前版本: $CURRENT → 新版本: $NEW_VERSION"

git switch -c "$RELEASE_BRANCH"
cyan "✓ 已创建分支 $RELEASE_BRANCH"

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

git add "$VERSION_FILE" "$PYPROJECT"
git commit -m "release: v${NEW_VERSION}"

green "✓ 已提交版本变更"

# ── 推送分支 & 创建 PR ──────────────────────────────
printf '%s' "是否推送分支并创建 Release PR？[Y/n] "
CONFIRM="Y"
read -r CONFIRM || true
CONFIRM="${CONFIRM:-Y}"

if [[ "$CONFIRM" =~ ^[Yy] ]]; then
  git push -u "$REMOTE" "$RELEASE_BRANCH"
  green "✓ 已推送分支 $RELEASE_BRANCH 到 $REMOTE"

  # 通过 GitHub CLI 创建 Release PR
  if command -v gh >/dev/null 2>&1; then
    # 确保 release 标签存在
    gh label create release --description "版本发布 PR" --color "0075ca" 2>/dev/null || true

    PR_URL=$(gh pr create \
      --title "release: v${NEW_VERSION}" \
      --body "## Release v${NEW_VERSION}

版本变更：\`$CURRENT\` → \`$NEW_VERSION\`

### 变更文件
- \`VERSION\`
- \`backend/pyproject.toml\`

### 合并后自动流程
1. \`auto-tag-release.yml\` 检测 VERSION 变更 → 创建标签 \`v${NEW_VERSION}\`
2. \`docker-images.yml\` 被触发 → 构建 Docker 镜像 + 推送 GHCR
3. 自动生成 GitHub Release（含 AI Release Notes）" \
      --base main \
      --head "$RELEASE_BRANCH" \
      --label "release" 2>&1) || {
      red "⚠ gh pr create 失败，请手动创建 PR:"
      echo "  https://github.com/yzxingtu/novusai-saas/compare/main...$RELEASE_BRANCH"
    }

    if [[ "$PR_URL" == http* ]]; then
      green "✓ 已创建 Release PR: $PR_URL"
    fi
  else
    cyan "未安装 GitHub CLI，请手动创建 PR:"
    echo "  https://github.com/yzxingtu/novusai-saas/compare/main...$RELEASE_BRANCH"
  fi

  echo ""
  green "后续流程（PR 合并后自动执行）："
  green "  1. auto-tag-release.yml 检测 VERSION 变更 → 打标签 v${NEW_VERSION}"
  green "  2. docker-images.yml 触发 → 构建镜像 + GitHub Release"
  green "查看进度: https://github.com/yzxingtu/novusai-saas/actions"
else
  cyan "跳过推送。分支已创建在本地，稍后可手动推送:"
  echo "  git push -u $REMOTE $RELEASE_BRANCH"
  echo "  gh pr create --base main --head $RELEASE_BRANCH --title 'release: v${NEW_VERSION}'"
fi
