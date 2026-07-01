# My AI Studio

全栈 AI 聊天工作台：多 Provider LLM 接入、流式对话、会话历史、系统提示词，以及支持 **9 语言 i18n** 的 React 界面（默认英文）。

## 核心亮点

- **国际化 UI** — 英语、简体中文、繁體中文、日本語、한국어、Español、Français、Deutsch、Русский
- **语言切换** — 登录页与侧边栏均可切换，选择保存在 `localStorage`
- **自动检测语言** — 根据 IP 地区与浏览器语言推断（不会覆盖用户手动选择）
- **自带 Key（BYOK）** — 支持 DeepSeek、OpenAI、Gemini、Qwen、OpenRouter、Ollama 等；在连接对话框填写 API Key 与模型 ID
- **FastAPI 后端** — 用户认证、会话管理、SSE 流式聊天、按用户加密存储模型配置
- **现代前端** — React 18、Vite、Tailwind、Radix UI

## 旅行规划 Agent

侧边栏 **「旅行规划 Agent」** 模块提供：

- **LLM / ReAct Agent 对话** — 可切换模式，或使用 **对比模式**（LLM 与 Agent 并排输出）
- **ReAct 过程可视化** — Observe → Think → Act → Verify 时间线
- **默认含美食推荐** — Agent 模式第 1 轮 Observe 自动查天气 + 美食参考，最终行程含每日用餐安排
- **工具台** — 独立测试天气、景点、酒店、交通、美食推荐、计算器等内置工具
- **正式行程导出** — 结构化 JSON / Markdown，含每日活动与用餐项
- **共用模型配置** — 与主聊天工作台使用同一套 BYOK 模型连接

后端路由：`/api/v1/travel/*`（需 JWT 登录）。

### 旅行 Agent 环境变量

| 变量 | 用途 |
|------|------|
| `AMAP_API_KEY` | 天气、景点/酒店 POI、驾车路线 |
| `JUHE_TRAIN_API_KEY` / `JUHE_FLIGHT_API_KEY` | 高铁 / 航班班次 |
| `TAVILY_API_KEY` | 美食推荐（含小红书关键词网页摘要）、交通兜底搜索 |
| `HTTP_TIMEOUT_SECONDS` | 外部 API 超时（默认 `10`） |
| `TAVILY_MAX_RESULTS` | Tavily 每次最多返回条数（默认 `5`） |

## 快速开始

项目支持 **本地开发** 与 **Docker** 两种启动方式，环境变量文件位置不同：

| 方式 | 启动命令 | 环境变量文件 |
|------|----------|--------------|
| 本地开发 | `./scripts/start-macos-linux.sh` | `backend/.env` |
| Docker | `./scripts/docker-deploy.sh` | 项目根目录 `.env` |

`docker-deploy.sh` 会在启动前自动把 `backend/.env` 中缺失的旅行 Agent 配置（`AMAP_*`、`TAVILY_*`、`JUHE_*` 等）合并到根目录 `.env`，**不会覆盖已有值**。本地只维护 `backend/.env` 也可以。

### 本地开发（推荐调试）

```bash
cp backend/.env.example backend/.env   # 填写 API Key
chmod +x scripts/start-macos-linux.sh
./scripts/start-macos-linux.sh
```

启动后访问：

- **前端**：http://localhost:11010
- **后端 API**：http://localhost:10011
- **API 文档**：http://localhost:10011/docs

### Docker（推荐部署 / 本地容器化）

```bash
cp .env.docker.example .env
# 填写 DOMAIN、SECRET_KEY、API_KEY_ENCRYPTION_KEY、CORS_ORIGINS
# 旅行 Agent Key 可写在根 .env，或只写在 backend/.env 由部署脚本自动合并
chmod +x scripts/docker-deploy.sh
./scripts/docker-deploy.sh
```

- **云服务器**：配置真实域名后访问 `https://你的域名`（Caddy 自动 HTTPS），详见 [deploy/README.md](./deploy/README.md)
- **本地 Docker**：`docker-compose.override.yml` 将 Caddy 映射到 **8080**，访问 http://localhost:8080

常用命令：

```bash
docker compose ps          # 查看状态
docker compose logs -f     # 查看日志
docker compose down        # 停止（保留数据卷）
```

### 手动启动

#### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 配置 backend/.env 与数据库迁移后：
uvicorn app.main:app --reload --host 0.0.0.0 --port 10011
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认在 `http://localhost:11010`，API 默认指向同主机 `10011` 端口。

首次登录且尚未保存模型连接时，会自动弹出 **模型连接** 对话框。选择 Provider、填写 API Key、设置模型 ID（如 `deepseek-chat`、`gpt-4o`），测试通过后保存即可。

### 默认语言规则

- 首次访问（无保存偏好）：优先按 **IP 地区**（ipapi.co）选择，失败则用浏览器语言，再失败则英文
- 示例：中国大陆 → `zh-CN`，台港澳 → `zh-TW`，日本 → `ja`，韩国 → `ko`，美英 → `en`
- 点击 **地球图标** 可手动切换；选择会写入 `localStorage`，后续访问优先于 IP 推断

## i18n 结构

| 路径                                           | 作用                                                                |
| ---------------------------------------------- | ------------------------------------------------------------------- |
| `frontend/src/i18n/index.ts`                   | i18next 初始化、语言检测、`setLanguage()`、`bindDocumentLanguage()` |
| `frontend/src/i18n/locales/*.json`             | 各语言翻译文件                                                      |
| `frontend/src/components/LanguageSwitcher.tsx` | 语言切换 UI                                                         |

新增文案：先在 `en.json` 添加 key，再同步到其他语言文件，组件内使用 `const { t } = useTranslation()` 与 `t('section.key')`。

## 开源发布前

本仓库 **不包含** 真实 API Key。本地敏感文件说明见 [SECURITY.md](./SECURITY.md)。

推送前快速自检：

```bash
# 不应输出真实密钥（仅 .env.example 占位符可接受）
rg 'sk-[a-zA-Z0-9]{20,}' --glob '!node_modules' --glob '!.venv' --glob '!frontend/build'

# 以下文件必须保持未跟踪
ls backend/.env backend/.encryption_key backend/*.db .env 2>/dev/null
```

请勿提交：`node_modules/`、`backend/.venv/`、`frontend/build/`、`*.db`、`.encryption_key`、`.env`。
