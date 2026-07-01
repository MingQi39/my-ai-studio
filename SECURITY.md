# 安全与密钥管理

## 仓库里**没有**什么

- 源码中不包含真实 LLM API Key（`sk-...`、OpenRouter 等）
- 不提交 `.env`（仅提供 `backend/.env.example` 占位模板）
- `backend/config/providers.yaml` 只存 **环境变量名**（`api_key_env`），不存 Key 值
- 前端不硬编码用户 Key；运行时通过连接对话框提交给后端

## 运行应用后**本地/服务器**会存什么

| 位置                      | 内容                                                             | 是否进 git                          |
| ------------------------- | ---------------------------------------------------------------- | ----------------------------------- |
| `backend/myai_studio.db`  | 用户、会话、**加密后**的模型 API Key                             | 否 — `*.db` 已 gitignore            |
| `backend/.encryption_key` | 用于加密数据库中 API Key 的 Fernet 密钥                          | 否 — `.encryption_key` 已 gitignore |
| `backend/.env`            | `SECRET_KEY`、`API_KEY_ENCRYPTION_KEY`、各 Provider 可选环境变量 | 否 — `.env` 已 gitignore            |
| 浏览器 `localStorage`     | JWT `auth_token`、用户信息、语言偏好                             | 不适用（仅客户端）                  |

API Key 流转：用户在 UI 输入 → 后端用 `API_KEY_ENCRYPTION_KEY` 或 `.encryption_key` 加密 → 写入 `model_configs.encrypted_api_key`。

## `git push` 之前

1. 复制 `backend/.env.example` → `backend/.env`，并设置足够强的随机值：
   - `SECRET_KEY`（JWT 签名）
   - `API_KEY_ENCRYPTION_KEY`（32 字节 Fernet 密钥；开发环境也可由程序自动生成 `.encryption_key`）
2. 切勿提交：`.env`、`.encryption_key`、`*.db`、`*.sqlite`、`node_modules/`、`.venv/`、`frontend/build/`
3. 若已在本地跑过应用，确保 `backend/myai_studio.db` 与 `backend/.encryption_key` 不会被打包进提交
4. 若曾误提交过密钥，务必在对应平台**轮换/作废**该 Key

## 生产环境检查清单

- `backend/app/config.py` 中的默认 `SECRET_KEY` 只是**兜底**；生产必须通过 `.env` 覆盖
- 生产环境使用 HTTPS；将 `CORS_ORIGINS` 限制为真实前端域名
- 将 `myai_studio.db` 与 `.encryption_key` 视为敏感备份，妥善保管
