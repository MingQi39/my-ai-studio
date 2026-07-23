# 面试训练：语音口述交卷（模拟 AI 面试 · 一期）设计规格

**日期**：2026-07-22  
**状态**：已定稿并实施中  
**模块**：Interview Navigator · Training  
**路径选择**：方案 2（MediaRecorder + 后端 STT）+ 阿里云百炼 Paraformer  
**关联**：在现有训练闭环上增加口述入口；不改变评估 / Attempt / 复习卡语义

---

## 1. 背景与目标

面试训练页当前答题区为纯文本 `textarea`：用户看题 → 打字 → 提交 → 断点反馈。仓库内无语音识别能力。用户希望一期先做成「模拟 AI 面试」的口述答辩体验：说完即交卷；多轮连续追问留二期。

### 1.1 本规格范围（一期）

- 现有「当前练习」答题区增加语音口述入口
- 交互：点开始录音 → 再点结束 → 后端转写 → **自动走现有提交答案**
- 中文为主
- Web + Electron 共用同一套前端录音逻辑
- STT：阿里云百炼 Paraformer（后端持 Key）
- 题目仍为文字展示（一期不做 TTS 读题）

### 1.2 明确不在本规格

- AI 朗读题目（TTS）
- 多轮连续口语对话 / 追问 / 打断（二期「口语面试」模式）
- 改评估算法、Attempt 状态机、复习卡生命周期
- 音频落库或长期存储
- 英文主识别（可后续加 `language_hints`）
- 自建本地 Whisper

### 1.3 成功标准

1. 用户点结束口述后，转写文本进入答题框并自动调用与打字相同的提交链路，评估结果一致。
2. 无麦克风权限、无 `DASHSCOPE_API_KEY`、转写失败时不崩溃；仍可打字提交。
3. 未使用语音时不产生 STT 费用（按量计费、闲置为零）。

---

## 2. 产品交互

### 2.1 主路径

1. 用户看到文字题干与焦点节点说明（现有 UI）。
2. 点击「开始口述」→ 请求麦克风权限 → 进入 `recording`（显示已录时长）。
3. 点击「结束并提交」→ 进入 `transcribing` → 上传音频 → 获得文本。
4. 文本写入 `answer` 状态 → 自动调用现有 `submitAnswer()`（v1 或 v2 与当前可提交态一致）。
5. 进入现有评估 / 断点 / 提示流程。

### 2.2 并存规则

- 打字与语音并存；语音成功后覆盖当前答题框内容再提交。
- Attempt 已 `committed` / `abandoned` 时禁用录音（与 textarea 一致）。
- `busy` 为 submitting / hinting / committing 时禁止开始新录音。

### 2.3 失败路径

| 情况 | 行为 |
| --- | --- |
| 麦克风拒绝 / 浏览器不支持 | 提示无法使用麦克风；可继续打字 |
| 空音频 / 转写为空 | 不提交；提示再说一次 |
| 转写超时 / Paraformer 失败 | Toast + 可重试；不自动交空答案 |
| 未配置 Key | 麦克风按钮禁用 + 简短说明 |
| 转写成功但评估提交失败 | 文本保留在答题框；用户可手动再点「提交」 |

### 2.4 录音约束

- 单次上限 **5 分钟**：到时自动停止并进入转写（与「结束并提交」相同）。
- 录音中可「取消」：丢弃音频，回到 idle，不上传、不提交。
- 音频仅用于当次转写，**不落库**；落库的仍是文本答案（现有 Attempt.answers）。

---

## 3. 架构与数据流

```text
[InterviewPage / VoiceAnswerButton]
   │  MediaRecorder → Blob (webm/ogg 等)
   ▼
POST /api/v1/interview/transcribe   (multipart: file)
   │  后端 DASHSCOPE_API_KEY
   │  → Paraformer realtime（本地音频字节流，无需公网 file URL）
   ▼
{ "text": "…" }
   │
   ▼
setAnswer(text) → 现有
POST /api/v1/interview/training/attempts/{id}/answers
```

### 3.1 为何用 realtime 而非「录音文件异步转写」

