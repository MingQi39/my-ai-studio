# 讲义「对照」可点击深链

日期：2026-07-23  
状态：待确认

## 问题

模板讲义「对照」行只提示用户去下方参考链接找章节，无法一点跳转。

## 目标

- 「对照」改为 **Markdown 可点链接**
- **能锚就锚**（主要靠 GitHub `#heading`）；锚不到则落到 **整篇文档**（飞书手册或 GitHub 文件）
- LLM 讲义在 prompt 中同样要求写出可点对照链接

## 非目标

- 不实现飞书页内精确锚点（飞书 wiki fragment 不稳定）
- 不在生成时实时抓取外网解析标题
- 不改前端 Markdown 渲染器（已支持链接）

## 方案

在 `learning_sources` 增加课程章节 → 主参考源映射：

| 字段 | 含义 |
|------|------|
| `section_title` | 与 curriculum 一致，如「Transformer 与注意力机制」 |
| `label` | 链接文案，如「Transformer 手册」或「07-大模型基础 · 注意力」 |
| `url` | 完整 http(s) URL；有 GitHub 标题锚点则带 `#…`，否则整页 |

**优先级（已拍板）**：

1. 若该节有 **已校对的 GitHub 文件 + heading slug** → 用 `blob/main/...md#slug`
2. 否则若 topic 有 **飞书手册** → 用手册整页 URL
3. 否则 → 该 stage/topic 的首个 GitHub 文件整页
4. 再否则 → 不写死链，退回「见下方参考链接」（极少）

模板文案示例：

```markdown
- **对照**：[Transformer 手册](https://…/wiki/…) · 用原文核对「Transformer 与注意力机制」
```

或带锚点：

```markdown
- **对照**：[07-大模型基础 · 注意力](https://github.com/…/07-大模型基础.md#注意力) · 用原文核对
```

`format_source_links` 仍保留底部链接条；对照行只多一个「当日章节主链」。

## LLM 讲义

在 `_build_user_prompt` / system 中增加：对照行必须使用提供的「章节主链」Markdown 链接，禁止只写「打开下方链接」。

## 验证

- 单元测试：若干 `section_title` 解析出带 `http` 的 markdown 链接；未知章节走 fallback
- 手工：打开模板讲义，点「对照」能打开手册或 GitHub

## 风险

- GitHub 改标题会导致锚点失效 → 映射表可改；失效时仍打开文件顶部，可接受
- 飞书需登录/权限 → 与现有参考链接相同，不新增假设
