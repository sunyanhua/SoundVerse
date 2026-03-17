#!/usr/bin/env python3
"""
检查向量归一化状态
对于余弦相似度，向量应为单位长度（范数=1）
"""

import asyncio
import sys
import os
import json
import numpy as np
from pathlib import Path
from typing import List, Tuple

# 设置项目根目录
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 设置容器内的数据库URL
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from config import settings

print("=== 向量归一化检查 ===\n")
print("对于余弦相似度，向量应为单位长度（范数≈1）\n")

async def check_vector_norms():
    """检查向量范数"""
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results = {
        "total_vectors": 0,
        "norms": [],
        "norm_stats": {
            "mean": 0,
            "std": 0,
            "min": float('inf'),
            "max": 0,
            "unit_vectors": 0,  # 范数接近1的向量
            "non_unit_vectors": 0,
            "zero_vectors": 0
        }
    }

    async with async_session() as session:
        # 抽样检查向量
        result = await session.execute(text("""
            SELECT id, transcription, vector
            FROM audio_segments
            WHERE vector IS NOT NULL
            ORDER BY RAND()
            LIMIT 50
        """))

        segments = result.fetchall()

        print(f"抽样检查 {len(segments)} 个向量\n")

        for i, (seg_id, transcription, vector_json) in enumerate(segments):
            try:
                vector = json.loads(vector_json) if isinstance(vector_json, str) else vector_json

                if not vector or len(vector) == 0:
                    print(f"{i+1:2d}. ❌ ID: {seg_id} - 空向量")
                    results["norm_stats"]["zero_vectors"] += 1
                    continue

                # 计算范数
                norm = np.linalg.norm(vector)

                results["total_vectors"] += 1
                results["norms"].append(norm)

                # 更新统计
                results["norm_stats"]["min"] = min(results["norm_stats"]["min"], norm)
                results["norm_stats"]["max"] = max(results["norm_stats"]["max"], norm)

                # 判断是否为单位向量（允许一定误差）
                is_unit = 0.95 <= norm <= 1.05
                if is_unit:
                    results["norm_stats"]["unit_vectors"] += 1
                else:
                    results["norm_stats"]["non_unit_vectors"] += 1

                # 显示前10个样本的详细信息
                if i < 10:
                    status = "✅" if is_unit else "❌"
                    transcription_preview = (transcription[:40] + "...") if transcription and len(transcription) > 40 else transcription or "无文本"
                    print(f"{i+1:2d}. {status} ID: {seg_id}")
                    print(f"     范数: {norm:.6f} {'(单位向量)' if is_unit else '(非单位向量)'}")
                    print(f"     文本: {transcription_preview}")
                    print()

            except Exception as e:
                print(f"{i+1:2d}. ❌ ID: {seg_id} - 解析失败: {str(e)}")

        # 计算统计信息
        if results["norms"]:
            norms_array = np.array(results["norms"])
            results["norm_stats"]["mean"] = float(np.mean(norms_array))
            results["norm_stats"]["std"] = float(np.std(norms_array))

        return results

async def test_cosine_similarity_calculation():
    """测试余弦相似度计算"""
    print("\n🧪 测试余弦相似度计算")

    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 获取两个随机向量
        result = await session.execute(text("""
            SELECT id, vector
            FROM audio_segments
            WHERE vector IS NOT NULL
            ORDER BY RAND()
            LIMIT 2
        """))

        vectors = result.fetchall()

        if len(vectors) < 2:
            print("   需要至少2个向量进行测试")
            return

        vec1_id, vec1_json = vectors[0]
        vec2_id, vec2_json = vectors[1]

        vec1 = json.loads(vec1_json) if isinstance(vec1_json, str) else vec1_json
        vec2 = json.loads(vec2_json) if isinstance(vec2_json, str) else vec2_json

        if not vec1 or not vec2:
            print("   向量数据无效")
            return

        # 计算手动余弦相似度
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        # 计算余弦相似度
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            print("   向量范数为0，无法计算余弦相似度")
            return

        cosine_sim = dot_product / (norm1 * norm2)

        print(f"   向量1 ID: {vec1_id}, 范数: {norm1:.6f}")
        print(f"   向量2 ID: {vec2_id}, 范数: {norm2:.6f}")
        print(f"   点积: {dot_product:.6f}")
        print(f"   手动计算余弦相似度: {cosine_sim:.6f}")
        print(f"   理论范围: [-1, 1]")

        # 测试DashVector相似度计算
        try:
            from services.search_service import search_audio_segments_by_text

            # 通过文本搜索测试
            # 获取向量1对应的文本
            result = await session.execute(text("""
                SELECT transcription FROM audio_segments WHERE id = :vec_id
            """), {"vec_id": vec1_id})

            transcription = result.scalar()

            if transcription:
                search_results = await search_audio_segments_by_text(
                    transcription,
                    top_k=10,
                    similarity_threshold=0.0
                )

                # 查找向量2的相似度
                for result_id, similarity in search_results:
                    if result_id == vec2_id:
                        print(f"   DashVector相似度: {similarity:.6f}")
                        print(f"   差异: {abs(cosine_sim - similarity):.6f}")

                        if abs(cosine_sim - similarity) > 0.01:
                            print(f"   ⚠️  注意: DashVector相似度与手动计算有较大差异")
                        break

        except Exception as e:
            print(f"   DashVector测试失败: {str(e)}")

