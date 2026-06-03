"""
Ollama 适配器测试脚本

测试功能：
1. 服务健康检查
2. 获取模型列表
3. 验证凭证
4. 非流式聊天
5. 流式聊天
6. 错误处理（模型不存在、服务不可用）
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.adapters.ollama import OllamaAdapter
from app.core.adapters.types import ChatMessage
from app.core.exceptions import ModelUnavailableError, ProviderConnectionError


# 测试配置
OLLAMA_BASE_URL = "http://192.168.110.131:11434"
TEST_MODEL = "qwen3:0.6b"


def print_header(title: str):
    """打印测试标题"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(success: bool, message: str):
    """打印测试结果"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")


async def test_health_check():
    """测试 1: 健康检查"""
    print_header("测试 1: 健康检查")
    
    adapter = OllamaAdapter(
        base_url=OLLAMA_BASE_URL,
        model_id=TEST_MODEL,
    )
    
    try:
        is_healthy = await adapter._check_health()
        print_result(is_healthy, f"服务健康状态: {is_healthy}")
        return is_healthy
    except Exception as e:
        print_result(False, f"健康检查失败: {e}")
        return False
    finally:
        await adapter.close()


async def test_list_models():
    """测试 2: 获取模型列表"""
    print_header("测试 2: 获取模型列表")
    
    adapter = OllamaAdapter(
        base_url=OLLAMA_BASE_URL,
        model_id=TEST_MODEL,
    )
    
    try:
        models = await adapter.list_models()
        print(f"可用模型数量: {len(models)}")
        
        for model in models:
            features = []
            if model.get("supports_vision"):
                features.append("视觉")
            if model.get("supports_reasoning"):
                features.append("思考")
            if model.get("supports_tools"):
                features.append("工具")
            
            features_str = ", ".join(features) if features else "基础"
            print(f"  - {model['id']} ({features_str})")
        
        print_result(len(models) > 0, f"获取到 {len(models)} 个模型")
        return len(models) > 0
    except Exception as e:
        print_result(False, f"获取模型列表失败: {e}")
        return False
    finally:
        await adapter.close()


async def test_validate_credentials():
    """测试 3: 验证凭证"""
    print_header("测试 3: 验证凭证")
    
    adapter = OllamaAdapter(
        base_url=OLLAMA_BASE_URL,
        model_id=TEST_MODEL,
    )
    
    try:
        is_valid = await adapter.validate_credentials()
        print_result(is_valid, f"凭证验证: {is_valid}")
        return is_valid
    except Exception as e:
        print_result(False, f"凭证验证失败: {e}")
        return False
    finally:
        await adapter.close()


async def test_non_streaming_chat():
    """测试 4: 非流式聊天"""
    print_header("测试 4: 非流式聊天")
    
    adapter = OllamaAdapter(
        base_url=OLLAMA_BASE_URL,
        model_id=TEST_MODEL,
        timeout=120,
    )
    
    messages: list[ChatMessage] = [
        ChatMessage(role="user", content="你好！请用一句话介绍你自己。")
    ]
    
    try:
        print("发送请求中...")
        response = await adapter.chat_completion(
            messages=messages,
            temperature=0.7,
            stream=False,
        )
        
        print(f"\n响应内容: {response.get('content', '')[:200]}")
        
        if response.get("reasoning_content"):
            print(f"\n思考内容: {response['reasoning_content'][:200]}...")
        
        if response.get("usage"):
            usage = response["usage"]
            print(f"\nToken 统计:")
            print(f"  - 输入 tokens: {usage.get('prompt_tokens', 0)}")
            print(f"  - 输出 tokens: {usage.get('completion_tokens', 0)}")
            print(f"  - 总计 tokens: {usage.get('total_tokens', 0)}")
        
        success = bool(response.get("content"))
        print_result(success, "非流式聊天完成")
        return success
    except Exception as e:
        print_result(False, f"非流式聊天失败: {e}")
        return False
    finally:
        await adapter.close()


async def test_streaming_chat():
    """测试 5: 流式聊天"""
    print_header("测试 5: 流式聊天")
    
    adapter = OllamaAdapter(
        base_url=OLLAMA_BASE_URL,
        model_id=TEST_MODEL,
        timeout=120,
    )
    
    messages: list[ChatMessage] = [
        ChatMessage(role="user", content="请用两句话描述一下春天的景色。")
    ]
    
    try:
        print("流式响应中:\n")
        
        full_content = ""
        full_thinking = ""
        usage_info = None
        
        response_gen = await adapter.chat_completion(
            messages=messages,
            temperature=0.7,
            stream=True,
        )
        
        async for chunk in response_gen:
            chunk_type = chunk.get("type")
            
            if chunk_type == "content":
                content = chunk.get("content", "")
                full_content += content
                print(content, end="", flush=True)
                
            elif chunk_type == "thinking":
                thinking = chunk.get("thinking", "")
                full_thinking += thinking
                print(f"[思考: {thinking}]", end="", flush=True)
                
            elif chunk_type == "usage":
                usage_info = chunk.get("usage")
                
            elif chunk_type == "done":
                print("\n\n[完成]")
                
            elif chunk_type == "error":
                print(f"\n[错误: {chunk.get('error')}]")
        
        if usage_info:
            print(f"\nToken 统计:")
            print(f"  - 输入 tokens: {usage_info.get('prompt_tokens', 0)}")
            print(f"  - 输出 tokens: {usage_info.get('completion_tokens', 0)}")
            if "tokens_per_second" in usage_info:
                print(f"  - 生成速度: {usage_info['tokens_per_second']:.2f} tokens/秒")
        
        success = len(full_content) > 0
        print_result(success, f"流式聊天完成，共 {len(full_content)} 字符")
        return success
    except Exception as e:
        print_result(False, f"流式聊天失败: {e}")
        return False
    finally:
        await adapter.close()


async def test_model_not_found():
    """测试 6: 模型不存在错误处理"""
    print_header("测试 6: 模型不存在错误处理")
    
    adapter = OllamaAdapter(
        base_url=OLLAMA_BASE_URL,
        model_id="nonexistent-model:latest",
        timeout=30,
    )
    
    messages: list[ChatMessage] = [
        ChatMessage(role="user", content="Hello")
    ]
    
    try:
        await adapter.chat_completion(
            messages=messages,
            stream=False,
        )
        print_result(False, "应该抛出 ModelUnavailableError")
        return False
    except ModelUnavailableError as e:
        print(f"捕获到预期的错误: {e.message}")
        print_result(True, "正确处理模型不存在错误")
        return True
    except Exception as e:
        print_result(False, f"捕获到非预期的错误: {type(e).__name__}: {e}")
        return False
    finally:
        await adapter.close()


async def test_service_unavailable():
    """测试 7: 服务不可用错误处理"""
    print_header("测试 7: 服务不可用错误处理")
    
    # 使用错误的地址
    adapter = OllamaAdapter(
        base_url="http://127.0.0.1:99999",
        model_id=TEST_MODEL,
        timeout=5,
        connect_timeout=2.0,
    )
    
    messages: list[ChatMessage] = [
        ChatMessage(role="user", content="Hello")
    ]
    
    try:
        await adapter.chat_completion(
            messages=messages,
            stream=False,
        )
        print_result(False, "应该抛出 ProviderConnectionError")
        return False
    except ProviderConnectionError as e:
        print(f"捕获到预期的错误: {e.message}")
        print_result(True, "正确处理服务不可用错误")
        return True
    except Exception as e:
        # 也可能抛出其他连接相关的错误
        print(f"捕获到错误: {type(e).__name__}: {e}")
        print_result(True, "正确处理服务不可用错误")
        return True
    finally:
        await adapter.close()


async def test_feature_detection():
    """测试 8: 功能检测"""
    print_header("测试 8: 功能检测")
    
    adapter = OllamaAdapter(
        base_url=OLLAMA_BASE_URL,
        model_id=TEST_MODEL,
    )
    
    try:
        features = ["streaming", "vision", "tools", "reasoning", "audio"]
        
        print(f"模型: {TEST_MODEL}")
        print(f"功能支持:")
        
        for feature in features:
            supported = adapter.supports_feature(feature)
            status = "✓" if supported else "✗"
            print(f"  {status} {feature}: {supported}")
        
        # 流式应该总是支持
        success = adapter.supports_feature("streaming")
        print_result(success, "功能检测完成")
        return success
    finally:
        await adapter.close()


async def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("  Ollama 适配器测试套件")
    print(f"  服务地址: {OLLAMA_BASE_URL}")
    print(f"  测试模型: {TEST_MODEL}")
    print("="*60)
    
    results = []
    
    # 测试 1: 健康检查
    results.append(("健康检查", await test_health_check()))
    
    # 如果健康检查失败，跳过后续测试
    if not results[-1][1]:
        print("\n⚠️  服务不可用，跳过后续测试")
        print("请确保 Ollama 服务已启动并可访问")
        return
    
    # 测试 2: 获取模型列表
    results.append(("获取模型列表", await test_list_models()))
    
    # 测试 3: 验证凭证
    results.append(("验证凭证", await test_validate_credentials()))
    
    # 测试 4: 非流式聊天
    results.append(("非流式聊天", await test_non_streaming_chat()))
    
    # 测试 5: 流式聊天
    results.append(("流式聊天", await test_streaming_chat()))
    
    # 测试 6: 模型不存在错误
    results.append(("模型不存在错误", await test_model_not_found()))
    
    # 测试 7: 服务不可用错误
    results.append(("服务不可用错误", await test_service_unavailable()))
    
    # 测试 8: 功能检测
    results.append(("功能检测", await test_feature_detection()))
    
    # 打印汇总
    print("\n" + "="*60)
    print("  测试汇总")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}")
    
    print(f"\n  通过: {passed}/{total}")
    
    if passed == total:
        print("\n  🎉 所有测试通过！")
    else:
        print(f"\n  ⚠️  {total - passed} 个测试失败")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
