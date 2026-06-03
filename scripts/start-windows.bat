@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   MyAI Studio - 一键启动脚本
echo ============================================
echo.

cd /d "%~dp0\.."

:: 检查 Python 是否安装
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: 检查 Node.js 是否安装
where node >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)

echo [信息] Python 版本:
python --version
echo [信息] Node.js 版本:
node --version
echo.

:: ========== 后端设置 ==========
echo [步骤 1/4] 检查 Python 虚拟环境...
if not exist "backend\.venv" (
    echo [信息] 创建虚拟环境 backend\.venv ...
    python -m venv backend\.venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [成功] 虚拟环境创建完成
) else (
    echo [信息] 虚拟环境已存在
)

echo.
echo [步骤 2/4] 安装后端依赖...
call backend\.venv\Scripts\activate.bat
pip install -r backend\requirements-windows.txt -q
if errorlevel 1 (
    echo [错误] 安装后端依赖失败
    pause
    exit /b 1
)
echo [成功] 后端依赖安装完成

:: ========== 数据库初始化 ==========
echo.
echo [步骤 3/5] 检查数据库...
cd backend
if not exist "myai_studio.db" (
    echo [信息] 首次启动，正在初始化数据库...
    call alembic upgrade head
    if errorlevel 1 (
        echo [错误] 数据库初始化失败
        cd ..
        pause
        exit /b 1
    )
    echo [成功] 数据库初始化完成
) else (
    echo [信息] 数据库已存在，检查迁移状态...
    call alembic upgrade head >nul 2>&1
    echo [成功] 数据库检查完成
)

:: 检查加密密钥
if not exist ".encryption_key" (
    echo [信息] 加密密钥将在首次启动时自动生成
) else (
    echo [信息] 加密密钥文件已存在
)
cd ..

:: ========== 前端设置 ==========
echo.
echo [步骤 4/5] 安装前端依赖...
cd frontend
if not exist "node_modules" (
    echo [信息] 首次安装，运行 npm install...
    call npm install
    if errorlevel 1 (
        echo [错误] 安装前端依赖失败
        pause
        exit /b 1
    )
) else (
    echo [信息] node_modules 已存在，跳过安装
)
cd ..

echo [成功] 前端依赖检查完成
echo.

:: ========== 启动服务 ==========
echo [步骤 5/5] 启动服务...
echo.
echo   后端: http://localhost:8000
echo   前端: http://localhost:3000
echo   API 文档: http://localhost:8000/docs
echo.
echo ============================================
echo   按 Ctrl+C 停止所有服务
echo ============================================
echo.

:: 使用 start 命令在新窗口中启动后端
start "MyAI Backend" cmd /k "cd /d %~dp0\..\backend && .venv\Scripts\activate.bat && python run.py"

:: 等待后端启动
echo [信息] 等待后端启动...
timeout /t 3 /noblock >nul

:: 在当前窗口启动前端
cd frontend
call npm run dev -- --force

pause
