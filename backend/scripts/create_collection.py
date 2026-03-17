#!/usr/bin/env python3
"""
创建DashVector集合
"""
import sys
import os
from pathlib import Path

# 设置项目根目录
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings

print("=== 创建DashVector集合 ===\n")

def create_collection():
    """创建DashVector集合"""
    try:
        import dashvector

        print(f"API Key: {'已配置' if settings.DASHVECTOR_API_KEY else '未配置'}")
        print(f"Endpoint: {settings.DASHVECTOR_ENDPOINT}")
        print(f"Collection: {settings.DASHVECTOR_COLLECTION}")
        print(f"Dimension: {settings.DASHVECTOR_COLLECTION_DIMENSION}")

        # 创建客户端
        client = dashvector.Client(
            api_key=settings.DASHVECTOR_API_KEY,
            endpoint=settings.DASHVECTOR_ENDPOINT
        )

        collection_name = settings.DASHVECTOR_COLLECTION

        # 检查集合是否存在
        existing = client.get(collection_name)
        if existing:
            print(f"\n✅ 集合已存在: {collection_name}")
            return True

        # 创建新集合
        print(f"\n创建新集合: {collection_name}...")
        result = client.create(
            name=collection_name,
            dimension=settings.DASHVECTOR_COLLECTION_DIMENSION,
            metric='cosine'
        )

        if result:
            print(f"✅ 集合创建请求成功: {collection_name}")

            # 验证集合
            collection = client.get(collection_name)
            if collection:
                print(f"✅ 集合验证成功: {collection_name}")
                return True
            else:
                print(f"❌ 无法获取集合对象: {collection_name}")
                return False
        else:
            print(f"❌ 集合创建失败: {collection_name}")
            return False

    except Exception as e:
        print(f"❌ 创建集合时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_collection()
    sys.exit(0 if success else 1)