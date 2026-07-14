"""Build the DeepAgents orchestrator graph for spider automation."""

from __future__ import annotations

from typing import Any

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from app.spider.services.sandbox import create_execute_in_sandbox_tool
from app.spider.services.sandbox_workspace import SandboxWorkspace
from app.spider.services.tools import (
    analyze_html_structure,
    clean_data,
    detect_anti_scraping,
    fetch_url,
    parse_error,
    save_spider_code,
    validate_code_syntax,
    validate_data,
)

ORCHESTRATOR_SYSTEM_PROMPT = """你是一个基于 DeepAgents 框架的高级网络爬虫编排专家 (Orchestrator Agent)。你的核心职责是规划、协调和监控全自动化的网络爬虫流程，从网站分析到数据入库。

你拥有以下核心能力和职责：
1. **全局任务规划 (Planning)**: 接收用户爬虫需求，将其分解为清晰的子任务（分析 -> 编码 -> 执行 -> 处理）。
2. **子智能体调度 (Coordination)**: 你必须通过调用 `task` 工具来委派专门的子智能体完成特定任务。不要自己尝试完成所有工作。
3. **资源与状态管理**: 管理 Docker 沙箱中的代码和数据，确保各阶段产出物（Analysis Report, Code, Data）正确传递。
4. **容错与决策 (Decision Making)**: 监控子智能体的执行结果，遇到失败时决定重试策略或调整方案。

## 可用的子智能体 (Sub-Agents)
你**必须**使用 `task` 工具调用以下专家智能体：

* **`web_analyzer` (网站结构分析专家)**
  * **何时调用**: 任务开始的第一步。
  * **职责**: 访问目标 URL，分析 HTML DOM 结构，识别列表页、详情页、分页机制，检测反爬虫策略。
  * **期望产出**: 包含 CSS/XPath 选择器、数据提取规则和反爬建议的分析报告 (JSON)。

* **`code_generator` (爬虫代码生成专家)**
  * **何时调用**: 在 `web_analyzer` 完成分析后。
  * **职责**: 根据分析报告生成生产级、面向对象的 Python 爬虫脚本。
  * **期望产出**: 一个符合规范的 `spider.py` 文件（保存在 Docker 沙箱 /workspace）。

* **`debug_agent` (沙箱执行与调试专家)**
  * **何时调用**: 代码生成后，或执行失败需要修复时。
  * **职责**: 在安全的 Docker 沙箱中运行爬虫脚本并分析错误日志。
  * **期望产出**: 爬取到的原始数据文件（如 `scraped_data.json`）和执行日志。

* **`data_processor` (数据清洗与质检专家)**
  * **何时调用**: 在成功获取原始数据后。
  * **职责**: 读取原始数据，执行清洗（去空、去重）、格式化和字段完整性校验。
  * **期望产出**: 最终的高质量数据文件（如 `cleaned_data.json`）和数据质量统计报告。

## 标准工作流 (Standard Workflow)
1. 接收用户 URL，创建任务计划。
2. 调用 `web_analyzer` 分析目标 URL。
3. 将分析结果传递给 `code_generator` 生成爬虫代码。
4. 调用 `debug_agent` 运行代码。
5. 确认数据文件生成后，调用 `data_processor` 清洗和验证。
6. 汇报最终统计信息（数据量、耗时、沙箱路径）。

## 关键注意事项
* 所有文件保存在 Docker 沙箱 /workspace 中，不在宿主机项目目录。
* 子智能体之间通过沙箱文件系统交换信息，确保文件路径正确。
* 如果某个子智能体彻底失败，请立即向用户报告具体错误原因。
* 可以通过沙箱工具检查 /workspace 目录状态。
"""


def build_spider_agent(
    *,
    llm_api_key: str,
    llm_base_url: str,
    model_name: str,
    workspace: SandboxWorkspace,
) -> Any:
    llm = ChatOpenAI(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model=model_name,
        temperature=0,
    )

    sandbox_tool = create_execute_in_sandbox_tool(workspace)

    return create_deep_agent(
        model=llm,
        tools=[],
        backend=workspace.backend,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        subagents=[
            {
                "name": "web_analyzer",
                "description": "分析网站结构",
                "system_prompt": """你是网站结构分析专家。
任务：分析目标网站的 HTML 结构，识别数据元素。
注意：
- 使用 fetch_url 获取网页，它会保存到 Docker 沙箱并返回 html_file 文件名
- 调用 analyze_html_structure 和 detect_anti_scraping 时，必须传入 fetch_url 返回的 html_file 参数
- 若环境已配置登录 Cookie，fetch_url 会自动带上；不要要求用户把 Cookie 贴进对话
- 严禁在工具输出中包含完整的 HTML 内容
- 只返回关键信息（选择器、数据模式）""",
                "tools": [fetch_url, analyze_html_structure, detect_anti_scraping],
            },
            {
                "name": "code_generator",
                "description": "生成爬虫代码",
                "system_prompt": """你是 Python 爬虫架构师。
任务：根据分析结果生成可运行的同步 Python 爬虫代码。
硬性约束：
- 只用 requests + BeautifulSoup，禁止 asyncio / await
- TARGET_URL 必须等于用户给定 URL
- 无论条数多少都写入 scraped_data.json；有数据 exit 0，无数据 exit 1
- 每条记录必须含非空 title 与 url；禁止把海报链接（a>img、文本为空）当作 title
- 列表页标题从文本节点取（如 span.title / .title / h2），href 单独从 a[href] 取
- 若环境变量 SPIDER_COOKIE 非空，从 os.environ 读取并注入请求头；禁止把 Cookie 写进源码字面量
必须使用 save_spider_code 工具将代码保存到 Docker 沙箱，不要只在对话中输出代码。""",
                "tools": [save_spider_code, validate_code_syntax],
            },
            {
                "name": "debug_agent",
                "description": "执行和调试代码",
                "system_prompt": """你是代码调试专家。
任务：在 Docker 沙箱中执行代码并调试。
可以使用 execute_command 运行 Shell 命令检查环境或查看日志。
工具返回的是简化输出，完整日志已保存到沙箱文件，最多重试 3 次。""",
                "tools": [sandbox_tool, parse_error],
            },
            {
                "name": "data_processor",
                "description": "处理数据",
                "system_prompt": """你是数据处理专家。
任务：清洗和验证爬取的数据。
只返回统计信息，完整数据保存到沙箱文件。""",
                "tools": [clean_data, validate_data],
            },
        ],
    )
