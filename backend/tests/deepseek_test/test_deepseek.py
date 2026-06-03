"""
DeepSeek API 测试脚本
测试三种功能：
1. 基本调用
2. 思考模式（Reasoning）
3. 工具调用（Function Calling）
"""

import json
from openai import OpenAI

# API 配置
API_KEY = "sk-"
BASE_URL = "https://api.deepseek.com"

# 初始化客户端
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ==================== 1. 基本调用 ====================
def test_basic_call():
    """测试 DeepSeek 基本调用"""
    print("=" * 60)
    print("测试 1: 基本调用")
    print("=" * 60)

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello, please introduce yourself briefly."},
        ],
        stream=False
    )

    print(f"模型回复: {response.choices[0].message.content}")
    print()


# ==================== 2. 思考模式 ====================
def test_reasoning_mode():
    """测试 DeepSeek 思考模式（deepseek-reasoner）"""
    print("=" * 60)
    print("测试 2: 思考模式")
    print("=" * 60)

    # Turn 1
    messages = [{"role": "user", "content": "9.11 and 9.8, which is greater?"}]
    print(f"用户问题 1: {messages[0]['content']}")

    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=messages,
        stream=True
    )

    reasoning_content = ""
    content = ""

    for chunk in response:
        if chunk.choices[0].delta.reasoning_content:
            reasoning_content += chunk.choices[0].delta.reasoning_content
        elif chunk.choices[0].delta.content:
            content += chunk.choices[0].delta.content

    print(f"\n思维链:\n{reasoning_content}")
    print(f"\n最终回答:\n{content}")

    # Turn 2 - 多轮对话
    messages.append({"role": "assistant", "content": content})
    messages.append({"role": "user", "content": "How many Rs are there in the word 'strawberry'?"})
    print(f"\n用户问题 2: {messages[-1]['content']}")

    response = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=messages,
        stream=True
    )

    reasoning_content = ""
    content = ""

    for chunk in response:
        if chunk.choices[0].delta.reasoning_content:
            reasoning_content += chunk.choices[0].delta.reasoning_content
        elif chunk.choices[0].delta.content:
            content += chunk.choices[0].delta.content

    print(f"\n思维链:\n{reasoning_content}")
    print(f"\n最终回答:\n{content}")
    print()


# ==================== 3. 工具调用 ====================
# 工具定义
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_date",
            "description": "Get the current date. You should call this first to know today's date before getting weather for relative dates like 'tomorrow'.",
            "parameters": {"type": "object", "properties": {}},
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather of a location for a specific date. Use get_date first to determine the current date if the user asks about relative dates like 'today' or 'tomorrow'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "The city name"},
                    "date": {"type": "string", "description": "The date in format YYYY-mm-dd"},
                },
                "required": ["location", "date"]
            },
        }
    },
]


# 模拟工具实现
def get_date_mock():
    """模拟获取当前日期"""
    return "2025-01-22"


def get_weather_mock(location: str, date: str):
    """模拟获取天气"""
    return f"{location} on {date}: Cloudy 7~13°C"


TOOL_CALL_MAP = {
    "get_date": get_date_mock,
    "get_weather": get_weather_mock
}


def clear_reasoning_content(messages):
    """清除历史消息中的 reasoning_content 以节省带宽"""
    for message in messages:
        if hasattr(message, 'reasoning_content'):
            message.reasoning_content = None


def run_turn(turn: int, messages: list, enable_thinking: bool = False):
    """
    运行一轮对话，处理可能的多次工具调用

    Args:
        turn: 当前轮次
        messages: 消息列表
        enable_thinking: 是否启用思考模式
    """
    sub_turn = 1

    while True:
        # 构建请求参数
        request_params = {
            "model": "deepseek-chat",
            "messages": messages,
            "tools": TOOLS,
        }

        # 如果启用思考模式
        if enable_thinking:
            request_params["extra_body"] = {"thinking": {"type": "enabled"}}

        response = client.chat.completions.create(**request_params)

        # 获取响应内容
        message = response.choices[0].message
        messages.append(message)

        reasoning_content = getattr(message, 'reasoning_content', None)
        content = message.content
        tool_calls = message.tool_calls

        print(f"\nTurn {turn}.{sub_turn}")
        if reasoning_content:
            print(f"思维链: {reasoning_content[:200]}..." if len(str(reasoning_content)) > 200 else f"思维链: {reasoning_content}")
        print(f"回复内容: {content}")
        print(f"工具调用: {tool_calls}")

        # 如果没有工具调用，说明模型已经得出最终答案
        if tool_calls is None:
            break

        # 执行工具调用
        for tool in tool_calls:
            tool_name = tool.function.name
            tool_args = json.loads(tool.function.arguments) if tool.function.arguments else {}
            tool_function = TOOL_CALL_MAP.get(tool_name)

            if tool_function:
                tool_result = tool_function(**tool_args)
                print(f"工具 {tool_name} 执行结果: {tool_result}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool.id,
                    "content": str(tool_result),
                })
            else:
                print(f"未知工具: {tool_name}")

        sub_turn += 1


def test_tool_calling():
    """测试 DeepSeek 工具调用"""
    print("=" * 60)
    print("测试 3: 工具调用")
    print("=" * 60)

    # Turn 1: 询问天气
    turn = 1
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. When the user asks about weather for relative dates like 'tomorrow' or 'today', you MUST first call get_date to get the current date, then call get_weather with the calculated date. Always use the tools available to you."
        },
        {
            "role": "user",
            "content": "How's the weather in Hangzhou tomorrow?"
        }
    ]
    print(f"\n用户问题: {messages[1]['content']}")
    run_turn(turn, messages, enable_thinking=False)

    # Turn 2: 继续询问
    turn = 2
    messages.append({
        "role": "user",
        "content": "What about Beijing?"
    })
    print(f"\n用户问题: {messages[-1]['content']}")

    # 清除历史消息中的 reasoning_content 以节省带宽
    clear_reasoning_content(messages)
    run_turn(turn, messages, enable_thinking=False)
    print()


def test_tool_calling_with_thinking():
    """测试 DeepSeek 工具调用 + 思考模式"""
    print("=" * 60)
    print("测试 3b: 工具调用 + 思考模式")
    print("=" * 60)

    messages = [{
        "role": "user",
        "content": "What's the weather in Shanghai tomorrow?"
    }]
    print(f"\n用户问题: {messages[0]['content']}")
    run_turn(1, messages, enable_thinking=True)
    print()


# ==================== 主函数 ====================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("DeepSeek API 测试")
    print("=" * 60 + "\n")

    try:
        # 测试 1: 基本调用
        test_basic_call()

        # 测试 2: 思考模式
        test_reasoning_mode()

        # 测试 3: 工具调用
        test_tool_calling()

        # 测试 3b: 工具调用 + 思考模式（可选）
        # test_tool_calling_with_thinking()

        print("=" * 60)
        print("所有测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"测试出错: {e}")
        raise
