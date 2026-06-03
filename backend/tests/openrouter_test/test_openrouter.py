"""
OpenRouter API 测试脚本
测试功能：
1. 基础对话
2. 推理模式（Reasoning）
3. 多轮对话 + 推理模式
4. 视觉理解
5. 图像生成
6. 流式响应
7. 多模型切换
"""

from openai import OpenAI

# API 配置
API_KEY = "sk-or-v1-"
BASE_URL = "https://openrouter.ai/api/v1"

# 初始化客户端
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


# ==================== 1. 基础对话 ====================
def test_basic_chat():
    """测试 OpenRouter 基础对话"""
    print("=" * 60)
    print("测试 1: 基础对话")
    print("=" * 60)

    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",  # 使用 Gemini Flash 模型
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, please introduce yourself briefly."},
        ],
        stream=False,
    )

    print(f"模型: {response.model}")
    print(f"回复: {response.choices[0].message.content}")
    if response.usage:
        print(f"Token 使用: {response.usage}")
    print()


# ==================== 2. 推理模式 ====================
def test_reasoning_mode():
    """测试 OpenRouter 推理模式"""
    print("=" * 60)
    print("测试 2: 推理模式")
    print("=" * 60)

    response = client.chat.completions.create(
        model="google/gemini-2.5-pro-preview",  # 使用支持推理的模型
        messages=[
            {
                "role": "user",
                "content": "How many r's are in the word 'strawberry'?"
            }
        ],
        extra_body={"reasoning": {"enabled": True}},
    )

    message = response.choices[0].message
    print(f"回复: {message.content}")

    # 检查是否有推理详情
    reasoning_details = getattr(message, "reasoning_details", None)
    if reasoning_details:
        print(f"\n推理详情: {reasoning_details}")
    print()


# ==================== 3. 多轮对话 + 推理模式 ====================
def test_multi_turn_reasoning():
    """测试 OpenRouter 多轮对话 + 推理模式"""
    print("=" * 60)
    print("测试 3: 多轮对话 + 推理模式")
    print("=" * 60)

    # 第一轮对话
    print("第一轮对话:")
    response = client.chat.completions.create(
        model="google/gemini-2.5-pro-preview",
        messages=[
            {
                "role": "user",
                "content": "How many r's are in the word 'strawberry'?"
            }
        ],
        extra_body={"reasoning": {"enabled": True}},
    )

    first_message = response.choices[0].message
    print(f"回复: {first_message.content}")

    # 构建第二轮消息，保留推理详情
    reasoning_details = getattr(first_message, "reasoning_details", None)
    messages = [
        {"role": "user", "content": "How many r's are in the word 'strawberry'?"},
        {
            "role": "assistant",
            "content": first_message.content,
        },
        {"role": "user", "content": "Are you sure? Think carefully."}
    ]

    # 如果有推理详情，添加到 assistant 消息中
    if reasoning_details:
        messages[1]["reasoning_details"] = reasoning_details

    # 第二轮对话
    print("\n第二轮对话:")
    response2 = client.chat.completions.create(
        model="google/gemini-2.5-pro-preview",
        messages=messages,
        extra_body={"reasoning": {"enabled": True}},
    )

    print(f"回复: {response2.choices[0].message.content}")
    print()


# ==================== 4. 视觉理解 ====================
def test_vision():
    """测试 OpenRouter 视觉理解"""
    print("=" * 60)
    print("测试 4: 视觉理解")
    print("=" * 60)

    # 使用阿里云 OSS 的稳定测试图片
    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",  # 使用支持视觉的模型
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://dashscope.oss-cn-beijing.aliyuncs.com/images/dog_and_girl.jpeg"
                        }
                    },
                    {
                        "type": "text",
                        "text": "What's in this image? Describe it in detail."
                    }
                ]
            }
        ],
        stream=False,
    )

    print(f"回复: {response.choices[0].message.content}")
    print()


