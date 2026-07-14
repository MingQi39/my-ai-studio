# EllipsisTooltip 溢出文案 Tooltip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供统一的 `EllipsisTooltip` 公共组件（单行/多行省略 + 仅溢出时展示 Radix Tooltip），并迁移主要业务文案调用点。

**Architecture:** 新建 `EllipsisTooltip`：根元素承担省略样式与 `ref` 测量；`ResizeObserver` + rAF 检测溢出；仅当溢出且有可解析 Tooltip 内容时用现有 Radix `Tooltip` + `TooltipTrigger asChild` 包裹。业务侧把展示文案的 `truncate` / `line-clamp-*` 换成该组件，并去掉仅为补全文的 `title=`。

**Tech Stack:** React 18、Tailwind、`@radix-ui/react-tooltip`、现有 `frontend/src/components/ui/tooltip.tsx`、`cn` from `@/components/ui/utils`

**Spec:** `docs/superpowers/specs/2026-07-14-ellipsis-tooltip-design.md`

**Note:** 前端无 Vitest/Jest。本计划不做新测试框架引入；用 TypeScript build + 规格 §7 手工验收。

---

## File map

| File | Responsibility |
|------|----------------|
| `frontend/src/components/EllipsisTooltip.tsx` | 公共组件：省略样式、溢出检测、条件 Tooltip |
| `frontend/src/components/ActiveModelBadge.tsx` | 试点：模型名省略 + 去全文 `title` |
| `frontend/src/features/spider/components/SpiderTodoCard.tsx` | 试点：Todo 内容省略 |
| `frontend/src/components/AppSidebar.tsx` | 会话标题 / 用户名 / 邮箱 |
| `frontend/src/components/SessionHistory.tsx` | 会话标题 |
| `frontend/src/components/MainWorkspace.tsx` | 顶栏文案 |
| `frontend/src/components/chat/StudioLaunchpad.tsx` | 历史会话标题 |
| `frontend/src/components/LanguageSwitcher.tsx` | 语言 label |
| `frontend/src/components/ControlPanel.tsx` | 模型名 / 说明摘要 |
| `frontend/src/components/ConnectionModal.tsx` | 列表与错误文案省略 |
| `frontend/src/components/ModelSelectorModal.tsx` | 模型描述省略 |
| `frontend/src/components/chat/MessageQueuePanel.tsx` | 队列消息 `line-clamp-3` |
| Spider / Travel / Fitness Workspace、ControlPanel、Files、EmptyState、SessionScopeMeta、RecommendationCards、FilePreviewViewer、TravelControlPanel | 业务标题、文件名、URL 等 |

**Explicit non-touch:** `frontend/src/components/ui/**`、`SystemInstructionModal` 可展开 `line-clamp`、按钮/操作说明性 `title`（如删除会话、新建会话、导出代码、切换语言标题、iframe `title`）。

---

### Task 1: 实现 `EllipsisTooltip` 组件

**Files:**
- Create: `frontend/src/components/EllipsisTooltip.tsx`

- [ ] **Step 1: 创建组件文件，写入完整实现**

