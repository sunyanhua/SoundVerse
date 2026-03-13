#!/usr/bin/env python3
"""
统计DashVector集合中的向量数量
"""
import asyncio
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from services.search_service import vector_collection

async def main():
    if not vector_collection:
        print("DashVector集合未初始化")
        return

    try:
        # 使用scan获取总数（限制为1，但返回总数）
        result = vector_collection.scan(limit=1)
        print(f"DashVector集合名称: {vector_collection.name}")
        print(f"向量总数: {result.total}")
    except Exception as e:
        print(f"获取向量数量失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())