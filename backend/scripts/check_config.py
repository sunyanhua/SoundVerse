#!/usr/bin/env python3
"""
检查配置加载
"""
import os
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 打印环境变量
print("=== Environment Variables ===")
print(f"DATABASE_URL: {os.environ.get('DATABASE_URL')}")
print(f"DASHVECTOR_API_KEY: {'*'*20 if os.environ.get('DASHVECTOR_API_KEY') else 'Not set'}")
print(f"DASHVECTOR_ENDPOINT: {os.environ.get('DASHVECTOR_ENDPOINT')}")

# 加载配置
from config import settings

print("\n=== Settings from config.py ===")
print(f"DASHVECTOR_API_KEY: {'*'*20 if settings.DASHVECTOR_API_KEY else 'Not set'}")
print(f"DASHVECTOR_ENDPOINT: {settings.DASHVECTOR_ENDPOINT}")
print(f"DASHVECTOR_COLLECTION_DIMENSION: {settings.DASHVECTOR_COLLECTION_DIMENSION}")
print(f"VECTOR_DIMENSION: {settings.VECTOR_DIMENSION}")
print(f"DASHSCOPE_EMBEDDING_MODEL: {settings.DASHSCOPE_EMBEDDING_MODEL}")

# 检查.env文件
env_path = Path(__file__).parent.parent / ".env"
print(f"\n=== .env file exists: {env_path.exists()} ===")
if env_path.exists():
    with open(env_path, 'r') as f:
        content = f.read()
        # 只显示相关行
        lines = content.split('\n')
        for line in lines:
            if 'DASHVECTOR' in line or 'DASHSCOPE' in line or 'VECTOR' in line:
                print(f"  {line}")