```tsx
import * as React from 'react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/components/ui/utils';

const LINE_CLAMP_CLASS: Record<number, string> = {
  2: 'line-clamp-2',
  3: 'line-clamp-3',
  4: 'line-clamp-4',
  5: 'line-clamp-5',
  6: 'line-clamp-6',
};

export type EllipsisTooltipProps = {
  children: React.ReactNode;
  tooltip?: React.ReactNode;
  lines?: number;
  as?: 'span' | 'p' | 'div' | 'h1' | 'h2' | 'h3' | 'h4';
  className?: string;
  side?: 'top' | 'right' | 'bottom' | 'left';
};

function resolveTooltipContent(
  tooltip: React.ReactNode | undefined,
  children: React.ReactNode,
): React.ReactNode | null {
  if (tooltip != null && tooltip !== false) return tooltip;
  if (typeof children === 'string' || typeof children === 'number') {
    return String(children);
  }
  return null;
}

function measureOverflow(el: HTMLElement, lines: number): boolean {
  if (lines <= 1) return el.scrollWidth > el.clientWidth + 1;
  return el.scrollHeight > el.clientHeight + 1;
}

export function EllipsisTooltip({
  children,
  tooltip,
  lines = 1,
  as: Tag = 'span',
  className,
  side = 'top',
}: EllipsisTooltipProps) {
  const ref = React.useRef<HTMLElement | null>(null);
  const [isOverflow, setIsOverflow] = React.useState(false);
  const tooltipContent = resolveTooltipContent(tooltip, children);
  const clampClass =
    lines <= 1 ? 'truncate' : (LINE_CLAMP_CLASS[lines] ?? `line-clamp-[${lines}]`);

  const remeasure = React.useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setIsOverflow(measureOverflow(el, lines));
  }, [lines]);

  React.useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    let raf = 0;
    const schedule = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(remeasure);
    };

    schedule();
    const ro = new ResizeObserver(schedule);
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [remeasure, children, lines, className, tooltipContent]);

  const node = (
    <Tag
      ref={ref as never}
      className={cn('min-w-0', clampClass, className)}
    >
      {children}
    </Tag>
  );

  if (!isOverflow || tooltipContent == null) {
    return node;
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{node}</TooltipTrigger>
      <TooltipContent
        side={side}
        className="max-w-sm break-words text-left whitespace-normal"
      >
        {tooltipContent}
      </TooltipContent>
    </Tooltip>
  );
}
```

注意：

1. Tailwind 对动态 `line-clamp-${n}` 可能扫不到；优先用 `LINE_CLAMP_CLASS` 静态表（2–6）。若 `lines` 超出表，可用任意值 class `line-clamp-[n]`（确保 safelist 或接受仅常用行数）。
2. 溢出容差用 `+ 1` 避免亚像素误判。
3. 未溢出或无可展示内容时直接返回裸节点，不挂 Tooltip。

- [ ] **Step 2: 确认 TypeScript 能解析路径**

Run（在 `frontend/`）:

```bash
npx tsc --noEmit -p tsconfig.json 2>&1 | head -40
```

Expected: 无与 `EllipsisTooltip.tsx` 相关的报错（若项目本身已有无关错误可忽略，但新文件不得引入）。

若无单独 `tsc` 脚本，改用：

```bash
npm run build
```

Expected: build 成功，或错误不来自本文件。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/EllipsisTooltip.tsx
git commit -m "$(cat <<'EOF'
feat(frontend): add EllipsisTooltip for overflow-only tooltips

EOF
)"
```

---

### Task 2: 试点迁移 — ActiveModelBadge + SpiderTodoCard

**Files:**
- Modify: `frontend/src/components/ActiveModelBadge.tsx`
- Modify: `frontend/src/features/spider/components/SpiderTodoCard.tsx`

- [ ] **Step 1: 改 ActiveModelBadge**

- `import { EllipsisTooltip } from '@/components/EllipsisTooltip'`
- compact / default 两个内部 `<span className={...truncate...} title={displayName}>` 改为：

```tsx
<EllipsisTooltip
  className={cn(
    'font-medium',
    variant === 'compact' ? undefined : 'text-sm',
    isConfigured ? 'text-[var(--text-primary)]' : 'text-[var(--text-placeholder)]',
  )}
  tooltip={displayName}
>
  {variant === 'compact' ? (secondary ?? primary) : primary}
</EllipsisTooltip>
```

（按 variant 分支保留原有展示文本；`EllipsisTooltip` 自带 `truncate`，勿再传 `truncate`。）

- 保留按钮上功能说明 `title={t('workspace.changeModel')}`（操作提示，非全文补全）。
- 去掉 span 上的 `title={displayName}`。

- [ ] **Step 2: 改 SpiderTodoCard**

- 将 Todo 内容那一段：

```tsx
<span
  className={cn('min-w-0 flex-1 truncate text-sm', ...)}
  title={todo.content}
>
  {todo.content}
