# Spider HTTP→Playwright 分层升级设计规格

**日期**：2026-07-14  
**状态**：已定稿（待实现）  
**模块代号**：`spider` / `browser-escalation`  
**关联**：[`2026-07-14-spider-pipeline-todos-hybrid-design.md`](./2026-07-14-spider-pipeline-todos-hybrid-design.md)

---

## 1. 背景与目标

爬虫 Pipeline 当前以宿主 `aiohttp` 抓取 + 沙箱内 `requests + BeautifulSoup` 执行为主。反爬能力停在「HTML 关键字检测 + 建议塞进 LLM prompt + 失败卡片 hints」。`fetch_url` 的 `use_selenium` 仅为占位；强 JS 渲染 / Cloudflare 挑战类站点会表现为抓取失败或零数据。

产品选择路线 **「浏览器跃迁包」**：在现有 Docker 沙箱内按需启用 Playwright，默认仍走便宜的 HTTP 路径。

### 1.1 成功标准

- **静态列表页**：行为与现状基本一致（HTTP 分析 + requests 脚本），不明显拖慢。
- **需渲染页面**：判定为 `js_render`，或 HTTP soft 失败触发升级后：
  - 分析阶段在沙箱内用 Playwright 拿到渲染后 HTML，写入 `source_page.html`；
  - 代码生成产出 **Playwright** 同步脚本（非 requests）；
  - 执行阶段在同一沙箱镜像内跑该脚本，产出 `scraped_data.json`。
- **诊断**：反爬分级 `none | soft | hard | js_render` 写入 `analysis_report.json`，失败卡片有对应 error code / hints。
- **hard / CAPTCHA**：不自动硬破；清晰失败并提示用户换 URL 或稍后再试。
- 镜像未就绪时：升级路径给出可操作错误（提示配置 Playwright 镜像），不静默回落成「空爬取」误导。

### 1.2 非目标

- Cookie 注入、代理池、打码、cloudscraper 专项硬破。
- 独立 browser worker 服务。
- 默认每次请求都开浏览器。
- DeepAgent 路径完整对齐浏览器升级（本版 **必达 Pipeline**；DeepAgent 仅可复用分类函数，UI/流式升级可选后置）。
- 修改 Todo 四阶段语义（仍是 analyze → codegen → execute → clean）。

### 1.3 已确认产品决策

| 项 | 选择 |
|---|---|
| 总路线 | L0 诊断 + L1 精简（仅会话/延迟等可随 Playwright 模板附带）+ L2 按需 Playwright |
| 浏览器运行位置 | **现有 Docker 沙箱**（扩展 `SPIDER_DOCKER_IMAGE`） |
| 升级范围 | **分析 + 执行** 一并升级（避免分析过了执行再被挡） |
| 触发策略 | HTTP 先试，命中条件后升级 |
| Cookie / 代理 | **本版不做** |
| DeepAgent | 非必达 |

---

## 2. 反爬分级与升级触发

### 2.1 级别定义

扩展 `detect_anti_scraping`（或抽 `classify_fetch_result`）返回统一结构：

```json
{
  "level": "none | soft | hard | js_render",
  "detected_mechanisms": ["..."],
  "recommendations": ["..."],
  "escalate_to_browser": false,
  "block_hard": false,
  "success": true
}
```

| level | 含义 | 后续动作 |
|---|---|---|
| `none` | 正常 HTML 列表/内容页特征 | HTTP + requests 路径 |
| `soft` | 轻度限流/空壳怀疑，但仍可能有可用 HTML | 先继续 HTTP 路径；若后续 fetch 失败或执行空数据，再升级（见 §2.2） |
| `js_render` | 大量 script、正文极少；或明确 SPA/挑战前壳页 | **立即** `escalate_to_browser=true` |
| `hard` | CAPTCHA / reCAPTCHA / 明确人机验证文案；或持续 Cloudflare 挑战页且浏览器也无解（事后） | `block_hard=true`，不进入「指望自动过验证」路径 |

启发式（首版可迭代，但契约固定）：

- HTML 含 `cloudflare` 且含挑战/等待关键字 → `js_render`（允许浏览器升级一次）；浏览器后仍为挑战页 → 再标 `hard` 并失败。
- `captcha` / `recaptcha` / `验证码` → `hard`（不升级硬破）。
- `script` 多且可见文本 &lt; 阈值（沿用现状 ~500）→ `js_render`。
- HTTP 状态 `403`/`429`/`503`：分级函数接收 `status_code`；无 CAPTCHA 正文时标 `soft` 并按 §2.2 尝试 Playwright 一次；明确人机验证正文则 `hard`。

