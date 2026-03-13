#!/usr/bin/env python3
"""
验证真实DashScope API密钥
硬编码检查变量名，确保读取的是正确的32位密钥
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings

def verify_real_key():
    """验证真实API密钥"""
    print("=== 验证DashScope API密钥 ===")

    # 方法1: 直接从settings获取
    key_from_settings = settings.DASHSCOPE_API_KEY
    print(f"1. 从settings.DASHSCOPE_API_KEY获取:")
    print(f"   密钥: {key_from_settings}")
    print(f"   长度: {len(key_from_settings)}")

    # 方法2: 从环境变量获取
    key_from_env = os.getenv('DASHSCOPE_API_KEY')
    print(f"2. 从环境变量DASHSCOPE_API_KEY获取:")
    print(f"   密钥: {key_from_env}")
    print(f"   长度: {len(key_from_env) if key_from_env else 'None'}")

    # 方法3: 检查DASHVECTOR_API_KEY（对比）
    dashvector_key = settings.DASHVECTOR_API_KEY
    print(f"3. 对比settings.DASHVECTOR_API_KEY:")
    print(f"   密钥: {dashvector_key}")
    print(f"   长度: {len(dashvector_key) if dashvector_key else 'None'}")

    # 致命检查
    print("\n=== 致命检查 ===")
    if key_from_settings and len(key_from_settings) == 64:
        print("严重错误：settings.DASHSCOPE_API_KEY 长度是64位！")
        print("    这意味着你错误地读取了DASHVECTOR_API_KEY！")
        print("    请立即检查config.py中的变量名是否正确。")
        print("    程序立即停止。")
        return False

    if key_from_settings and len(key_from_settings) == 35:
        print("正确：settings.DASHSCOPE_API_KEY 长度是35位！")
        print(f"    密钥: {key_from_settings[:8]}...")
        print(f"    符合百炼平台API密钥格式（sk-前缀 + 32位十六进制）。")
        return True

    if not key_from_settings:
        print("警告：settings.DASHSCOPE_API_KEY 为空！")
        print("    请检查.env文件是否包含DASHSCOPE_API_KEY设置。")
        return False

    print(f"警告：密钥长度异常: {len(key_from_settings)} 位")
    print(f"    预期35位（百炼密钥，sk-前缀+32位十六进制）或64位（DashVector密钥）")
    return False

def test_embedding():
    """测试Embedding API"""
    print("\n=== 测试Embedding API ===")

    from openai import OpenAI

    api_key = settings.DASHSCOPE_API_KEY
    workspace_id = settings.DASHSCOPE_WORKSPACE_ID
    model = settings.DASHSCOPE_EMBEDDING_MODEL
    vector_dimension = settings.VECTOR_DIMENSION

    print(f"API密钥长度: {len(api_key)}")
    print(f"工作空间ID: {workspace_id}")
    print(f"Embedding模型: {model}")
    print(f"向量维度: {vector_dimension}")

    if not api_key:
        print("API密钥为空，无法测试")
        return False

    # 创建OpenAI客户端
    default_headers = {}
    if workspace_id:
        default_headers["X-DashScope-WorkSpace"] = workspace_id

    print(f"OpenAI客户端配置:")
    print(f"  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1")
    print(f"  default_headers: {default_headers}")

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_headers=default_headers
        )

        # 测试文本
        test_text = "你好，北京广播。"
        print(f"测试文本: '{test_text}'")

        # 调用embeddings.create
        print("正在调用 embeddings.create...")
        response = client.embeddings.create(
            model=model,
            input=test_text,
            dimensions=vector_dimension,
            encoding_format="float"
        )

        # 检查响应
        embedding = response.data[0].embedding
        print(f"Embedding API调用成功！")
        print(f"   向量维度: {len(embedding)}")
        print(f"   向量前5个值: {embedding[:5]}")
        print(f"   向量类型: {type(embedding[0])}")

        if len(embedding) == vector_dimension:
            print(f"验证通过: {len(embedding)} == {vector_dimension}")
            return True
        else:
            print(f"维度不匹配: {len(embedding)} != {vector_dimension}")
            return False

    except Exception as e:
        print(f"Embedding API调用失败: {e}")

        # 错误分析
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str:
            print("401 UNAUTHORIZED 错误")
            print("    可能原因:")
            print("    1. API密钥无效")
            print("    2. 密钥无权限访问指定工作空间")
            print("    3. 工作空间ID错误")
        elif "403" in error_str or "forbidden" in error_str:
            print("403 FORBIDDEN 错误")
            print("    可能原因:")
            print("    1. API密钥无权访问指定工作空间")
            print("    2. 工作空间ID错误")
            print("    3. 账户权限不足")
        elif "invalid api-key" in error_str:
            print("无效的API密钥")
            print("    请检查百炼控制台，获取正确的DashScope API密钥")
        return False

def main():
    """主函数"""
    print("开始验证DashScope API密钥...")

    # 步骤1：验证密钥
    if not verify_real_key():
        print("\n密钥验证失败，停止执行。")
        return 1

    # 步骤2：测试Embedding API
    print("\n" + "="*50)
    success = test_embedding()

    if success:
        print("\n所有验证通过，可以开始全流程处理！")
        return 0
    else:
        print("\nEmbedding API测试失败，请解决问题后再试。")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)