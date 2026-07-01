# Docker 部署（云服务器 / 个人自用）

## 架构

```text
浏览器 → Caddy (80/443, 自动 HTTPS)
           ├─ /api/*、/docs → backend (FastAPI)
           └─ 其余路径        → frontend (Nginx 静态)
         backend 数据卷: SQLite + 上传文件
```

## 前置条件

- 云服务器已安装 Docker 与 Docker Compose v2
- 域名已 A 记录指向服务器公网 IP
- 安全组 / 防火墙放行 **80、443**（SSH 按需）

## 快速部署

```bash
# 1. 克隆代码到服务器
git clone <your-repo> my-ai-studio && cd my-ai-studio

# 2. 配置环境变量
cp .env.docker.example .env
nano .env   # 填写 DOMAIN、SECRET_KEY、API_KEY_ENCRYPTION_KEY、CORS_ORIGINS

# 生成加密密钥（本地或服务器均可）
cd backend && python generate_encryption_key.py && cd ..

# 3. 构建并启动
docker compose up -d --build

# 4. 查看状态
docker compose ps
docker compose logs -f backend
```

访问：`https://你的域名`

## 迁移本地已有数据

若本地已跑通过，可把数据拷到容器：

```bash
# 先启动一次
docker compose up -d backend

# 本地 → 容器（在项目根目录执行）
docker compose cp ./backend/myai_studio.db backend:/app/data/myai_studio.db
docker compose cp ./backend/.encryption_key backend:/app/.encryption_key

docker compose restart backend
```

> 若 `.env` 里已设置 `API_KEY_ENCRYPTION_KEY`，须与加密数据库时使用的密钥一致。

## 常用命令

```bash
docker compose up -d --build    # 更新代码后重建
docker compose logs -f          # 查看日志
docker compose down             # 停止（保留数据卷）
docker compose down -v          # 停止并删除数据卷（慎用）
```

## 备份

定期备份 Docker 卷中的：

- `/app/data/myai_studio.db`
- `/app/.encryption_key`（若未用环境变量存密钥）

```bash
docker compose exec backend tar -czf - /app/data/myai_studio.db | gzip > backup-$(date +%F).db.tgz
```

## 仅 IP、无域名（不推荐）

无域名时无法自动签 HTTPS 证书。可临时把 `.env` 中 `DOMAIN` 设为 `:80`，`CORS_ORIGINS` 设为 `http://服务器IP`，并自行承担 HTTP 明文风险。

## 故障排查

| 现象 | 检查 |
|------|------|
| 502 | `docker compose logs backend` 是否迁移失败 |
| 前端能开、API 失败 | Caddy 是否把 `/api` 转到 backend |
| 登录后 Key 无效 | `API_KEY_ENCRYPTION_KEY` 是否与建库时一致 |
| SSE 流式中断 | Caddy 已配置 `flush_interval -1` |
