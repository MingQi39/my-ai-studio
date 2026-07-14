# Spider Codegen 导入守卫设计规格

**日期**：2026-07-14  
**状态**：已定稿（待用户确认后实现）  
**模块代号**：`spider` / `codegen-import-guard`  
**关联**：[`2026-07-14-spider-browser-escalation-design.md`](./2026-07-14-spider-browser-escalation-design.md)

---

## 1. 背景与目标

Playwright 引擎路径下，LLM 偶发生成非法导入，例如：

```python
from playwright.sync_api import sync_playwright, Browser, Page, Soup
```

`Soup` 不存在于 `playwright.sync_api`，沙箱执行立刻 `ImportError`。当前 `_generate_spider_code_with_retry` 只做 `ast.parse` 语法校验，这类代码语法合法，无法在进沙箱前拦住。

### 1.1 成功标准

- 含 `from playwright.sync_api import ... Soup`（或同类幻觉名）的代码在 codegen 校验阶段判为无效。
- 校验失败复用现有路径：`llm_fixed` → 仍无效则 `template`（`_fallback_playwright_spider_code` / `_fallback_spider_code`）。
- Playwright prompt / runtime fix prompt 明确写出合法导入块，减少幻觉。
- 合法 Playwright 模板与「sync_playwright + BeautifulSoup」组合通过校验。

### 1.2 非目标

- 不改沙箱镜像或依赖安装策略。
- 不做完整依赖图 / 第三方包安全扫描。
- 不新增 pipeline 阶段或 Todo 语义。
- 不在宿主环境执行 LLM 生成的代码来探测 ImportError。

### 1.3 产品决策

| 项 | 选择 |
|---|---|
| 策略 | Prompt 收紧 + AST 导入白名单 |
| 失败处理 | 等同语法失败，走 `llm_fixed` → template |
| 校验时机 | codegen 产出后、写入沙箱执行前 |
| 范围 | `requests` 与 `playwright` 两套引擎均校验 |

---

## 2. Prompt 约束

### 2.1 Playwright `_codegen_system_prompt`

新增硬性条款（表述可微调，语义固定）：

- 合法导入仅允许：
  - `from playwright.sync_api import sync_playwright`
  - `from bs4 import BeautifulSoup`
  - 以及标准库（`json` / `os` / `time` / `logging` 等）
- **禁止**从 `playwright` 或 `playwright.sync_api` 导入 `Soup`、`BeautifulSoup`、`Browser`、`Page`（类型名不需要 import；若需要类型可注解为字符串或不写）
- 解析 HTML 必须用 `BeautifulSoup(page.content(), ...)`，不得伪造 `Soup`

### 2.2 `_fix_runtime_spider_code`（playwright 分支）

在硬性约束中同步上述导入规则，并给出一行合法示例：

```python
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
```

### 2.3 requests 引擎 prompt

补充一句：禁止 `playwright` / `selenium` 导入；解析只用 `from bs4 import BeautifulSoup`。

### 2.4 fix-syntax 路径

`_generate_spider_code_with_retry` 里修语法的 SystemMessage 若因本守卫触发，应改为同时覆盖「语法 + 非法导入」，例如说明错误原因（来自校验 message），避免只修语法却保留 `Soup`。

---

## 3. 导入校验

### 3.1 API

新增纯函数（建议放在 `spider_pipeline_service.py` 或抽到 `backend/app/spider/services/code_guards.py`）：

```python
def validate_spider_imports(code: str, *, scrape_engine: str) -> dict[str, Any]:
    """返回 {valid: bool, errors: [...], message: str}，形状对齐 validate_code_syntax。"""
```

`_validate_python_code`（或调用方）组合为：

1. 先 `ast.parse`（现有语法校验）
2. 再 `validate_spider_imports(code, scrape_engine=...)`

任一步失败 → `valid=False`。

### 3.2 规则（AST `Import` / `ImportFrom`）

**公共：**

- `from bs4 import ...`：允许名仅 `BeautifulSoup`（可选放行 `Tag`）；禁止别名成无关符号以外的奇怪用法不强制，但 `Soup` 单独从 bs4 导入也不接受（正确名是 `BeautifulSoup`）。
- 禁止 `import Soup` / `from xxx import Soup`。

**`scrape_engine == "playwright"`：**

- `from playwright.sync_api import ...`：允许名白名单初始为 `{"sync_playwright"}`（可后续按需加 `Error` / `TimeoutError` 若 Playwright 真实导出且模板需要；默认从严）。
- 禁止 `from playwright import ...` 除明确需要外；若出现非 `sync_api` 子模块，判失败或仅允许 `sync_api`。
- 允许 `import playwright` 仅当不用于错误属性访问——为简单起见：**禁止**裸 `import playwright`，只允许 `from playwright.sync_api import sync_playwright`。

**`scrape_engine == "requests"`：**

- 任何 `playwright` / `selenium` 相关 import → 失败。
- `requests` 允许；`bs4` 按公共规则。

### 3.3 与 retry 的衔接

`_generate_spider_code_with_retry`：

- 调用组合校验时传入 `scrape_engine`。
- 若首次失败：fix prompt 携带 `message`（含非法导入名）。
- 二次仍失败：fallback template（与现逻辑一致）。

Runtime fix 成功后若再次 execute 前有校验点，同样过导入守卫（若当前 pipeline 在 save 前已有校验则对齐；否则至少在 codegen retry 路径保证）。

---

## 4. 测试

| 用例 | 期望 |
|------|------|
| `from playwright.sync_api import sync_playwright, Soup` + engine=playwright | `valid=False`，message 提及 Soup |
| 合法 `sync_playwright` + `BeautifulSoup` | `valid=True` |
| requests 引擎代码含 `playwright` import | `valid=False` |
| `_fallback_playwright_spider_code` 输出 | `valid=True` |

单测文件建议：`backend/tests/spider/test_codegen_import_guard.py`。

---

## 5. 非目标回顾 / 风险

- **误杀**：LLM 导入 `Browser`/`Page` 作类型注解时会被拒 → 可接受，逼其用更简单脚本或走 template。
- **白名单过窄**：后续真实需要 `TimeoutError` 等再扩名单，默认从严。
- **Prompt  alone 不够**：本规格以 AST 守卫为主，prompt 为辅助。

---

## 6. 实现触点（预估）

| 文件 | 变更 |
|------|------|
| `backend/app/spider/services/spider_pipeline_service.py`（或新 `code_guards.py`） | prompt + `validate_spider_imports` + retry 接线 |
| `backend/tests/spider/test_codegen_import_guard.py` | 新增单测 |

工作量小，独立于浏览器跃迁大包，可单独合入。