</span>
```

改为：

```tsx
<EllipsisTooltip
  className={cn(
    'min-w-0 flex-1 text-sm',
    isDone
      ? 'text-[var(--text-secondary)] line-through'
      : isFailed
        ? 'text-red-600'
        : 'text-[var(--text-primary)]',
  )}
>
  {todo.content}
</EllipsisTooltip>
```

- 标题行 `completedCount` 的 `truncate` 也可换成 `EllipsisTooltip`（短文案多数不溢出，行为无害）。

- [ ] **Step 3: 手工冒烟**

1. 打开带长模型名的页面：未溢出无 tooltip；缩窄/加长后 overflow 出现 Radix tooltip，内容为完整 `displayName`。
2. Spider Todo 长 content：溢出后 hover 见全文；点击折叠按钮仍正常。
3. 有 `onClick` 的 ActiveModelBadge：点击仍打开选模型；勿出现原生 `title` 与 Radix 双提示叠在模型名上（按钮 `changeModel` title 可保留）。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ActiveModelBadge.tsx \
  frontend/src/features/spider/components/SpiderTodoCard.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): pilot EllipsisTooltip on model badge and spider todos

EOF
)"
```

---

### Task 3: 迁移核心壳层组件

**Files:**
- Modify: `frontend/src/components/AppSidebar.tsx`
- Modify: `frontend/src/components/SessionHistory.tsx`
- Modify: `frontend/src/components/MainWorkspace.tsx`
- Modify: `frontend/src/components/chat/StudioLaunchpad.tsx`
- Modify: `frontend/src/components/LanguageSwitcher.tsx`

- [ ] **Step 1: AppSidebar**

替换用户名、邮箱、会话标题等**展示文案**的 `truncate` 为 `EllipsisTooltip`：

- 约 699 / 713–714 / 830 / 833 行附近的 truncate 文本节点。
- **不要**改新建会话、删除会话等按钮的 `title={t(...)}`。

模式：

```tsx
import { EllipsisTooltip } from '@/components/EllipsisTooltip';

// before
<span className="... truncate ...">{currentUser.username}</span>

// after
<EllipsisTooltip className="text-sm font-medium">
  {currentUser.username}
</EllipsisTooltip>
```

父级 flex 行保持 `min-w-0`。

- [ ] **Step 2: SessionHistory**

会话标题 `truncate` → `EllipsisTooltip`（保留原 font/size class，去掉自带的 truncate）。

- [ ] **Step 3: MainWorkspace**

顶栏会话/标题 truncate span → `EllipsisTooltip`；保留 export / startTalking 等功能 `title`。

- [ ] **Step 4: StudioLaunchpad**

`session.title` 的 truncate `<p>` → `<EllipsisTooltip as="p" className="text-sm font-medium text-[var(--text-primary)]">`。

模型卡片的 `title={t(model.titleKey)}` 若是卡片 props（非 DOM title），勿误删。

- [ ] **Step 5: LanguageSwitcher**

语言 `lang.label` 的 truncate → `EllipsisTooltip`；保留开关按钮 `title={t('language.switcherTitle')}`。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AppSidebar.tsx \
  frontend/src/components/SessionHistory.tsx \
  frontend/src/components/MainWorkspace.tsx \
  frontend/src/components/chat/StudioLaunchpad.tsx \
  frontend/src/components/LanguageSwitcher.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): migrate shell truncate text to EllipsisTooltip

EOF
)"
```

---

### Task 4: 迁移 Control / Modal / Queue

**Files:**
- Modify: `frontend/src/components/ControlPanel.tsx`
- Modify: `frontend/src/components/ConnectionModal.tsx`
- Modify: `frontend/src/components/ModelSelectorModal.tsx`
- Modify: `frontend/src/components/chat/MessageQueuePanel.tsx`

- [ ] **Step 1: ControlPanel**

- 模型名：有 `title={selectedModel}` 的 truncate → `EllipsisTooltip tooltip={selectedModel}`，去掉 `title`。
- `line-clamp-3` 说明段落 → `<EllipsisTooltip as="p" lines={3} className="text-xs text-[var(--text-secondary)]">`。

- [ ] **Step 2: ConnectionModal / ModelSelectorModal**

列表名、副标题、错误信息等 truncate 文案 → `EllipsisTooltip`；不要动 Dialog 布局用的 `overflow-hidden`。

- [ ] **Step 3: MessageQueuePanel**

```tsx
<EllipsisTooltip
  as="p"
  lines={3}
  className="flex-1 text-sm text-slate-700 dark:text-slate-200 whitespace-pre-wrap break-words"