### 2.2 升级触发条件（Pipeline）

满足任一即进入浏览器模式（`fetch_mode = "playwright"`），且后续 codegen/execute 绑定该模式：

1. 分类结果 `escalate_to_browser == true`（典型：`js_render`）。
2. 宿主 HTTP `fetch_url` **失败**（网络/4xx/5xx），且未判定为 `hard` 阻断 → 尝试沙箱 Playwright 再抓一次（一次）。
3. HTTP 成功且未立即升级，但沙箱 **requests 执行** 无有效数据（`empty_scrape`），且分类曾为 `soft` 或 `js_render` 可疑 → **同一轮 Pipeline 内** 升级：浏览器重抓 → 重生成 Playwright 代码 → 再执行（最多一轮升级，禁止无限循环）。

不满足时保持 `fetch_mode = "http"`。

`hard` / `block_hard`：直接失败事件，hints 明确「需要人工验证 / 请换更开放列表页」，不升级硬破。

### 2.3 错误码（L0）

| code | 场景 |
|---|---|
| `fetch_failed` | HTTP 与（若尝试）Playwright 均失败 |
| `anti_scrape_hard` | CAPTCHA / 验证墙 |
| `browser_image_unavailable` | 需升级但镜像无 Playwright/Chromium |
| `browser_fetch_failed` | 沙箱 Playwright 抓取失败 |
| `empty_scrape` | 升级后仍无数据（保留现有语义） |
| `execution_failed` | 脚本执行非空数据类失败 |

失败卡片 `hints` 按 code 定制，替换泛化「若网站有强反爬…」单一文案。

---

## 3. 架构与数据流

```text
Pipeline(web_analyzer)
  ├─ host fetch_url (aiohttp) → 可选 source_page.html（或仅内存预览）
  ├─ classify → anti report
  ├─ if hard → error anti_scrape_hard → stop
  ├─ if escalate:
  │     sandbox playwright_fetch.py → write source_page.html
  │     （写 meta: fetch_mode=playwright, scrape_engine=playwright）
  └─ else:
        现有 analyze_html_structure on HTTP HTML
        meta: fetch_mode=http, scrape_engine=requests

code_generator
  ├─ scrape_engine=requests → 现有 LLM + fallback BS 模板
  └─ scrape_engine=playwright → Playwright system prompt + Playwright fallback 模板

debug_agent
  └─ 沙箱执行 spider.py（引擎与 meta 一致）

（可选同轮）empty_scrape + soft 可疑
  → 置 scrape_engine=playwright，重走 fetch+codegen+execute 一轮
```

工作区元数据建议写入 `source_page.meta.json` / `analysis_report.json`：

```json
{
  "url": "...",
  "fetch_mode": "http | playwright",
  "scrape_engine": "requests | playwright",
  "anti_level": "none | soft | hard | js_render",
  "escalation_reason": null
}
```

UI 可选：在 web_analyzer 阶段预览中展示「已升级为浏览器抓取」状态文案（非必须；有则更好）。

---

## 4. Docker / 沙箱

### 4.1 镜像

- 配置项仍用 `SPIDER_DOCKER_IMAGE`（默认可保持 `python:3.11-slim` 以兼容纯 HTTP 工作流）。
- 文档与 `.env.example` 增加推荐镜像示例，例如官方 `mcr.microsoft.com/playwright/python:v1.xx-jammy`（实现时锁定具体 tag），或项目自建 `Dockerfile.spider`（python + playwright + deps）。
- **浏览器升级路径**启动前探针：在容器内执行 `python -c "from playwright.sync_api import sync_playwright"`（或等价）。失败 → `browser_image_unavailable`。
- 内存：升级启用时建议 `SPIDER_DOCKER_MEMORY_LIMIT` ≥ `2g`（配置注释说明；不强制改默认破坏现有机器，但文档标明 Playwright 最低建议）。

### 4.2 沙箱内 Playwright 抓取

新增内部辅助（非必须暴露为用户 LangChain tool，Pipeline 可直接调）：

- 文件：`playwright_fetch.py`（写入 workspace 或镜像内置脚本）。
- 行为：headless Chromium → `goto(url, wait_until=domcontentloaded|networkidle 可配置)` → 超时上限（建议 30–45s）→ 写出 `source_page.html` + 更新 meta。
- 禁止无头以外模式；禁止下载额外浏览器（镜像预制）。

宿主 `fetch_url` 的 `use_selenium` 参数：本版改为明确文档「deprecated / unused」；浏览器能力走沙箱，不在后端进程装 Chromium。

