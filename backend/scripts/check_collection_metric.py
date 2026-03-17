#!/usr/bin/env python3
"""
直接检查DashVector集合度量方式
"""
import sys
import os
from pathlib import Path

# 设置项目根目录
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings

print("=== 检查DashVector集合度量方式 ===\n")

def check_collection_metric():
    """检查集合度量方式"""
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

        # 获取集合
        collection = client.get(collection_name)
        if not collection:
            print(f"\n❌ 集合不存在: {collection_name}")
            return False

        print(f"\n✅ 成功获取集合: {collection_name}")

        # 尝试获取统计信息
        try:
            stats = collection.stats()
            print(f"stats类型: {type(stats)}")

            # 尝试多种方式提取度量方式
            metric = None

            # 方法1：直接访问metric属性
            if hasattr(stats, 'metric'):
                metric = stats.metric
                print(f"方法1 (stats.metric): {metric}")

            # 方法2：访问output.metric
            if metric is None and hasattr(stats, 'output'):
                output = stats.output
                if hasattr(output, 'metric'):
                    metric = output.metric
                    print(f"方法2 (stats.output.metric): {metric}")

            # 方法3：访问字典
            if metric is None and isinstance(stats, dict):
                if 'metric' in stats:
                    metric = stats['metric']
                    print(f"方法3 (stats['metric']): {metric}")

            # 方法4：遍历属性
            if metric is None:
                print("方法4: 遍历stats对象属性:")
                if hasattr(stats, '__dict__'):
                    for key, value in stats.__dict__.items():
                        if not key.startswith('_'):
                            print(f"  {key}: {value}")
                            if key == 'metric' or 'metric' in key.lower():
                                metric = value

            # 方法5：尝试序列化为字典
            if metric is None:
                try:
                    import json
                    stats_dict = json.loads(json.dumps(stats, default=str))
                    if isinstance(stats_dict, dict) and 'metric' in stats_dict:
                        metric = stats_dict['metric']
                        print(f"方法5 (JSON解析): {metric}")
                except:
                    pass

            if metric:
                print(f"\n✅ 集合度量方式: {metric}")
                print(f"\n度量方式解释:")
                if metric.lower() == 'cosine':
                    print("  • cosine: 余弦相似度，范围[-1, 1]，值越大越相似")
                    print("  • 自我相似度应接近1.0")
                elif metric.lower() == 'ip':
                    print("  • ip: 内积相似度，范围(-∞, +∞)，值越大越相似")
                    print("  • 对于单位向量，内积等于余弦相似度")
                elif metric.lower() == 'l2':
                    print("  • l2: L2距离（欧氏距离），范围[0, +∞)，值越小越相似")
                    print("  • 需要转换为相似度分数")
                else:
                    print(f"  • {metric}: 未知度量方式")

                return metric
            else:
                print(f"\n⚠️ 无法确定度量方式")
                return None

        except Exception as e:
            print(f"\n❌ 获取统计信息失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    except Exception as e:
        print(f"\n❌ 检查集合时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_similarity_calculation():
    """测试相似度计算"""
    print("\n=== 测试相似度计算 ===")

    try:
        import dashvector
        import numpy as np

        # 创建客户端
        client = dashvector.Client(
            api_key=settings.DASHVECTOR_API_KEY,
            endpoint=settings.DASHVECTOR_ENDPOINT
        )

        collection = client.get(settings.DASHVECTOR_COLLECTION)
        if not collection:
            print("❌ 集合不存在")
            return

        # 创建一个简单的测试向量
        dim = settings.DASHVECTOR_COLLECTION_DIMENSION
        test_vector = [0.1] * dim

        print(f"测试向量维度: {dim}")
        print(f"测试向量范数: {np.linalg.norm(test_vector):.4f}")

        # 查询自身
        results = collection.query(
            vector=test_vector,
            topk=1,
            include_vector=False
        )

        if results:
            doc = results[0]
            print(f"查询分数: {doc.score:.6f}")

            # 分析分数
            if doc.score < -1 or doc.score > 1:
                print(f"⚠️ 分数超出[-1, 1]范围，可能不是余弦相似度")
            elif doc.score < 0:
                print(f"⚠️ 负分数，可能不是余弦相似度或向量不相似")
            else:
                print(f"✅ 分数在[-1, 1]范围内")

            # 插入测试向量并查询
            print("\n插入测试向量并查询...")
            from dashvector import Doc
            test_doc = Doc(
                id="test_vector_001",
                vector=test_vector,
                fields={"test": True}
            )

            # 插入
            result = collection.upsert(test_doc)
            if result:
                print("✅ 测试向量插入成功")

                # 查询测试向量
                results = collection.query(
                    vector=test_vector,
                    topk=2,
                    include_vector=False
                )

                print("查询结果:")
                for i, doc in enumerate(results):
                    if doc.id == "test_vector_001":
                        print(f"  {i+1}. [✓] ID: {doc.id}, 分数: {doc.score:.6f} (自我相似度)")
                    else:
                        print(f"  {i+1}. [ ] ID: {doc.id}, 分数: {doc.score:.6f}")

                # 清理测试向量
                collection.delete(["test_vector_001"])
                print("✅ 清理测试向量")
            else:
                print("❌ 测试向量插入失败")

        else:
            print("❌ 查询无结果")

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    metric = check_collection_metric()
    if metric:
        test_similarity_calculation()

    print("\n" + "="*60)
    print("总结")
    print("="*60)

    if metric:
        print(f"集合度量方式: {metric}")
        if metric.lower() != 'cosine':
            print("\n❌ 问题: 集合未使用余弦相似度度量")
            print("   这可以解释为什么自我相似度为0.0000")
            print("\n🔧 解决方案:")
            print("   1. 删除并重新创建集合，指定metric='cosine'")
            print("   2. 重新同步所有向量")
            print("   3. 重新测试自我相似度")
        else:
            print("\n✅ 集合使用余弦相似度度量")
            print("   但自我相似度为0.0000，可能是其他问题")
            print("\n🔧 需要进一步调查:")
            print("   1. 向量归一化问题")
            print("   2. 查询向量与存储向量不一致")
            print("   3. DashVector服务端问题")
    else:
        print("⚠️ 无法确定集合度量方式")