# ==================== 5. 图像生成 ====================
def test_image_generation():
    """测试 OpenRouter 图像生成"""
    print("=" * 60)
    print("测试 5: 图像生成")
    print("=" * 60)

    try:
        response = client.chat.completions.create(
            model="google/gemini-3-pro-image-preview",  # 使用支持图像生成的模型
            messages=[
                {
                    "role": "user",
                    "content": "Generate a beautiful sunset over mountains"
                }
            ],
            extra_body={"modalities": ["image", "text"]},
        )

        message = response.choices[0].message
        print(f"文本回复: {message.content}")

        # 检查是否有生成的图像
        images = getattr(message, "images", None)
        if images:
            for i, image in enumerate(images):
                image_url = image.get("image_url", {}).get("url", "")
                print(f"生成图像 {i + 1}: {image_url[:80]}..." if len(image_url) > 80 else f"生成图像 {i + 1}: {image_url}")
        else:
            print("未生成图像（模型可能不支持图像生成）")

    except Exception as e:
        print(f"图像生成测试跳过: {e}")

    print()


# ==================== 6. 流式响应 ====================
def test_streaming():
    """测试 OpenRouter 流式响应"""
    print("=" * 60)
    print("测试 6: 流式响应")
    print("=" * 60)

    response = client.chat.completions.create(
        model="google/gemini-2.0-flash-001",
        messages=[
            {"role": "user", "content": "Write a short poem about coding."}
        ],
        stream=True,
    )

    print("流式回复: ", end="")
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")


# ==================== 7. 多模型切换 ====================
def test_model_switching():
    """测试 OpenRouter 多模型切换"""
    print("=" * 60)
    print("测试 7: 多模型切换")
    print("=" * 60)

    # 测试不同模型
    models = [
        "google/gemini-2.0-flash-001",
        "anthropic/claude-3.5-haiku",
        "openai/gpt-4o-mini",
        "meta-llama/llama-3.3-70b-instruct",
    ]

    question = "What is 2 + 2? Answer in one word."

    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": question}],
                max_tokens=50,
            )
            print(f"{model}: {response.choices[0].message.content.strip()}")
        except Exception as e:
            print(f"{model}: 错误 - {e}")

    print()


# ==================== 8. 流式推理模式 ====================
def test_streaming_reasoning():
    """测试 OpenRouter 流式推理模式"""
    print("=" * 60)
    print("测试 8: 流式推理模式")
    print("=" * 60)

    response = client.chat.completions.create(
        model="google/gemini-2.5-pro-preview",
        messages=[
            {
                "role": "user",
                "content": "What is 15 * 17? Show your reasoning."
            }
        ],
        stream=True,
        extra_body={"reasoning": {"enabled": True}},
    )

    reasoning_content = ""
    answer_content = ""
    current_type = None

    print("推理过程:")
    for chunk in response:
        if not chunk.choices:
            continue

        delta = chunk.choices[0].delta

        # 检查是否有推理内容
        reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if reasoning:
            if current_type != "reasoning":
                current_type = "reasoning"
            print(reasoning, end="", flush=True)
            reasoning_content += reasoning
        elif delta.content:
            if current_type != "content":
                if current_type == "reasoning":
                    print("\n\n回答:")
                current_type = "content"
            print(delta.content, end="", flush=True)
            answer_content += delta.content

    print("\n")


# ==================== 主函数 ====================
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("OpenRouter API 测试")
    print("=" * 60 + "\n")

    try:
        # 测试 1: 基础对话
        test_basic_chat()

        # 测试 2: 推理模式
        test_reasoning_mode()

        # 测试 3: 多轮对话 + 推理模式
        test_multi_turn_reasoning()

        # 测试 4: 视觉理解
        test_vision()

        # 测试 5: 图像生成（可选，部分模型支持）
        # test_image_generation()

        # 测试 6: 流式响应
        test_streaming()

        # 测试 7: 多模型切换
        test_model_switching()

        # 测试 8: 流式推理模式
        # test_streaming_reasoning()

        print("=" * 60)
        print("所有测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"测试出错: {e}")
        raise
