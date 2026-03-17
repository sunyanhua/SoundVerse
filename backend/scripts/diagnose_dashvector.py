#!/usr/bin/env python3
"""
诊断DashVector集合配置问题
检查度量方式、相似度计算等问题
"""

import sys
import os
from pathlib import Path

# 设置项目根目录
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings

print("=== DashVector集合诊断 ===\n")

def diagnose_dashvector():
    """诊断DashVector集合配置"""

    if not settings.DASHVECTOR_API_KEY or not settings.DASHVECTOR_ENDPOINT:
        print("❌ DashVector API Key或Endpoint未配置")
        return

    print(f"API Key: {'已配置' if settings.DASHVECTOR_API_KEY else '未配置'}")
    print(f"Endpoint: {settings.DASHVECTOR_ENDPOINT}")
    print(f"Collection: {settings.DASHVECTOR_COLLECTION}")
    print(f"Namespace: {settings.DASHVECTOR_NAMESPACE}")
    print(f"集合维度: {settings.DASHVECTOR_COLLECTION_DIMENSION}")
    print(f"向量维度: {settings.VECTOR_DIMENSION}")

    try:
        import dashvector

        # 初始化客户端
        client = dashvector.Client(
            api_key=settings.DASHVECTOR_API_KEY,
            endpoint=settings.DASHVECTOR_ENDPOINT
        )

        collection_name = settings.DASHVECTOR_COLLECTION
        collection = client.get(collection_name)

        if not collection:
            print(f"\n❌ 集合 {collection_name} 不存在")
            return

        print(f"\n✅ 成功连接到集合 {collection_name}")

        # 尝试获取集合详细信息
        try:
            # stats方法可能返回不同类型的数据
            stats = collection.stats()

            print("\n📊 集合统计信息:")

            # 尝试多种方式提取信息
            def try_get(obj, *keys):
                """尝试从对象或字典中获取值"""
                for key in keys:
                    if hasattr(obj, key):
                        return getattr(obj, key)
                    elif isinstance(obj, dict) and key in obj:
                        return obj[key]
                return None

            # 文档数
            total_docs = try_get(stats, 'total_doc_count', 'total_count', 'total_docs', 'count', 'doc_count')
            if total_docs is not None:
                print(f"  文档总数: {total_docs}")
            else:
                print("  文档总数: 无法获取")

            # 维度
            dimension = try_get(stats, 'dimension')
            if dimension is not None:
                print(f"  维度: {dimension}")
            else:
                print(f"  维度: 使用配置值 {settings.DASHVECTOR_COLLECTION_DIMENSION}")

            # 度量方式
            metric = try_get(stats, 'metric')
            if metric is not None:
                print(f"  度量方式: {metric}")

                # 解释度量方式
                metric_explanations = {
                    'cosine': '余弦相似度，范围[-1, 1]，值越大越相似',
                    'ip': '内积相似度，值越大越相似',
                    'l2': 'L2距离（欧氏距离），值越小越相似'
                }

                if metric.lower() in metric_explanations:
                    print(f"    解释: {metric_explanations[metric.lower()]}")
                else:
                    print(f"    警告: 未知度量方式 '{metric}'")

                # 检查是否为余弦相似度
                if metric.lower() != 'cosine':
                    print(f"    ❌ 问题: 集合未使用余弦相似度度量")
                    print(f"        当前度量: {metric}")
                    print(f"        推荐使用: cosine (余弦相似度)")
            else:
                print(f"  度量方式: 未知 (无法获取)")
                print(f"    ⚠️ 警告: 无法确认集合使用的度量方式")

            # 尝试获取更详细的信息
            print("\n🔍 尝试获取完整统计信息:")
            try:
                # 打印stats对象的类型和属性
                print(f"  stats对象类型: {type(stats)}")

                if hasattr(stats, '__dict__'):
                    print(f"  stats对象属性:")
                    for key, value in stats.__dict__.items():
                        if not key.startswith('_'):
                            print(f"    {key}: {value}")

                # 如果是DashVectorResponse对象
                if hasattr(stats, 'output'):
                    output = stats.output
                    print(f"  output类型: {type(output)}")

                    if hasattr(output, '__dict__'):
                        for key, value in output.__dict__.items():
                            if not key.startswith('_'):
                                print(f"    output.{key}: {value}")
            except Exception as e:
                print(f"  获取详细信息失败: {str(e)}")

        except Exception as e:
            print(f"\n❌ 获取集合统计信息失败: {str(e)}")

        # 测试相似度计算
        print("\n🧪 测试相似度计算:")

        try:
            # 创建一个简单的测试查询
            from services.search_service import search_service

            # 初始化搜索服务
            import asyncio

            async def test_search():
                await search_service.initialize()

                # 测试一个简单查询
                test_query = "测试"
                results = await search_service.search_by_text(test_query, top_k=3, similarity_threshold=0.0)

                print(f"  测试查询: '{test_query}'")
                print(f"  返回结果数: {len(results)}")

                if results:
                    print(f"  相似度范围: {min(sim for _, sim in results):.4f} - {max(sim for _, sim in results):.4f}")

                    # 检查是否有负值
                    negative_scores = [sim for _, sim in results if sim < 0]
                    if negative_scores:
                        print(f"  ⚠️ 警告: 发现负相似度分数: {negative_scores[0]:.4f}")
                        print(f"     余弦相似度应为[-1, 1]，但负值可能表示度量方式问题")

                    # 检查是否有大于1的值
                    large_scores = [sim for _, sim in results if sim > 1]
                    if large_scores:
                        print(f"  ⚠️ 警告: 发现大于1的相似度分数: {large_scores[0]:.4f}")
                        print(f"     余弦相似度不应大于1")

                return results

            results = asyncio.run(test_search())

        except Exception as e:
            print(f"  搜索测试失败: {str(e)}")

        # 测试向量相似度计算原理
        print("\n🔬 测试向量相似度计算原理:")

        try:
            # 尝试直接调用DashVector查询
            test_vector = [0.1] * settings.DASHVECTOR_COLLECTION_DIMENSION  # 简单的测试向量

            # 直接查询
            query_result = collection.query(
                vector=test_vector,
                topk=1,
                include_vector=False
            )

            if query_result:
                print(f"  测试向量查询成功")
                if hasattr(query_result[0], 'score'):
                    score = query_result[0].score
                    print(f"  查询分数: {score:.6f}")

                    # 分析分数范围
                    if score < -1 or score > 1:
                        print(f"  ⚠️ 分数超出[-1, 1]范围，可能不是余弦相似度")
                    elif score < 0:
                        print(f"  ⚠️ 负分数，向量可能不相似")
                    else:
                        print(f"  ✅ 分数在合理范围内")
            else:
                print(f"  测试向量查询无结果")

        except Exception as e:
            print(f"  向量查询测试失败: {str(e)}")

    except ImportError:
        print(f"\n❌ dashvector库未安装")
    except Exception as e:
        print(f"\n❌ 诊断过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()

def check_similarity_calculation():
    """检查相似度计算逻辑"""
    print("\n" + "="*80)
    print("相似度计算逻辑检查")
    print("="*80)

    # 查看search_service.py中的相似度计算
    search_service_path = Path(backend_dir) / "services" / "search_service.py"

    print(f"检查文件: {search_service_path}")

    if search_service_path.exists():
        with open(search_service_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 查找相似度计算相关的代码
        lines = content.split('\n')

        print("\n在search_service.py中找到的相似度处理:")

        for i, line in enumerate(lines):
            if 'similarity' in line.lower() or 'score' in line.lower() or 'distance' in line.lower():
                # 显示上下文
                start = max(0, i-1)
                end = min(len(lines), i+2)

                print(f"\n行 {i+1}:")
                for j in range(start, end):
                    prefix = ">>> " if j == i else "    "
                    print(f"{prefix}{lines[j]}")

    # 检查配置文件中的阈值
    print(f"\n📊 当前阈值配置:")
    print(f"  SIMILARITY_THRESHOLD: {settings.SIMILARITY_THRESHOLD}")
    print(f"  AUDIO_REPLY_THRESHOLD: {settings.AUDIO_REPLY_THRESHOLD}")
    print(f"  AUDIO_SUGGEST_THRESHOLD: {settings.AUDIO_SUGGEST_THRESHOLD}")

def main():
    """主函数"""
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    try:
        diagnose_dashvector()
        check_similarity_calculation()

        print("\n" + "="*80)
        print("诊断总结")
        print("="*80)

        print("\n📋 可能的问题和解决方案:")

        print("\n1. 度量方式问题:")
        print("   • 症状: 自我相似度为0.0000或负值")
        print("   • 可能原因: DashVector集合未使用余弦相似度度量")
        print("   • 解决方案:")
        print("     a) 检查并确认集合度量方式")
        print("     b) 如果度量方式错误，需要重建集合")
        print("     c) 更新代码以处理正确的相似度范围")

        print("\n2. 向量归一化问题:")
        print("   • 症状: 相似度分数范围异常")
        print("   • 可能原因: 向量未归一化，或归一化方式与度量方式不匹配")
        print("   • 解决方案:")
        print("     a) 确保向量在入库前已正确归一化")
        print("     b) 对于余弦相似度，向量应为单位长度")

        print("\n3. 阈值设置问题:")
        print("   • 症状: 当前阈值(0.55/0.35)可能不适用于当前相似度分布")
        print("   • 可能原因: 相似度分布范围未知")
        print("   • 解决方案:")
        print("     a) 先修复度量方式问题")
        print("     b) 分析修复后的相似度分布")
        print("     c) 基于实际数据调整阈值")

        print("\n🔧 建议的修复步骤:")
        print("1. 首先确定DashVector集合的实际度量方式")
        print("2. 如果度量方式不是'cosine'，考虑重建集合")
        print("3. 测试修复后的自我相似度是否正常(接近1.0)")
        print("4. 重新评估并调整阈值设置")
        print("5. 重新测试语义匹配功能")

        print("\n⚠️ 注意: 重建DashVector集合需要重新同步所有向量(2370个片段)")
        print("      这可能需要一些时间，但可以修复根本问题")

        return 0

    except Exception as e:
        print(f"\n❌ 诊断过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())