>
  {message text}
</EllipsisTooltip>
```

注意：`whitespace-pre-wrap` 与单行 `truncate` 冲突；多行用 `lines={3}`，不要再加 `truncate`。若 `whitespace-pre-wrap` 导致测高异常，保留 `break-words` + `line-clamp-3` 即可，去掉会破坏钳制的 class。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ControlPanel.tsx \
  frontend/src/components/ConnectionModal.tsx \
  frontend/src/components/ModelSelectorModal.tsx \
  frontend/src/components/chat/MessageQueuePanel.tsx
git commit -m "$(cat <<'EOF'
refactor(frontend): migrate control/modal/queue text to EllipsisTooltip

EOF
)"
```

---

### Task 5: 迁移 Spider 业务面

**Files:**
- Modify: `frontend/src/features/spider/SpiderWorkspace.tsx`
- Modify: `frontend/src/features/spider/SpiderControlPanel.tsx`
- Modify: `frontend/src/features/spider/SpiderFilesWorkspace.tsx`
- Modify: `frontend/src/features/spider/components/SpiderEmptyState.tsx`
- Modify: `frontend/src/features/spider/components/SpiderSessionScopeMeta.tsx`
- Modify: `frontend/src/features/spider/components/file-preview/FilePreviewViewer.tsx`

- [ ] **Step 1: Workspace / ControlPanel / Files**

- 页头 `h1`/`p`/`h2` 固定 i18n 短标题：可换 `EllipsisTooltip as="h1"` 等（窄屏防溢出）。
- **动态**内容（`sessionTitle`、`file.name`、模型名、文件 meta）：换 `EllipsisTooltip`，并删除对应全文 `title={sessionTitle}` / 同类。
- iframe 的 `title={...}` **保留**（无障碍名，不是省略补全）。

示例（文件名）：

```tsx
<EllipsisTooltip as="p" className="text-sm font-medium text-[var(--text-primary)]">
  {file.name}
</EllipsisTooltip>
```

有 `title={sessionTitle}` 且节点本身 truncate 时：

```tsx
<EllipsisTooltip as="p" className="truncate-removed-classes..." tooltip={sessionTitle}>
  {sessionTitle}
</EllipsisTooltip>
```

- [ ] **Step 2: EmptyState / SessionScopeMeta / FilePreviewViewer**

- URL、sessionLabel 等：`EllipsisTooltip` + 去掉 `title=`。
- 预览顶栏标题 truncate → `EllipsisTooltip`。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/features/spider/SpiderWorkspace.tsx \
  frontend/src/features/spider/SpiderControlPanel.tsx \
  frontend/src/features/spider/SpiderFilesWorkspace.tsx \
  frontend/src/features/spider/components/SpiderEmptyState.tsx \
  frontend/src/features/spider/components/SpiderSessionScopeMeta.tsx \
  frontend/src/features/spider/components/file-preview/FilePreviewViewer.tsx
git commit -m "$(cat <<'EOF'
refactor(spider): migrate truncated labels to EllipsisTooltip

