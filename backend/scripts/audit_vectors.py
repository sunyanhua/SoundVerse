#!/usr/bin/env python3
"""
向量真实性审计脚本
检查数据库中的向量是否为真实的1024维浮点数向量
"""
import os
import sys
import json
import numpy as np
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 设置数据库URL
if os.environ.get("DATABASE_URL") is None:
    # 自动检测运行环境：容器内使用mysql，容器外使用localhost
    import os
    if os.path.exists("/.dockerenv"):
        # 在Docker容器内，使用服务名mysql
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"
        print("检测到Docker容器环境，使用mysql:3306")
    else:
        # 在主机上，使用localhost
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"
        print("检测到主机环境，使用localhost:3306")

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
import shared.database.session as db_session
from shared.models.audio import AudioSegment
from shared.models.user import User  # 确保User模型已注册
from shared.models.chat import ChatMessage  # 确保ChatMessage模型已注册

async def audit_vectors():
    """审计向量数据"""
    print("=== 向量真实性审计 ===")

    async with db_session.async_session_maker() as db:
        try:
            # 获取前10个有向量的音频片段
            stmt = select(AudioSegment).where(AudioSegment.vector.isnot(None)).limit(10)
            result = await db.execute(stmt)
            segments = result.scalars().all()

            print(f"数据库中有向量的片段总数: {len(segments)}")

            if not segments:
                print("[ERROR] 数据库中没有向量数据")
                return False

            print(f"\n检查前{len(segments)}个片段的向量...")

            all_vectors_valid = True
            vector_lengths = set()

            for i, segment in enumerate(segments):
                print(f"\n--- 片段 {i+1} ---")
                print(f"ID: {segment.id}")
                print(f"转录文本: {segment.transcription[:100] if segment.transcription else '无'}")

                # 获取向量数据
                if segment.vector:
                    # 尝试解析向量
                    try:
                        # vector字段可能是JSON字符串或已解析的列表
                        if isinstance(segment.vector, str):
                            vector_data = json.loads(segment.vector)
                        else:
                            vector_data = segment.vector

                        # 转换为numpy数组
                        vector_array = np.array(vector_data, dtype=np.float32)

                        # 检查维度
                        dimension = len(vector_array)
                        vector_lengths.add(dimension)

                        print(f"向量维度: {dimension}")

                        # 检查向量值
                        print(f"向量前10个值: {vector_array[:10]}")

                        # 统计特征
                        mean_val = np.mean(vector_array)
                        std_val = np.std(vector_array)
                        zero_count = np.sum(np.abs(vector_array) < 1e-6)

                        print(f"统计特征:")
                        print(f"  均值: {mean_val:.6f}")
                        print(f"  标准差: {std_val:.6f}")
                        print(f"  接近零的值(<1e-6): {zero_count}/{dimension} ({zero_count/dimension*100:.1f}%)")

                        # 检查是否全零或接近全零
                        if zero_count > dimension * 0.9:
                            print("[WARNING] 警告: 超过90%的向量值接近零，可能是无效向量")
                            all_vectors_valid = False

                        # 检查是否包含异常值
                        max_val = np.max(np.abs(vector_array))
                        if max_val > 10.0 or max_val < 1e-6:
                            print(f"[WARNING] 警告: 向量最大绝对值异常: {max_val}")

                    except Exception as e:
                        print(f"[ERROR] 向量解析失败: {e}")
                        print(f"向量数据类型: {type(segment.vector)}")
                        if isinstance(segment.vector, str):
                            print(f"向量字符串前100字符: {segment.vector[:100]}")
                        all_vectors_valid = False
                else:
                    print("[ERROR] 向量字段为空")
                    all_vectors_valid = False

            # 检查维度一致性
            print(f"\n=== 维度一致性检查 ===")
            if len(vector_lengths) == 1:
                dimension = list(vector_lengths)[0]
                print(f"[OK] 所有向量维度一致: {dimension}")

                if dimension == 1024:
                    print(f"[OK] 维度与配置匹配: {dimension} == 1024")
                else:
                    print(f"[WARNING] 维度不匹配: {dimension} != 1024")
                    all_vectors_valid = False
            elif len(vector_lengths) > 1:
                print(f"[ERROR] 向量维度不一致: {vector_lengths}")
                all_vectors_valid = False

            # 检查向量之间的相似度（如果维度一致）
            if len(vector_lengths) == 1 and len(segments) >= 2:
                print(f"\n=== 向量相似度检查 ===")

                vectors = []
                for segment in segments:
                    if segment.vector:
                        try:
                            if isinstance(segment.vector, str):
                                vector_data = json.loads(segment.vector)
                            else:
                                vector_data = segment.vector
                            vectors.append(np.array(vector_data, dtype=np.float32))
                        except:
                            continue

                if len(vectors) >= 2:
                    # 计算第一对向量的余弦相似度
                    v1 = vectors[0]
                    v2 = vectors[1]

                    similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
                    print(f"前两个向量的余弦相似度: {similarity:.6f}")

                    if abs(similarity) > 0.99:
                        print("[WARNING] 警告: 向量高度相似（可能相同）")
                    elif abs(similarity) < 0.01:
                        print("[OK] 向量差异显著")

            return all_vectors_valid

        except Exception as e:
            print(f"[ERROR] 审计失败: {e}")
            return False

async def count_total_segments():
    """统计片段总数"""
    async with db_session.async_session_maker() as db:
        result = await db.execute(select(AudioSegment))
        total = len(result.scalars().all())

        result = await db.execute(select(AudioSegment).where(AudioSegment.vector.isnot(None)))
        with_vectors = len(result.scalars().all())

        print(f"\n=== 数据库统计 ===")
        print(f"音频片段总数: {total}")
        print(f"带向量的片段数: {with_vectors}")
        print(f"无向量的片段数: {total - with_vectors}")

        return total, with_vectors

async def check_vector_field_type():
    """检查vector字段的数据类型"""
    async with db_session.async_session_maker() as db:
        # 执行原始SQL查询检查字段类型
        result = await db.execute(
            text("DESCRIBE audio_segments")
        )
        columns = result.fetchall()

        print(f"\n=== 表结构检查 ===")
        for column in columns:
            if column[0] == 'vector':
                print(f"vector字段类型: {column[1]}")
                print(f"是否为NULL: {'YES' if column[2] == 'YES' else 'NO'}")
                break

async def main():
    """主函数"""
    print("开始向量真实性审计...")

    try:
        # 初始化数据库
        from shared.database.session import init_db
        await init_db()

        # 检查表结构
        await check_vector_field_type()

        # 统计片段
        total, with_vectors = await count_total_segments()

        if with_vectors == 0:
            print("[ERROR] 数据库中没有带向量的片段，无法审计")
            return 1

        # 审计向量
        valid = await audit_vectors()

        if valid:
            print("\n[OK] 审计通过: 向量数据看起来有效")
            return 0
        else:
            print("\n[ERROR] 审计失败: 向量数据存在问题")
            return 1

    except Exception as e:
        print(f"[ERROR] 审计过程中发生错误: {e}")
        return 1

if __name__ == "__main__":
    import asyncio
    exit_code = asyncio.run(main())
    sys.exit(exit_code)