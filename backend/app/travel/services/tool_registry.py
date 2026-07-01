"""
工具注册表
管理所有可用工具，支持注册、执行、转换为 OpenAI Function Calling 格式
"""
from typing import Dict, Any, Callable, Awaitable, List
import json


class Tool:
    """单个工具定义"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Awaitable[str]]
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema 格式
        self.handler = handler


class ToolsRegistry:
    """工具注册表，管理所有可用工具"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable[..., Awaitable[str]]
    ):
        """注册一个工具"""
        self._tools[name] = Tool(name, description, parameters, handler)

    def to_openai_tools(self) -> List[dict]:
        """转为 OpenAI Function Calling 的 tools 参数格式"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, args: Dict[str, Any]) -> str:
        """执行指定工具，返回字符串结果"""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")

        try:
            result = await tool.handler(**args)
            return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def list_tools(self) -> List[dict]:
        """列出所有工具（用于工具台页面）"""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters
            }
            for t in self._tools.values()
        ]

    @property
    def tool_names(self) -> List[str]:
        return list(self._tools.keys())
