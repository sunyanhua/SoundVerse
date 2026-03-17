#!/usr/bin/env python3
"""
简化的向量配置检查脚本
避免复杂的ORM关系问题
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# 设置项目根目录
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 设置容器内的数据库URL（如果未设置）
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config import settings

print("=== 向量配置检查 ===\n")

async def check_vector_dimensions():
    """检查向量维度"""
    print("1. 检查数据库向量维度...")

    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 查询总数
        result = await session.execute(text("SELECT COUNT(*) FROM audio_segments"))
        total = result.scalar()
        print(f"   音频片段总数: {total}")

        # 查询有向量的数量
        result = await session.execute(text("""
            SELECT COUNT(*) FROM audio_segments
            WHERE vector IS NOT NULL AND review_status = 'approved'
        """))
        with_vectors = result.scalar()
        print(f"   有向量的片段数: {with_vectors}")
        print(f"   向量覆盖率: {with_vectors/total*100:.1f}%" if total > 0 else "   向量覆盖率: N/A")

        # 抽样检查向量维度
        result = await session.execute(text("""
            SELECT id, transcription, vector
            FROM audio_segments
            WHERE vector IS NOT NULL AND review_status = 'approved'
            LIMIT 5
        """))

        samples = result.fetchall()
        print(f"\n   样本检查 (前{len(samples)}个):")

        expected_dim = settings.VECTOR_DIMENSION
        issues = []

        for i, (seg_id, transcription, vector_json) in enumerate(samples):
            try:
                vector = json.loads(vector_json) if isinstance(vector_json, str) else vector_json
                dim = len(vector) if vector else 0

                status = "✅" if dim == expected_dim else "❌"
                transcription_preview = (transcription[:50] + "...") if transcription else "无文本"

                print(f"   {i+1}. {status} ID: {seg_id}")
                print(f"      维度: {dim} (期望: {expected_dim})")
                print(f"      文本: {transcription_preview}")

                if dim != expected_dim:
                    issues.append(f"片段 {seg_id} 维度错误: {dim} ≠ {expected_dim}")

            except Exception as e:
                print(f"   {i+1}. ❌ ID: {seg_id} - 解析失败: {str(e)}")
                issues.append(f"片段 {seg_id} 向量解析失败")

        return {
            "total": total,
            "with_vectors": with_vectors,
            "coverage": with_vectors/total if total > 0 else 0,
            "issues": issues
        }

async def check_dashvector():
    """检查DashVector配置"""
    print("\n2. 检查DashVector配置...")

    results = {
        "enabled": False,
        "api_key": bool(settings.DASHVECTOR_API_KEY),
        "endpoint": bool(settings.DASHVECTOR_ENDPOINT),
        "collection": settings.DASHVECTOR_COLLECTION,
        "connected": False,
        "error": None,
        "collection_info": {}
    }

    if not settings.DASHVECTOR_API_KEY or not settings.DASHVECTOR_ENDPOINT:
        results["error"] = "DashVector API Key或Endpoint未配置"
        print(f"   ❌ {results['error']}")
        return results

    results["enabled"] = True
    print(f"   ✅ API Key: 已配置")
    print(f"   ✅ Endpoint: {settings.DASHVECTOR_ENDPOINT}")
    print(f"   ✅ Collection: {settings.DASHVECTOR_COLLECTION}")

    try:
        import dashvector

        client = dashvector.Client(
            api_key=settings.DASHVECTOR_API_KEY,
            endpoint=settings.DASHVECTOR_ENDPOINT
        )

        collection = client.get(settings.DASHVECTOR_COLLECTION)

        if collection:
            results["connected"] = True
            print(f"   ✅ 连接成功")

            # 尝试获取统计信息
            try:
                stats = collection.stats()

                # 尝试提取信息
                info = {}

                # 文档数
                if hasattr(stats, 'total_doc_count'):
                    info["total_docs"] = stats.total_doc_count
                elif hasattr(stats, 'output') and hasattr(stats.output, 'total_doc_count'):
                    info["total_docs"] = stats.output.total_doc_count

                # 度量方式
                if hasattr(stats, 'metric'):
                    info["metric"] = stats.metric
                elif hasattr(stats, 'output') and hasattr(stats.output, 'metric'):
                    info["metric"] = stats.output.metric

                # 维度
                if hasattr(stats, 'dimension'):
                    info["dimension"] = stats.dimension
                elif hasattr(stats, 'output') and hasattr(stats.output, 'dimension'):
                    info["dimension"] = stats.output.dimension

                results["collection_info"] = info

                if info:
                    print(f"   集合信息:")
                    for key, value in info.items():
                        print(f"     {key}: {value}")

            except Exception as e:
                results["error"] = f"获取集合信息失败: {str(e)}"
                print(f"   ⚠️  获取集合信息失败: {str(e)}")

        else:
            results["error"] = f"集合 {settings.DASHVECTOR_COLLECTION} 不存在"
            print(f"   ❌ {results['error']}")

    except ImportError:
        results["error"] = "dashvector库未安装"
        print(f"   ❌ {results['error']}")
    except Exception as e:
        results["error"] = f"连接DashVector失败: {str(e)}"
        print(f"   ❌ {results['error']}")

    return results

async def check_nlp_config():
    """检查NLP配置"""
    print("\n3. 检查NLP服务配置...")

    results = {
        "embedding_model": settings.DASHSCOPE_EMBEDDING_MODEL,
        "api_key": bool(settings.DASHSCOPE_API_KEY),
        "vector_dimension": settings.VECTOR_DIMENSION,
        "dashvector_dimension": settings.DASHVECTOR_COLLECTION_DIMENSION,
        "match": settings.VECTOR_DIMENSION == settings.DASHVECTOR_COLLECTION_DIMENSION
    }

    print(f"   嵌入模型: {results['embedding_model']}")
    print(f"   API Key: {'✅ 已配置' if results['api_key'] else '❌ 未配置'}")
    print(f"   向量维度: {results['vector_dimension']}")
    print(f"   DashVector集合维度: {results['dashvector_dimension']}")
    print(f"   维度匹配: {'✅' if results['match'] else '❌'}")

    if not results['match']:
        print(f"   ⚠️  警告: 向量生成维度({results['vector_dimension']})与集合维度({results['dashvector_dimension']})不匹配!")

    return results

async def test_search():
    """测试向量搜索"""
    print("\n4. 测试向量搜索...")

    try:
        from services.search_service import search_service

        # 初始化搜索服务
        await search_service.initialize()

        # 获取索引统计
        stats = await search_service.get_index_stats()

        print(f"   搜索引擎: {stats.get('engine', '未知')}")
        print(f"   索引片段数: {stats.get('total_segments', 0)}")
        print(f"   向量维度: {stats.get('vector_dimension', '未知')}")

        if stats.get('engine') == 'dashvector':
            print(f"   集合名称: {stats.get('collection_name', '未知')}")
            print(f"   Namespace: {stats.get('namespace', '未知')}")

        # 测试简单搜索
        test_query = "测试搜索"
        results = await search_service.search_by_text(test_query, top_k=3, similarity_threshold=0.0)

        print(f"   搜索测试查询: '{test_query}'")
        print(f"   返回结果数: {len(results)}")

        if results:
            print(f"   前3个结果:")
            for i, (seg_id, similarity) in enumerate(results[:3]):
                print(f"     {i+1}. 相似度: {similarity:.4f} | ID: {seg_id}")

        return {"stats": stats, "search_test_passed": len(results) > 0}

    except Exception as e:
        print(f"   ❌ 搜索测试失败: {str(e)}")
        return {"error": str(e), "search_test_passed": False}

async def main():
    """主函数"""
    # 设置编码
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    try:
        # 检查向量维度
        vector_results = await check_vector_dimensions()

        # 检查DashVector
        dashvector_results = await check_dashvector()

        # 检查NLP配置
        nlp_results = await check_nlp_config()

        # 测试搜索
        search_results = await test_search()

        # 总结
        print("\n" + "="*80)
        print("检查结果总结")
        print("="*80)

        issues = []

        # 向量覆盖率
        if vector_results["total"] > 0 and vector_results["coverage"] < 0.9:
            issues.append(f"向量覆盖率较低: {vector_results['coverage']*100:.1f}%")

        # 向量维度问题
        if vector_results["issues"]:
            issues.extend(vector_results["issues"])

        # DashVector连接
        if not dashvector_results.get("connected"):
            issues.append(f"DashVector连接失败: {dashvector_results.get('error', '未知错误')}")

        # 维度匹配
        if not nlp_results["match"]:
            issues.append(f"向量维度不匹配: 生成{ nlp_results['vector_dimension']} vs 集合{ nlp_results['dashvector_dimension']}")

        # 搜索测试
        if not search_results.get("search_test_passed"):
            issues.append("向量搜索测试失败")

        if issues:
            print("\n⚠️ 发现的问题:")
            for issue in issues:
                print(f"  • {issue}")
        else:
            print("\n✅ 所有检查通过!")

        # 建议
        print("\n📋 建议:")

        if vector_results["issues"]:
            print("1. 修复向量维度问题:")
            print("   - 重新生成维度错误的向量")
            print("   - 检查向量生成服务配置")

        if not dashvector_results.get("connected"):
            print("2. 修复DashVector连接:")
            print("   - 验证API Key和Endpoint")
            print("   - 检查网络连接")
            print("   - 确认DashVector服务已激活")

        if not nlp_results["match"]:
            print("3. 修复维度不匹配:")
            print("   - 更新DashVector集合维度配置")
            print("   - 或调整向量生成维度配置")

        if not search_results.get("search_test_passed"):
            print("4. 修复搜索服务:")
            print("   - 检查搜索服务初始化")
            print("   - 验证向量索引同步")

        print("\n✅ 检查完成")
        return 0

    except Exception as e:
        print(f"\n❌ 检查过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))