EOF
)"
```

---

### Task 6: 迁移 Travel / Fitness 业务面

**Files:**
- Modify: `frontend/src/features/travel/TravelWorkspace.tsx`
- Modify: `frontend/src/features/travel/TravelControlPanel.tsx`
- Modify: `frontend/src/features/fitness/FitnessWorkspace.tsx`
- Modify: `frontend/src/features/fitness/FitnessControlPanel.tsx`
- Modify: `frontend/src/features/fitness/components/FitnessRecommendationCards.tsx`

- [ ] **Step 1: Travel / Fitness Workspace 页头**

`pageTitle` / agentTitle / 副标题 truncate → `EllipsisTooltip as="h1"|"p"`。

- [ ] **Step 2: TravelControlPanel / FitnessControlPanel / RecommendationCards**

- 模型或状态 mono truncate → `EllipsisTooltip`。
- `FitnessControlPanel` 的 `line-clamp-2` 名称 → `<EllipsisTooltip lines={2}>`。
- `FitnessRecommendationCards` 标题 truncate → `EllipsisTooltip as="h4"`。

- [ ] **Step 3: TravelWorkspace 工具列表**

- `title={tool.name}` 且名称 truncate 的节点 → `EllipsisTooltip tooltip={tool.name}`，去掉 `title`。
- 按钮内短文案「复制 Schema」「测试调用」：若仅为 flex 收缩、文案固定很短，**可跳过**（不必为固定短 label 包组件）。
- `测试 {selectedTool.name}` 标题：用 `EllipsisTooltip`。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/travel/TravelWorkspace.tsx \
  frontend/src/features/travel/TravelControlPanel.tsx \
  frontend/src/features/fitness/FitnessWorkspace.tsx \
  frontend/src/features/fitness/FitnessControlPanel.tsx \
  frontend/src/features/fitness/components/FitnessRecommendationCards.tsx
git commit -m "$(cat <<'EOF'
refactor(travel,fitness): migrate truncated labels to EllipsisTooltip

EOF
)"
```

---

### Task 7: 全量扫尾与验收

**Files:**
- 复查所有业务 `truncate` / 业务 `line-clamp`（排除 `ui/**` 与可展开预览）

- [ ] **Step 1: 搜索残留**

```bash
rg -n "truncate|line-clamp-[0-9]" frontend/src --glob '!**/components/ui/**'
```

对每个命中按规则判定：

| 类型 | 动作 |
|------|------|
| 展示文案省略 | 改 `EllipsisTooltip` |
| 布局 `overflow-hidden` / 进度条 | 跳过 |
| 可展开 `SystemInstructionModal` | 跳过 |
| 短固定按钮字 | 可跳过 |
| 仅为补全文的 `title=` | 删除（组件已覆盖） |

再搜：

```bash
rg -n "title=\{" frontend/src --glob '!**/components/ui/**'
```

确认无「truncate 节点 + title=全文」双提示残留。

- [ ] **Step 2: Build**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 3: 手工验收（对照 spec §7）**

1. 短文案 hover 无 tooltip  
2. 单行溢出有 tooltip  
3. 多行（队列 `lines={3}` / fitness `lines={2}`）溢出有 tooltip  
4. 缩放侧栏后启用状态正确切换  
5. 侧栏会话点击、文件列表点击正常  
6. 亮/暗色 Tooltip 样式正常  
7. 无原生 title + Radix 双提示  

- [ ] **Step 4: Commit 扫尾（若有改动）**

```bash
git add -u frontend/src
git commit -m "$(cat <<'EOF'
chore(frontend): finish EllipsisTooltip migration sweep

EOF
)"
```

若无改动则跳过 commit。

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| `EllipsisTooltip` API / 单行+多行 | Task 1 |
| 仅溢出显示 Tooltip | Task 1 |
| Radix Tooltip + asChild | Task 1 |
| `tooltip` 覆盖 / 非文本不启用 | Task 1 |
| 去掉全文 `title=` | Task 2–6 |
| 业务迁移、不改 ui/** | Task 3–6，Task 7 排除 |
| 不改可展开 line-clamp | Task 7 排除 SystemInstructionModal |
| 验收 §7 | Task 2 冒烟 + Task 7 |

---

## Self-review notes

- 无 TBD /「类似 Task N」占位；迁移文件路径已列全。
- 前端无单测 runner，故不以「写 failing test」为第一步，改为实现 + build + 手工验收。
- `ActiveModelBadge` 按钮功能 `title` 与全文 Ellipsis 并存时：全文挂在内层文本，功能 title 在 button；验收时确认无双浮层抢同一省略文字。
