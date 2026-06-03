"""
Qwen VL (Vision-Language) API 测试脚本
测试功能：
1. 基础视觉理解（图片URL）
2. 视觉理解 + 思考模式
3. 多图理解
4. Base64 图片输入
"""

import base64
from openai import OpenAI

# API 配置
API_KEY = "sk-xxx"  # 替换为你的 API Key
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# 初始化客户端
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ==================== 1. 基础视觉理解 ====================
def test_basic_vision():
    """测试 Qwen VL 基础视觉理解（图片URL）"""
    print("=" * 60)
    print("测试 1: 基础视觉理解")
    print("=" * 60)

    response = client.chat.completions.create(
        model="qwen-vl-plus",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://img.alicdn.com/imgextra/i1/O1CN01gDEY8M1W114Hi3XcN_!!6000000002727-0-tps-1024-406.jpg"
                        },
                    },
                    {"type": "text", "text": "请描述这张图片的内容"},
                ],
            },
        ],
        stream=False,
    )

    print(f"模型回复: {response.choices[0].message.content}")
    print(f"Token 使用: {response.usage}")
    print()


# ==================== 2. 视觉理解 + 思考模式 ====================
def test_vision_with_thinking():
    """测试 Qwen VL 视觉理解 + 思考模式"""
    print("=" * 60)
    print("测试 2: 视觉理解 + 思考模式")
    print("=" * 60)

    reasoning_content = ""
    answer_content = ""
    is_answering = False

    response = client.chat.completions.create(
        model="qwen3-vl-plus",  # 使用 qwen3-vl 系列支持思考模式
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://img.alicdn.com/imgextra/i1/O1CN01gDEY8M1W114Hi3XcN_!!6000000002727-0-tps-1024-406.jpg"
                        },
                    },
                    {"type": "text", "text": "这道题怎么解答？"},
                ],
            },
        ],
        stream=True,
        extra_body={
            "enable_thinking": True,
            "thinking_budget": 4096,  # 限制思考 token 数
        },
        stream_options={"include_usage": True},
    )

    print("\n" + "=" * 20 + " 思考过程 " + "=" * 20 + "\n")

    for chunk in response:
        # 如果 chunk.choices 为空，则打印 usage
        if not chunk.choices:
            print(f"\n\nToken 使用: {chunk.usage}")
        else:
            delta = chunk.choices[0].delta

            # 打印思考过程
            if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                print(delta.reasoning_content, end="", flush=True)
                reasoning_content += delta.reasoning_content
            else:
                # 开始回复
                if delta.content and not is_answering:
                    print("\n\n" + "=" * 20 + " 完整回复 " + "=" * 20 + "\n")
                    is_answering = True
                # 打印回复过程
                if delta.content:
                    print(delta.content, end="", flush=True)
                    answer_content += delta.content

    print("\n")


# ==================== 3. 多图理解 ====================
def test_multi_image():
    """测试 Qwen VL 多图理解"""
    print("=" * 60)
    print("测试 3: 多图理解")
    print("=" * 60)

    response = client.chat.completions.create(
        model="qwen-vl-plus",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"
                        },
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/tiger.png"
                        },
                    },
                    {"type": "text", "text": "请比较这两张图片，描述它们的异同"},
                ],
            },
        ],
        stream=True,
    )

    print("模型回复: ", end="")
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")


# ==================== 4. Base64 图片输入 ====================
def test_base64_image():
    """测试 Qwen VL Base64 图片输入"""
    print("=" * 60)
    print("测试 4: Base64 图片输入")
    print("=" * 60)

    # 示例：从本地文件读取并转换为 base64
    # 这里使用一个简单的测试图片 URL 下载后转换
    import urllib.request

    # 下载测试图片
    test_image_url = "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"

    try:
        with urllib.request.urlopen(test_image_url) as response:
            image_data = response.read()
            base64_image = base64.b64encode(image_data).decode("utf-8")

        response = client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                        {"type": "text", "text": "请描述这张图片中的内容"},
                    ],
                },
            ],
            stream=False,
        )

        print(f"模型回复: {response.choices[0].message.content}")
        print(f"Token 使用: {response.usage}")

    except Exception as e:
        print(f"Base64 测试跳过（无法下载测试图片）: {e}")

    print()


# ==================== 5. 视觉理解 + 工具调用 ====================
def test_vision_with_tools():
    """测试 Qwen VL 视觉理解 + 工具调用"""
    print("=" * 60)
    print("测试 5: 视觉理解 + 工具调用")
    print("=" * 60)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_product",
                "description": "根据商品描述搜索商品信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product_name": {
                            "type": "string",
                            "description": "商品名称"
                        },
                        "category": {
                            "type": "string",
                            "description": "商品类别"
                        },
                    },
                    "required": ["product_name"],
                },
            },
        }
    ]

    response = client.chat.completions.create(
        model="qwen-vl-plus",
        messages=[
            {
                "role": "system",
                "content": "你是一个购物助手，可以识别图片中的商品并帮助用户搜索。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"
                        },
                    },
                    {"type": "text", "text": "帮我搜索图片中女孩穿的衣服"},
                ],
            },
        ],
        tools=tools,
        stream=False,
    )

    message = response.choices[0].message
    print(f"回复内容: {message.content}")
    print(f"工具调用: {message.tool_calls}")
    print()


# ==================== 主函数 ====================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Qwen VL (Vision-Language) API 测试")
    print("=" * 60 + "\n")

    try:
        # 测试 1: 基础视觉理解
        test_basic_vision()

        # 测试 2: 视觉理解 + 思考模式
        test_vision_with_thinking()

        # 测试 3: 多图理解
        test_multi_image()

        # 测试 4: Base64 图片输入
        test_base64_image()

        # 测试 5: 视觉理解 + 工具调用（可选）
        # test_vision_with_tools()

        print("=" * 60)
        print("所有测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"测试出错: {e}")
        raise
