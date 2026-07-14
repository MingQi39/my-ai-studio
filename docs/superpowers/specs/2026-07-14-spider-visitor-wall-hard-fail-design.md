# Spider 访客墙硬失败补丁设计

**日期**：2026-07-14  
**状态**：已定稿（待实现）  
**模块代号**：`spider` / `visitor-wall-hard-fail`  
**母规格**：[`2026-07-14-spider-browser-escalation-design.md`](./2026-07-14-spider-browser-escalation-design.md) §2.1 / §2.3 / §2.4

---

## 1. 目标

- 检测到访客系统 / 登录墙时，分析阶段即 `anti_scrape_hard` 失败，**不**升级 Playwright、不 codegen、不执行。
- 修复「脚本写出 0 条且 exit≠0」被标成 `execution_failed`（提示换模型）的误分类，改为 `empty_scrape`。

## 2. 实现要点

| 位置 | 变更 |
|---|---|
| `anti_scrape.classify_fetch_result` | 在 CAPTCHA 分支附近（`js_render` 之前）识别访客/登录墙 → `hard` |
| `anti_scrape._ERROR_HINTS["anti_scrape_hard"]` | 补充登录态 / 换公开列表页文案 |
| `spider_pipeline_service` 空数据判定 | `saved 0 records` / 0 条记录 → `empty_scrape` |
| 测试 | 微博访客页 HTML / visitor URL；exit=1 + 0 条 → `empty_scrape` |

## 3. 非目标

- Cookie / 登录态注入
- 新 error code（复用 `anti_scrape_hard`）
- DeepAgent 路径专项对齐（可共享 classify）

## 4. 验收

- `https://www.weibo.com/` 类访客页：流水线停在分析或首轮 classify 之后，错误码 `anti_scrape_hard`，hints 不含「换官方 API 模型」。
- 普通静态列表页 / CAPTCHA / Cloudflare 既有用例行为不变。
- 沙箱执行 `saved 0 records` 且 exit=1：失败卡片为 `empty_scrape` 语义（未能爬取到有效数据），非执行崩溃提示。
