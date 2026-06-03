#!/usr/bin/env pwsh
# 一键部署脚本 (Windows PowerShell)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  我的 AI Studio - 首次部署向导" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查 Python
Write-Host "📦 检查 Python 环境..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ 未找到 Python，请先安装 Python 3.11+" -ForegroundColor Red
    exit 1
}

# 2. 检查虚拟环境
Write-Host ""
Write-Host "📦 检查虚拟环境..." -ForegroundColor Yellow
if (Test-Path ".venv") {
    Write-Host "✅ 虚拟环境已存在" -ForegroundColor Green
} else {
    Write-Host "⚠️  未找到虚拟环境，正在创建..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "✅ 虚拟环境创建成功" -ForegroundColor Green
}

# 3. 激活虚拟环境并安装依赖
Write-Host ""
Write-Host "📦 安装依赖..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet
Write-Host "✅ 依赖安装完成" -ForegroundColor Green

# 4. 运行数据库迁移
Write-Host ""
Write-Host "🗄️  初始化数据库..." -ForegroundColor Yellow
if (Test-Path "myai_studio.db") {
    Write-Host "⚠️  数据库已存在，跳过初始化" -ForegroundColor Yellow
} else {
    alembic upgrade head
    Write-Host "✅ 数据库初始化完成" -ForegroundColor Green
}

# 5. 检查加密密钥
Write-Host ""
Write-Host "🔐 检查加密密钥..." -ForegroundColor Yellow
if (Test-Path ".encryption_key") {
    Write-Host "✅ 加密密钥文件已存在" -ForegroundColor Green
} else {
    Write-Host "ℹ️  加密密钥将在首次启动时自动生成" -ForegroundColor Cyan
}

# 完成
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "  ✅ 部署完成！" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步操作：" -ForegroundColor Yellow
Write-Host "  1. 运行: python run.py" -ForegroundColor White
Write-Host "  2. 访问后端 API: http://localhost:8000" -ForegroundColor White
Write-Host "  3. 查看 API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  注意事项：" -ForegroundColor Yellow
Write-Host "  - 首次启动会自动生成加密密钥文件 .encryption_key" -ForegroundColor White
Write-Host "  - 请妥善保管该文件，丢失后需要重新配置所有 API 密钥" -ForegroundColor White
Write-Host "  - 生产环境建议使用环境变量 API_KEY_ENCRYPTION_KEY" -ForegroundColor White
Write-Host ""
