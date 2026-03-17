#!/usr/bin/env python3
"""
向量配置验证脚本
验证向量生成和检索服务的配置状态

功能：
1. 检查数据库中音频片段的向量维度
2. 验证DashVector服务连接和集合配置
3. 检查向量生成模型配置
4. 诊断可能的问题

用法：
docker-compose exec api python scripts/verify_vector_config.py
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# 设置项目根目录
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 设置容器内的数据库URL（如果未设置）
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

import shared.database.session as db_session
from shared.models.audio import AudioSegment
from shared.database.session import init_db
from config import settings

print("=== 向量配置验证 ===\n")

async def check_database_vectors() -> Dict[str, Any]:
    """
    检查数据库中的向量配置
    """
    results = {
        "total_segments": 0,
        "segments_with_vectors": 0,
        "vector_dimensions": [],
        "vector_quality": {
            "valid_dimensions": 0,
            "invalid_dimensions": 0,
            "null_vectors": 0,
            "wrong_dimension": 0
        },
        "sample_vectors": []
    }

    async with db_session.async_session_maker() as db:
        # 统计总数
        stmt_total = select(func.count(AudioSegment.id))
        total_result = await db.execute(stmt_total)
        results["total_segments"] = total_result.scalar()

        # 统计有向量的片段
        stmt_with_vectors = select(func.count(AudioSegment.id)).where(
            AudioSegment.vector.is_not(None),
            AudioSegment.review_status == "approved"
        )
        vector_result = await db.execute(stmt_with_vectors)
        results["segments_with_vectors"] = vector_result.scalar()

        # 抽样检查向量维度
        stmt_sample = select(AudioSegment).where(
            AudioSegment.vector.is_not(None),
            AudioSegment.review_status == "approved"
        ).limit(10)

        sample_result = await db.execute(stmt_sample)
        segments = sample_result.scalars().all()

        expected_dimension = settings.VECTOR_DIMENSION
        for i, segment in enumerate(segments):
            if i >= 5:  # 只检查前5个样本
                break

            vector = segment.vector
            if vector:
                dimension = len(vector)
                results["vector_dimensions"].append(dimension)

                # 检查维度是否正确
                if dimension == expected_dimension:
                    results["vector_quality"]["valid_dimensions"] += 1
                else:
                    results["vector_quality"]["wrong_dimension"] += 1

                # 保存样本信息
                sample_info = {
                    "id": segment.id,
                    "transcription_preview": segment.transcription[:50] if segment.transcription else None,
                    "vector_dimension": dimension,
                    "expected_dimension": expected_dimension,
                    "dimension_match": dimension == expected_dimension
                }
                results["sample_vectors"].append(sample_info)
            else:
                results["vector_quality"]["null_vectors"] += 1

    return results

async def check_dashvector_config() -> Dict[str, Any]:
    """
    检查DashVector配置
    """
    results = {
        "dashvector_enabled": False,
        "api_key_configured": False,
        "endpoint_configured": False,
        "collection_configured": False,
        "collection_info": None,
        "connection_test": False,
        "error": None
    }

    try:
        # 检查配置
        results["dashvector_enabled"] = bool(settings.DASHVECTOR_API_KEY and settings.DASHVECTOR_ENDPOINT)
        results["api_key_configured"] = bool(settings.DASHVECTOR_API_KEY)
        results["endpoint_configured"] = bool(settings.DASHVECTOR_ENDPOINT)
        results["collection_configured"] = bool(settings.DASHVECTOR_COLLECTION)

        if not results["dashvector_enabled"]:
            results["error"] = "DashVector未启用或配置不全"
            return results

        # 尝试连接DashVector
        try:
            import dashvector

            # 初始化客户端
            client = dashvector.Client(
                api_key=settings.DASHVECTOR_API_KEY,
                endpoint=settings.DASHVECTOR_ENDPOINT
            )

            # 获取集合
            collection_name = settings.DASHVECTOR_COLLECTION
            collection = client.get(collection_name)

            if collection:
                results["connection_test"] = True

                # 获取集合信息
                try:
                    stats = collection.stats()

                    # 尝试获取各种可能的属性
                    collection_info = {}

                    # 尝试获取文档数
                    total_docs = 0
                    if hasattr(stats, 'total_doc_count'):
                        total_docs = stats.total_doc_count
                    elif hasattr(stats, 'output') and hasattr(stats.output, 'total_doc_count'):
                        total_docs = stats.output.total_doc_count
                    elif isinstance(stats, dict) and 'total_doc_count' in stats:
                        total_docs = stats['total_doc_count']

                    collection_info["total_docs"] = total_docs

                    # 尝试获取度量方式
                    metric = "unknown"
                    if hasattr(stats, 'metric'):
                        metric = stats.metric
                    elif hasattr(stats, 'output') and hasattr(stats.output, 'metric'):
                        metric = stats.output.metric
                    elif isinstance(stats, dict) and 'metric' in stats:
                        metric = stats['metric']

                    collection_info["metric"] = metric

                    # 获取维度
                    dimension = 0
                    if hasattr(stats, 'dimension'):
                        dimension = stats.dimension
                    elif hasattr(stats, 'output') and hasattr(stats.output, 'dimension'):
                        dimension = stats.output.dimension
                    elif isinstance(stats, dict) and 'dimension' in stats:
                        dimension = stats['dimension']

                    collection_info["dimension"] = dimension

                    results["collection_info"] = collection_info

                except Exception as e:
                    results["collection_info"] = {"error": f"获取集合统计失败: {str(e)}"}

            else:
                results["error"] = f"集合 {collection_name} 不存在"

        except ImportError:
            results["error"] = "dashvector库未安装"
        except Exception as e:
            results["error"] = f"连接DashVector失败: {str(e)}"

    except Exception as e:
        results["error"] = f"检查配置时出错: {str(e)}"

    return results

async def check_nlp_service() -> Dict[str, Any]:
    """
    检查NLP服务配置
    """
    results = {
        "embedding_model": settings.DASHSCOPE_EMBEDDING_MODEL,
        "api_key_configured": bool(settings.DASHSCOPE_API_KEY),
        "vector_dimension": settings.VECTOR_DIMENSION,
        "dashvector_collection_dimension": settings.DASHVECTOR_COLLECTION_DIMENSION,
        "dimension_match": settings.VECTOR_DIMENSION == settings.DASHVECTOR_COLLECTION_DIMENSION
    }

    return results

async def test_vector_search(audio_id: str) -> Dict[str, Any]:
    """
    测试特定音频片段的向量搜索
    """
    results = {
        "audio_id": audio_id,
        "found_in_database": False,
        "has_vector": False,
        "vector_dimension": None,
        "search_results": None,
        "self_similarity": None,
        "search_test_passed": False
    }

    try:
        # 查询音频片段
        async with db_session.async_session_maker() as db:
            stmt = select(AudioSegment).where(AudioSegment.id == audio_id)
            result = await db.execute(stmt)
            segment = result.scalar_one_or_none()

            if segment:
                results["found_in_database"] = True
                results["has_vector"] = segment.vector is not None
                if segment.vector:
                    results["vector_dimension"] = len(segment.vector)

        # 使用原始转录文本进行搜索测试
        if segment and segment.transcription:
            from services.search_service import search_audio_segments_by_text

            search_results = await search_audio_segments_by_text(
                segment.transcription,
                top_k=5,
                similarity_threshold=0.0
            )

            results["search_results"] = search_results

            # 查找自相似度
            for seg_id, similarity in search_results:
                if seg_id == audio_id:
                    results["self_similarity"] = similarity
                    results["search_test_passed"] = True
                    break

    except Exception as e:
        results["error"] = f"搜索测试失败: {str(e)}"

    return results

async def main():
    """主函数"""
    # 设置编码
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("1. 初始化数据库连接...")
    await init_db()

    print("2. 检查数据库向量配置...")
    db_results = await check_database_vectors()

    print("3. 检查DashVector配置...")
    dashvector_results = await check_dashvector_config()

    print("4. 检查NLP服务配置...")
    nlp_results = await check_nlp_service()

    print("5. 测试音频片段 4584b9cc-3176-4be5-bece-d159a1a364e9 的向量搜索...")
    search_results = await test_vector_search("4584b9cc-3176-4be5-bece-d159a1a364e9")

    # 输出结果
    print("\n" + "="*80)
    print("验证结果汇总")
    print("="*80)

    print("\n📊 数据库向量统计:")
    print(f"  音频片段总数: {db_results['total_segments']}")
    print(f"  有向量的片段数: {db_results['segments_with_vectors']}")
    print(f"  向量覆盖率: {db_results['segments_with_vectors']/db_results['total_segments']*100:.1f}%")

    if db_results['vector_dimensions']:
        print(f"  向量维度范围: {min(db_results['vector_dimensions'])} - {max(db_results['vector_dimensions'])}")
        print(f"  期望维度: {settings.VECTOR_DIMENSION}")

    print("\n📝 向量质量检查:")
    print(f"  维度正确: {db_results['vector_quality']['valid_dimensions']}")
    print(f"  维度错误: {db_results['vector_quality']['wrong_dimension']}")
    print(f"  空向量: {db_results['vector_quality']['null_vectors']}")

    if db_results['sample_vectors']:
        print("\n🔍 样本向量检查:")
        for sample in db_results['sample_vectors']:
            status = "✅" if sample["dimension_match"] else "❌"
            print(f"  {status} ID: {sample['id']}")
            print(f"    维度: {sample['vector_dimension']} (期望: {sample['expected_dimension']})")
            if sample['transcription_preview']:
                print(f"    文本: {sample['transcription_preview']}...")

    print("\n🌐 DashVector配置:")
    print(f"  启用状态: {'✅' if dashvector_results['dashvector_enabled'] else '❌'}")
    print(f"  API Key配置: {'✅' if dashvector_results['api_key_configured'] else '❌'}")
    print(f"  Endpoint配置: {'✅' if dashvector_results['endpoint_configured'] else '❌'}")
    print(f"  Collection配置: {'✅' if dashvector_results['collection_configured'] else '❌'}")
    print(f"  连接测试: {'✅' if dashvector_results['connection_test'] else '❌'}")

    if dashvector_results['collection_info']:
        print(f"  集合信息:")
        for key, value in dashvector_results['collection_info'].items():
            print(f"    {key}: {value}")

    if dashvector_results['error']:
        print(f"  错误信息: ❌ {dashvector_results['error']}")

    print("\n🤖 NLP服务配置:")
    print(f"  嵌入模型: {nlp_results['embedding_model']}")
    print(f"  API Key配置: {'✅' if nlp_results['api_key_configured'] else '❌'}")
    print(f"  向量维度: {nlp_results['vector_dimension']}")
    print(f"  DashVector集合维度: {nlp_results['dashvector_collection_dimension']}")
    print(f"  维度匹配: {'✅' if nlp_results['dimension_match'] else '❌'}")

    print("\n🔍 向量搜索测试结果:")
    print(f"  音频ID: {search_results['audio_id']}")
    print(f"  数据库中是否存在: {'✅' if search_results['found_in_database'] else '❌'}")
    print(f"  是否有向量: {'✅' if search_results['has_vector'] else '❌'}")
    if search_results['vector_dimension']:
        print(f"  向量维度: {search_results['vector_dimension']}")
    print(f"  自相似度: {search_results['self_similarity'] or '未找到'}")
    print(f"  搜索测试通过: {'✅' if search_results['search_test_passed'] else '❌'}")

    if search_results.get('error'):
        print(f"  错误信息: ❌ {search_results['error']}")

    # 诊断问题
    print("\n" + "="*80)
    print("问题诊断")
    print("="*80)

    issues = []

    # 检查维度匹配
    if not nlp_results['dimension_match']:
        issues.append("❌ 向量生成维度与DashVector集合维度不匹配")

    # 检查向量覆盖率
    if db_results['total_segments'] > 0:
        coverage = db_results['segments_with_vectors'] / db_results['total_segments']
        if coverage < 0.9:
            issues.append(f"❌ 向量覆盖率过低: {coverage*100:.1f}%")

    # 检查DashVector连接
    if not dashvector_results['connection_test']:
        issues.append("❌ DashVector连接失败")

    # 检查搜索自相似度
    if search_results['self_similarity'] is not None:
        if search_results['self_similarity'] < 0.5:
            issues.append(f"❌ 自相似度过低: {search_results['self_similarity']:.4f} (期望接近1.0)")
    else:
        issues.append("❌ 无法计算自相似度")

    if issues:
        print("发现以下问题:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✅ 未发现明显配置问题")

    print("\n" + "="*80)
    print("建议")
    print("="*80)

    if not dashvector_results['connection_test']:
        print("1. 🔧 修复DashVector连接:")
        print("   - 检查API Key和Endpoint是否正确")
        print("   - 验证网络连接和防火墙设置")
        print("   - 确保DashVector服务已激活")

    if not nlp_results['dimension_match']:
        print("2. 🔧 修复维度不匹配:")
        print(f"   - 向量生成维度: {nlp_results['vector_dimension']}")
        print(f"   - DashVector集合维度: {nlp_results['dashvector_collection_dimension']}")
        print("   - 需要确保两者一致")

    if search_results['self_similarity'] is not None and search_results['self_similarity'] < 0.5:
        print("3. 🔧 修复向量检索问题:")
        print("   - 检查向量生成质量")
        print("   - 验证DashVector集合度量方式是否为cosine")
        print("   - 检查向量是否已正确同步到DashVector")

    if db_results['vector_quality']['wrong_dimension'] > 0:
        print("4. 🔧 修复向量维度错误:")
        print("   - 重新生成维度错误的向量")
        print("   - 检查向量生成服务配置")

    print("\n✅ 验证完成")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))