# 启动脚本说明

本文件夹包含 Qi AI Studio 的一键启动脚本。

## 脚本列表

### 1. `start-windows.bat`
**适用系统**: Windows 10/11

**功能**:
- 自动检查并创建 Python 虚拟环境
- 安装后端依赖（使用 `requirements-windows.txt`）
- 初始化数据库（首次运行）
- 安装前端依赖
- 同时启动后端和前端服务

**使用方法**:
```bash
# 方法 1: 双击运行
双击 start-windows.bat 文件

# 方法 2: 命令行运行
scripts\start-windows.bat
```

---

### 2. `start-macos-linux.sh`
**适用系统**: macOS / Linux

**功能**:
- 自动检查并创建 Python 虚拟环境
- 根据操作系统自动选择依赖文件（macOS 或 Linux）
- 初始化数据库（首次运行）
- 安装前端依赖
- 同时启动后端和前端服务
- 支持 Ctrl+C 优雅停止

**使用方法**:
```bash
# 首次运行需要添加执行权限
chmod +x scripts/start-macos-linux.sh

# 启动服务
./scripts/start-macos-linux.sh
```

---

## 启动后访问

服务启动成功后，可以通过以下地址访问：

- **前端界面**: http://localhost:3000
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **ReDoc 文档**: http://localhost:8000/redoc

## 局域网访问

如需在局域网内其他设备访问，请使用本机 IP 地址：

- 前端: `http://<your-ip>:3000`
- 后端: `http://<your-ip>:8000`

## 停止服务

- **Windows**: 关闭命令行窗口或按 `Ctrl+C`
- **macOS/Linux**: 按 `Ctrl+C` 优雅停止所有服务

## 环境要求

- Python 3.11+
- Node.js 18+
- Redis (可选，用于 Celery 异步任务)

## 故障排除

### 虚拟环境创建失败
确保已安装 Python 3.11+ 并且 `python` 命令可用。

### 依赖安装失败
检查网络连接，或尝试使用国内镜像源：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 端口被占用
如果 8000 或 3000 端口被占用，请先停止占用端口的程序。

### 数据库初始化失败
删除 `backend/myai_studio.db` 文件后重新运行脚本。