async def test_self_similarity_with_normalization():
    """测试归一化后的自我相似度"""
    print("\n🔍 测试自我相似度（检查归一化问题）")

    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # 获取一个向量
        result = await session.execute(text("""
            SELECT id, transcription, vector
            FROM audio_segments
            WHERE vector IS NOT NULL AND transcription IS NOT NULL
            ORDER BY RAND()
            LIMIT 1
        """))

        segment = result.fetchone()

        if not segment:
            print("   未找到合适片段")
            return

        seg_id, transcription, vector_json = segment
        vector = json.loads(vector_json) if isinstance(vector_json, str) else vector_json

        if not vector:
            print(f"   片段 {seg_id} 无向量数据")
            return

        # 计算原始向量范数
        norm = np.linalg.norm(vector)
        print(f"   测试片段: {seg_id}")
        print(f"   向量范数: {norm:.6f}")

        # 如果是单位向量，计算自我余弦相似度
        if norm > 0:
            # 手动计算自我余弦相似度（应与1.0非常接近）
            normalized_vector = np.array(vector) / norm
            self_cosine = np.dot(normalized_vector, normalized_vector)

            print(f"   自我余弦相似度（理论）: {self_cosine:.6f}")

            # 如果向量不是单位长度，计算实际自我相似度
            if abs(norm - 1.0) > 0.01:
                print(f"   ⚠️  注意: 向量不是单位长度（范数={norm:.6f}）")
                print(f"      非单位向量的自我余弦相似度: {np.dot(vector, vector) / (norm * norm):.6f}")

        # 测试DashVector自我相似度
        try:
            from services.search_service import search_audio_segments_by_text

            search_results = await search_audio_segments_by_text(
                transcription,
                top_k=5,
                similarity_threshold=0.0
            )

            # 查找自相似度
            for result_id, similarity in search_results:
                if result_id == seg_id:
                    print(f"   DashVector自我相似度: {similarity:.6f}")

                    if similarity < 0.9:
                        print(f"   ❌ 问题: 自我相似度过低（期望接近1.0）")
                        print(f"      可能原因:")
                        print(f"      1. 向量未归一化")
                        print(f"      2. DashVector度量方式问题")
                        print(f"      3. 向量生成质量问题")
                    break

        except Exception as e:
            print(f"   搜索测试失败: {str(e)}")

async def main():
    """主函数"""
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    try:
        # 检查向量范数
        norm_results = await check_vector_norms()

        if norm_results["total_vectors"] > 0:
            print("\n📊 向量范数统计:")
            print(f"   检查向量数: {norm_results['total_vectors']}")
            print(f"   平均范数: {norm_results['norm_stats']['mean']:.6f}")
            print(f"   标准差: {norm_results['norm_stats']['std']:.6f}")
            print(f"   最小范数: {norm_results['norm_stats']['min']:.6f}")
            print(f"   最大范数: {norm_results['norm_stats']['max']:.6f}")
            print(f"   单位向量: {norm_results['norm_stats']['unit_vectors']} ({norm_results['norm_stats']['unit_vectors']/norm_results['total_vectors']*100:.1f}%)")
            print(f"   非单位向量: {norm_results['norm_stats']['non_unit_vectors']} ({norm_results['norm_stats']['non_unit_vectors']/norm_results['total_vectors']*100:.1f}%)")
            print(f"   空向量: {norm_results['norm_stats']['zero_vectors']}")

            # 分析问题
            unit_percentage = norm_results['norm_stats']['unit_vectors'] / norm_results['total_vectors']
            if unit_percentage < 0.5:
                print(f"\n❌ 问题: 大部分向量不是单位长度")
                print(f"   只有 {unit_percentage*100:.1f}% 的向量是单位长度")
                print(f"   对于余弦相似度，向量应归一化为单位长度")

        # 测试余弦相似度计算
        await test_cosine_similarity_calculation()

        # 测试自我相似度
        await test_self_similarity_with_normalization()

        print("\n" + "="*80)
        print("诊断总结")
        print("="*80)

        if norm_results["total_vectors"] > 0 and norm_results['norm_stats']['unit_vectors'] / norm_results['total_vectors'] < 0.5:
            print("\n❌ 主要问题: 向量未正确归一化")
            print("   对于余弦相似度，向量应为单位长度（范数≈1）")
            print("   非单位向量会导致相似度计算不准确")

            print("\n🔧 解决方案:")
            print("1. 重新归一化现有向量:")
            print("   • 从数据库读取向量")
            print("   • 归一化为单位长度")
            print("   • 更新数据库和DashVector索引")

            print("\n2. 修复向量生成服务:")
            print("   • 确保NLPService生成的向量已归一化")
            print("   • 检查text-embedding-v4模型输出是否需要后处理")

            print("\n3. 验证修复效果:")
            print("   • 重新检查向量范数")
            print("   • 测试自我相似度是否接近1.0")
            print("   • 重新测试语义匹配")

        else:
            print("\n✅ 向量归一化状态良好")
            print("   问题可能在其他方面（如度量方式、向量质量等）")

        print("\n📋 建议的后续步骤:")
        print("1. 如果向量未归一化，先修复归一化问题")
        print("2. 重新测试自我相似度")
        print("3. 如果问题仍然存在，检查DashVector度量方式")
        print("4. 考虑重新生成或重新索引向量")

        return 0

    except Exception as e:
        print(f"\n❌ 检查过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))