### 4.3 网络与安全

- 保持沙箱 `network_disabled=False`（爬取需要出网）；不新开特权。
- 不因本功能关闭现有 CPU/内存配额；可仅在文档中提示 Playwright 更吃内存。

---

## 5. 代码生成与 Fallback 模板

### 5.1 `scrape_engine=requests`（不变为主路径）

- 现有 `_generate_spider_code` / `_fallback_spider_code` 保留。
- 继续强制：同步、`requests`+`BeautifulSoup`、`scraped_data.json`、非空 `title`+`url`。

### 5.2 `scrape_engine=playwright`（新增）

LLM system 约束：

- 只用 **同步** Playwright（`sync_playwright`），禁止 asyncio。
- 入口仍 `def main() -> int` + `SystemExit`。
- `TARGET_URL` 禁止改写。
- 写出 `scraped_data.json`（0 条也写 `[]`）；有数据 exit 0，无数据 exit 1。
- 每条记录非空 `title` + `url`（与现规则一致）。
- 合理 `user_agent`、短延迟；超时显式设置。
- 不得依赖用户本机 Chrome 路径（使用 Playwright 自带 browser）。

新增 `_fallback_playwright_spider_code(target_url, limit)`：确定性模板，选择器启发式可复用 BS 模板思路（先 `page.content()` 再 BeautifulSoup 解析，降低 LLM 不稳风险——**允许 Playwright 只负责渲染，解析仍可用 BS**）。该组合视为合规 Playwright 引擎路径。

校验：语法 AST 通过即可；不在宿主机 import playwright（沙箱才有）。

### 5.3 执行重试

`_execute_spider_with_retry`：

- `scrape_engine=requests`：保留「LLM 失败 → fallback BS 模板」。
- `scrape_engine=playwright`：LLM 失败 → fallback Playwright 模板；**不得**静默退回纯 requests（会违背升级语义）。若 Playwright 镜像不可用，应在执行前已失败为 `browser_image_unavailable`。

---

## 6. Pipeline 阶段改动要点

文件焦点（实现时）：

- `tools.py`：分级输出契约；fetch 带上 status。
- `spider_pipeline_service.py`：升级状态机；错误码；按引擎分流 codegen/execute。
- `sandbox.py` / 配置：镜像文档、可选探针 helper。
- `agent_builder.py`：DeepAgent `code_generator` prompt 可日后跟引擎，但本版非必达。
- 前端：错误码 hints 映射（若今日 hints 完全后端下发则可零改或极小改）。

Todo 四步文案可不改；可选在 stage detail 中注明 `fetch_mode`。

---

## 7. 测试计划

| 测试 | 期望 |
|---|---|
| 单元：classify 纯 HTML 列表 | `none`，不升级 |
| 单元：script 壳 + 短文本 | `js_render`，`escalate_to_browser=true` |
| 单元：captcha 关键字 | `hard`，`block_hard=true` |
| 单元：fallback Playwright 模板 AST 可解析 | 通过 |
| Pipeline mock：HTTP 成功 + none | 不调 sandbox playwright_fetch |
| Pipeline mock：js_render | 调 playwright_fetch；codegen 使用 playwright 约束 |
| Pipeline mock：需升级但探针失败 | `browser_image_unavailable` |
| 集成（可选，需 Docker 镜像）：对公开静态页 HTTP；对简单动态页 Playwright | 有 `scraped_data.json` |

不把「打过真实 Cloudflare 生产站」列为 CI 必过。

---

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 镜像体积 / 拉取慢 | 文档推荐预拉；默认 slim 不强制所有用户装浏览器 |
| 内存 OOM | 文档 ≥2g；失败时错误可读 |
| 同轮二次升级拖时长 | 硬性「最多一轮升级」 |
| LLM 乱写 Playwright | 强约束 + fallback 模板（content+BS） |
| 合规 | 不提供打码/代理；hard 明确放弃 |

---

## 9. 后续（明确不在本版）

- Cookie / 代理（原 L1 可选 B/C）。
- DeepAgent 全路径引擎对齐。
- 用户手动「强制浏览器」开关。
- 独立 browser worker。

---

## 10. 实现顺序建议

1. 分级契约 + 错误码 + 单测（L0，可独立合并）。
2. 沙箱探针 + `playwright_fetch` + 镜像文档。
3. Pipeline 状态机（升级触发）+ Playwright codegen/fallback。
4. 同轮 soft→升级重试（可选与 3 同 PR 或紧随）。
5. 前端 hints（若需要）与手动验证清单。
