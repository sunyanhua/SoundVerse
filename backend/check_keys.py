#!/usr/bin/env python3
"""
验证双钥匙体系：检查DashScope和DashVector API密钥是否正确加载
"""
import os
import sys
from config import settings

def main():
    print("=== 双钥匙体系验证 ===\n")

    # 获取系统环境变量
    env_dashscope = os.getenv('DASHSCOPE_API_KEY')
    env_dashvector = os.getenv('DASHVECTOR_API_KEY')

    # 获取Settings加载的值
    settings_dashscope = settings.DASHSCOPE_API_KEY
    settings_dashvector = settings.DASHVECTOR_API_KEY

    # 显示密钥信息（部分）
    def format_key(key):
        if not key:
            return "None"
        if len(key) > 10:
            return f"{key[:10]}... ({len(key)} chars)"
        return f"{key} ({len(key)} chars)"

    print("1. DashScope API密钥（百炼平台 - 用于文本向量化）:")
    print(f"   系统环境变量: {format_key(env_dashscope)}")
    print(f"   Settings加载: {format_key(settings_dashscope)}")

    print("\n2. DashVector API密钥（向量检索服务 - 用于向量存储）:")
    print(f"   系统环境变量: {format_key(env_dashvector)}")
    print(f"   Settings加载: {format_key(settings_dashvector)}")

    print("\n3. 其他关键配置:")
    print(f"   嵌入模型: {settings.DASHSCOPE_EMBEDDING_MODEL}")
    print(f"   向量维度: {settings.VECTOR_DIMENSION}")
    print(f"   DashVector端点: {settings.DASHVECTOR_ENDPOINT}")
    print(f"   DashVector集合: {settings.DASHVECTOR_COLLECTION}")
    print(f"   DashVector命名空间: {settings.DASHVECTOR_NAMESPACE}")

    print("\n=== 验证结果 ===")

    # 验证DashScope密钥
    dashscope_valid = settings_dashscope and len(settings_dashscope) > 20
    dashscope_message = "[OK]" if dashscope_valid else "[ERROR]"
    print(f"DashScope密钥: {dashscope_message}")

    # 验证DashVector密钥
    dashvector_valid = settings_dashvector and len(settings_dashvector) > 20
    dashvector_message = "[OK]" if dashvector_valid else "[ERROR]"
    print(f"DashVector密钥: {dashvector_message}")

    # 特别检查：确保两个密钥不同
    different_keys = settings_dashscope != settings_dashvector
    different_message = "[OK]" if different_keys else "[ERROR]"
    print(f"双钥匙不同: {different_message}")

    # 检查DashVector密钥是否为64位（典型的DashVector密钥长度）
    is_64_chars = settings_dashvector and len(settings_dashvector) == 64
    length_message = "[OK]" if is_64_chars else "[WARNING]"
    print(f"DashVector密钥长度64位: {length_message}")

    if not dashscope_valid or not dashvector_valid:
        print("\n[ERROR] 密钥验证失败！请检查.env文件配置。")
        sys.exit(1)

    if not different_keys:
        print("\n[ERROR] 两个API密钥相同！这是错误的配置。")
        print("DASHSCOPE_API_KEY 应该是百炼平台的密钥")
        print("DASHVECTOR_API_KEY 应该是DashVector的密钥")
        sys.exit(1)

    print("\n[SUCCESS] 双钥匙体系验证通过！")
    return 0

if __name__ == "__main__":
    sys.exit(main())