百炼「录音文件识别」通常要求**公网可访问的 file URL**（或 OSS），短答口述场景会引入临时上传/OSS。一期改为后端收到 multipart 后，用 **Paraformer realtime（WebSocket / DashScope Recognition SDK）** 把本地字节流推给识别服务，适合 1–5 分钟短音频，且无需公网 URL。

计费仍按音频时长按量；不用不收费。

### 3.2 模块拆分

| 单元 | 职责 | 依赖 |
| --- | --- | --- |
| `VoiceAnswerButton`（前端） | 权限、状态机 idle/recording/transcribing、时长展示、触发上传 | `getUserMedia` / `MediaRecorder` |
| `api.transcribeInterviewAudio` | multipart 上传 | 现有 auth fetch |
| `interview/transcribe.py`（后端） | 调 Paraformer，归一化文本与错误 | DashScope SDK 或 WebSocket 客户端 |
| `POST .../interview/transcribe` | HTTP 边界、鉴权、文件大小限制 | FastAPI |
| 现有 `submit_answer` | 不变 | — |

### 3.3 API 草图

**请求**

- `POST /api/v1/interview/transcribe`
- Auth：与现有 interview 路由相同（登录用户）
- Body：`multipart/form-data`，字段 `file`（audio/*）
- 可选：`language=zh`（一期默认中文）

**响应 200**

```json
{ "text": "转写后的纯文本" }
```

**错误**

- `400`：空文件 / 不支持格式 / 超时长或超大小
- `503`：未配置 `DASHSCOPE_API_KEY`
- `502`：上游 Paraformer 失败（message 可对用户脱敏）

### 3.4 配置

- `DASHSCOPE_API_KEY`：百炼 API Key（若已有通义/百炼同一工作空间 Key，可复用）
- `INTERVIEW_STT_MODEL`：默认 `paraformer-realtime-v2`
- 未配置 Key → 前端禁用口述按钮

---

## 4. 前端状态机

```text
idle ──start──► recording ──stop──► transcribing ──ok──► idle
                  │                    │
                  │ cancel             └──fail──► idle
                  ▼
                 idle
```

- `recording`：显示红点/时长；主按钮文案「结束并提交」
- `transcribing`：禁用再次开始；文案「转写中…」
- 成功：写入 answer 并调用 `submitAnswer`；若当前不可提交（状态不允许），仅填入文本并提示手动提交

---

## 5. 错误处理与安全

- 后端校验：允许的 audio Content-Type；最大体积 **15MB**；前端强制 5 分钟上限
- Key 仅存服务端环境变量，不暴露给前端
- 不记录原始音频到 DB / 对象存储；日志只记耗时、转写字符数、错误码，**不记转写全文**
- CORS / Electron：与现有 API base URL 一致

---

## 6. 测试与验收

### 6.1 自动化（最小）

- 后端：mock Paraformer → 正常文本 / 空文本 / 上游错误 / 缺 Key
- 前端：状态切换 idle → recording → transcribing → idle；失败路径不调用 `submitAnswer`

### 6.2 手工

- Chrome Web：口述 → 自动交卷 → 看到断点反馈
- Electron：同上
- 拒麦、无 Key、断网各一次

### 6.3 验收对照 §1.3

见成功标准三条。

---

## 7. 二期预留（不实现）

- TTS 读题开关
- 「口语面试」模式：多轮追问、打断、压力面
- 热词表（框架名 / 项目专有名词）提升中文专名识别
- STT provider 抽象（OpenAI mini / Paraformer 可切换）

---

## 8. 决策记录

| 决策 | 选择 | 理由 |
| --- | --- | --- |
| 产品形态 | 现有训练 + 口述交卷 | 复用 Attempt/评估；最快像「模拟面试」 |
| 结束判定 | 点按开始/结束 | 长答可控，少误触 |
| 语言 | 中文 | 用户一期需求 |
| 平台 | Web + Electron | 同一套 MediaRecorder |
| STT | 百炼 Paraformer | 中文性价比；按量、闲置为零 |
| 接入形态 | 后端 multipart + realtime 流 | 避免公网 URL / OSS |
| TTS | 一期不做 | 缩小范围 |
