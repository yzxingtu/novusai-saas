#!/bin/bash
# ============================================
# NovusAI SaaS - 后端开发服务器启动脚本
# ============================================

set -e

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"

echo "🚀 启动 NovusAI SaaS 后端服务..."
echo "📁 项目目录: $BACKEND_DIR"

# 进入后端目录
cd "$BACKEND_DIR"

# 检查虚拟环境是否存在
if [ ! -d ".venv" ]; then
    echo "❌ 虚拟环境不存在，请先运行: python -m venv .venv && pip install -r requirements.txt"
    exit 1
fi

# 激活虚拟环境
source .venv/bin/activate

echo "✅ 虚拟环境已激活: $(which python)"

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  .env 文件不存在，使用默认配置"
fi

# 启动 uvicorn
echo "🔧 启动 uvicorn 开发服务器..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 \
    --reload-dir app
