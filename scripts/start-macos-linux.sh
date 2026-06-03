#!/bin/bash

# ============================================
#   MyAI Studio - 一键启动脚本
#   适用于 macOS 和 Linux
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "============================================"
echo "  MyAI Studio - 一键启动脚本"
echo "============================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[错误] 未找到 Python3，请先安装 Python 3.10+${NC}"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}[错误] 未找到 Node.js，请先安装 Node.js 18+${NC}"
    exit 1
fi

echo -e "${BLUE}[信息] Python 版本:${NC}"
python3 --version
echo -e "${BLUE}[信息] Node.js 版本:${NC}"
node --version
echo ""

# ========== 后端设置 ==========
echo -e "${YELLOW}[步骤 1/5] 检查 Python 虚拟环境...${NC}"
if [ ! -d "backend/.venv" ]; then
    echo -e "${BLUE}[信息] 创建虚拟环境 backend/.venv ...${NC}"
    python3 -m venv backend/.venv
    echo -e "${GREEN}[成功] 虚拟环境创建完成${NC}"
else
    echo -e "${BLUE}[信息] 虚拟环境已存在${NC}"
fi

echo ""
echo -e "${YELLOW}[步骤 2/5] 安装后端依赖...${NC}"
source backend/.venv/bin/activate

# 根据操作系统选择 requirements 文件
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    REQUIREMENTS_FILE="backend/requirements-macos.txt"
else
    # Linux
    REQUIREMENTS_FILE="backend/requirements-linux.txt"
fi

# 如果特定平台的 requirements 文件不存在，使用通用的
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    REQUIREMENTS_FILE="backend/requirements.txt"
fi

pip install -r "$REQUIREMENTS_FILE" -q
echo -e "${GREEN}[成功] 后端依赖安装完成${NC}"

# ========== 数据库初始化 ==========
echo ""
echo -e "${YELLOW}[步骤 3/5] 检查数据库...${NC}"
cd backend
if [ ! -f "myai_studio.db" ]; then
    echo -e "${BLUE}[信息] 首次启动，正在初始化数据库...${NC}"
    alembic upgrade head
    echo -e "${GREEN}[成功] 数据库初始化完成${NC}"
else
    echo -e "${BLUE}[信息] 数据库已存在，检查迁移状态...${NC}"
    alembic upgrade head > /dev/null 2>&1 || true
    echo -e "${GREEN}[成功] 数据库检查完成${NC}"
fi

# 检查加密密钥
if [ ! -f ".encryption_key" ]; then
    echo -e "${BLUE}[信息] 加密密钥将在首次启动时自动生成${NC}"
else
    echo -e "${BLUE}[信息] 加密密钥文件已存在${NC}"
fi
cd ..

# ========== 前端设置 ==========
echo ""
echo -e "${YELLOW}[步骤 4/5] 安装前端依赖...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    echo -e "${BLUE}[信息] 首次安装，运行 npm install...${NC}"
    npm install
else
    echo -e "${BLUE}[信息] node_modules 已存在，跳过安装${NC}"
fi
cd ..

echo -e "${GREEN}[成功] 前端依赖检查完成${NC}"
echo ""

# ========== 启动服务 ==========
echo -e "${YELLOW}[步骤 5/5] 启动服务...${NC}"
echo ""
echo "  后端: http://localhost:10011 | http://192.168.110.131:10011"
echo "  前端: http://localhost:11010 | http://192.168.110.131:11010"
echo "  API 文档: http://localhost:10011/docs"
echo ""
echo "============================================"
echo "  按 Ctrl+C 停止所有服务"
echo "============================================"
echo ""

# 存储后台进程 PID
BACKEND_PID=""

# 清理函数
cleanup() {
    echo ""
    echo -e "${YELLOW}[信息] 正在停止服务...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}[成功] 服务已停止${NC}"
    exit 0
}

# 捕获 Ctrl+C
trap cleanup SIGINT SIGTERM

# 启动后端（后台运行）
echo -e "${BLUE}[信息] 启动后端服务...${NC}"
cd backend
source .venv/bin/activate
python run.py &
BACKEND_PID=$!
cd ..

# 等待后端启动
echo -e "${BLUE}[信息] 等待后端启动...${NC}"
sleep 3

# 启动前端（前台运行）
echo -e "${BLUE}[信息] 启动前端服务...${NC}"
cd frontend
npm run dev -- --force

# 如果前端退出，清理后端
cleanup
