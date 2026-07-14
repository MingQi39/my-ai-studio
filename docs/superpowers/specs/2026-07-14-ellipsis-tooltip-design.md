# 省略文案溢出 Tooltip 公共能力设计规格

**日期**：2026-07-14  
**状态**：已定稿待实现  
**模块代号**：`frontend` / `ellipsis-tooltip`

---

## 1. 背景与目标

项目中大量文案使用 Tailwind `truncate` / `line-clamp-*` 做宽度溢出省略。部分调用点用原生 `title=` 补看全文，行为与样式不统一；多数调用点溢出后无法查看完整内容。

### 1.1 成功标准

- 提供统一公共组件 `EllipsisTooltip`，封装省略样式 + 溢出检测 + 条件 Tooltip。
- **仅当文案实际溢出时**，hover 才展示 Tooltip；未溢出无浮层。
- 支持单行（`truncate`）与多行（`line-clamp-n`）。
- Tooltip 使用现有 Radix `Tooltip`，视觉与全站一致。
- 本轮迁移主要业务文案场景，并去掉仅用于补全文的 `title=`，避免双提示。

### 1.2 非目标

- 不改 `components/ui/*` 内部实现（如 `select`、`alert`、折叠侧栏按钮 Tooltip）。
- 不处理容器级 `overflow-hidden`（布局裁剪，非文字省略）。
- 不替换按钮/图标的说明性 `title` 或已有功能 Tooltip。
- 不改造「可点击展开」的 `line-clamp`（如系统指令预览）。
- 不做全局 DOM 自动扫描挂载。

---

## 2. 产品决策

| 项 | 选择 |
|---|---|
| 触发条件 | 实际溢出才显示 Tooltip |
| 呈现 | 公共组件内条件挂载 Radix Tooltip |
| 省略类型 | 单行 + 多行 |
| 迁移范围 | 业务文案优先；UI 库内部本轮不动 |
| Tooltip 内容默认 | 完整文案；可用 `tooltip` 覆盖 |

---

## 3. 架构

```text
EllipsisTooltip
  ├─ 根元素（as + className + 省略样式 + min-w-0）
  ├─ ResizeObserver / 内容变化 → 复测溢出
  │    ├─ lines===1: scrollWidth > clientWidth
  │    └─ lines>1:   scrollHeight > clientHeight
  └─ isOverflow && 有可展示 tooltip 内容
       → Tooltip > TooltipTrigger asChild > 根元素
       → TooltipContent（可换行、max-w 限制）
```

文件建议：`frontend/src/components/EllipsisTooltip.tsx`（业务公共组件，非 shadcn 生成物）。

---

## 4. 组件 API

```tsx
type EllipsisTooltipProps = {
  children: React.ReactNode;
  /** 自定义 Tooltip 内容；默认等于可解析的文本 children */
  tooltip?: React.ReactNode;
  /** 省略行数，默认 1 */
  lines?: number;
  /** 根元素标签，默认 'span' */
  as?: 'span' | 'p' | 'div' | 'h1' | 'h2' | 'h3' | 'h4';
  className?: string;
  side?: 'top' | 'right' | 'bottom' | 'left';
};
```

### 4.1 样式约定

- `lines === 1`：应用 `truncate`（隐含 `overflow-hidden whitespace-nowrap text-ellipsis`）。
- `lines > 1`：应用对应 `line-clamp-{n}`；需保证多行省略可测高。
- 根元素默认追加 `min-w-0`（或调用方可控等价约束），以便 flex 子项正确测量溢出。

### 4.2 Tooltip 内容解析

1. 若传入 `tooltip`，优先使用。
2. 否则若 `children` 为 `string` / `number`，使用其字符串形式。
3. 否则不启用 Tooltip（即使溢出），避免空/错误浮层。

### 4.3 用法示例

```tsx
<EllipsisTooltip className="text-sm font-medium">{file.name}</EllipsisTooltip>
<EllipsisTooltip lines={2} as="p" className="text-xs">{desc}</EllipsisTooltip>
<EllipsisTooltip tooltip={fullPath}>{file.name}</EllipsisTooltip>
```

---

## 5. 溢出检测与交互细节

### 5.1 检测时机

- 挂载后、`children` / `lines` / 尺寸变化时复测。
- 使用 `ResizeObserver`；文案变化后用 `requestAnimationFrame` 测一次，避免布局未稳定误判。

### 5.2 交互

- 未溢出：不渲染 Tooltip 包裹层（或 `open` 禁用），hover 无层。
- 已溢出：Trigger 使用 `asChild` 作用在文案根元素上，不额外包可点击层，避免抢侧栏/列表点击。
- TooltipContent：允许换行；限制最大宽度（如 `max-w-xs` 或 `max-w-sm`），长 URL/路径可断行。
- 迁入点去掉仅为补全文的原生 `title=`。

### 5.3 嵌套与冲突

- 放在按钮/可点击行内：以文案元素为 Trigger，点击事件仍由外层处理。
- 若外层已有功能 Tooltip（说明「做什么」），与「展示被省略全文」职责不同；迁入时按场景二选一或外层说明优先，不为同一触发源叠两个 Tooltip。

---

## 6. 迁移清单（本轮）

### 6.1 纳入

优先替换实际展示文案的 `truncate` / 业务 `line-clamp`，示例范围：

- `AppSidebar`、`SessionHistory`、`ActiveModelBadge`
- `MainWorkspace`、`StudioLaunchpad`、`LanguageSwitcher`
- Spider：`SpiderWorkspace`、`SpiderControlPanel`、`SpiderFilesWorkspace`、`SpiderTodoCard`、`SpiderEmptyState`、`SpiderSessionScopeMeta`
- Travel / Fitness：Workspace 标题、ControlPanel、推荐卡片等业务省略文案
- 其他同模式业务文案（文件名、会话名、模型名、Todo 内容）

### 6.2 排除

- `frontend/src/components/ui/**`
- 容器 `overflow-hidden`、进度条裁剪、Dialog 滚动裁剪等
- 操作按钮说明性 `title` / 已有功能 Tooltip
- 可展开预览类 `line-clamp`（如 `SystemInstructionModal`）

---

## 7. 测试与验收

1. **未溢出**：短文案 hover 无 Tooltip。
2. **单行溢出**：缩窄容器或加长文案后 hover 出现全文 Tooltip。
3. **多行溢出**：`lines={2|3}` 超出后出现 Tooltip。
4. **动态变化**：窗口缩放或侧栏展开/收起后，溢出状态与 Tooltip 启用随之正确切换。
5. **嵌套点击**：侧栏会话行、文件列表点击不受影响。
6. **主题**：亮/暗色下 Tooltip 与现有 Radix 样式一致。
7. **无双提示**：迁入点不再同时出现浏览器原生 `title` 与 Radix Tooltip。

---

## 8. 实现顺序建议

1. 实现 `EllipsisTooltip` + 溢出检测。
2. 选 1～2 个高频场景（如侧栏会话名、Spider 文件名）验证。
3. 批量迁移 §6.1 业务调用点，并清理对应 `title=`。
4. 手动过一遍验收清单。
