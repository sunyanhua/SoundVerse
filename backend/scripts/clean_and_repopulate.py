#!/usr/bin/env python3
"""
清理并重新入库：清空数据库中的测试音频片段，重新运行完整流水线
"""
import asyncio
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 使用MySQL连接，根据运行环境自动选择
import os
if os.environ.get("DATABASE_URL") is None:
    # 检查是否在Docker容器内（通过环境变量或文件系统）
    if os.path.exists("/.dockerenv"):
        # 在容器内，使用服务名mysql
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@mysql:3306/soundverse"
    else:
        # 在主机上，使用localhost
        os.environ["DATABASE_URL"] = "mysql+asyncmy://soundverse:password@localhost:3306/soundverse"

from sqlalchemy import delete
from shared.database.session import init_db, async_session_maker
from shared.models.audio import AudioSegment, AudioSource
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def cleanup_database():
    """清理数据库中的测试音频片段"""
    try:
        # 初始化数据库
        await init_db()

        async with async_session_maker() as db:
            # 使用原生SQL删除，避免SQLAlchemy版本问题
            from sqlalchemy import text
            logger.info("删除所有音频片段...")
            await db.execute(text("DELETE FROM audio_segments"))
            logger.info("删除所有音频源...")
            await db.execute(text("DELETE FROM audio_sources"))
            await db.commit()

            logger.info("数据库清理完成")
            return True

    except Exception as e:
        logger.error(f"清理数据库失败: {str(e)}")
        return False

async def reset_vector_index():
    """重置向量索引"""
    try:
        # 导入重置脚本
        from scripts.reset_dashvector import reset_dashvector_collection
        logger.info("重置DashVector集合...")
        success = await reset_dashvector_collection()
        if success:
            logger.info("DashVector集合重置成功")
        else:
            logger.error("DashVector集合重置失败")
        return success
    except Exception as e:
        logger.error(f"重置向量索引失败: {str(e)}")
        return False

async def run_full_pipeline():
    """运行完整流水线"""
    try:
        import subprocess
        logger.info("运行完整音频处理流水线...")

        # 使用子进程运行脚本
        process = await asyncio.create_subprocess_exec(
            sys.executable, "scripts/process_full_pipeline.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(backend_dir)
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            logger.info("完整音频处理流水线运行成功")
            # 打印部分输出
            if stdout:
                output_lines = stdout.decode('utf-8', errors='ignore').split('\n')
                for line in output_lines[-20:]:  # 最后20行
                    if line.strip():
                        logger.info(f"流水线输出: {line.strip()}")
            return True
        else:
            logger.error(f"完整音频处理流水线运行失败，返回码: {process.returncode}")
            if stderr:
                error_output = stderr.decode('utf-8', errors='ignore')
                for line in error_output.split('\n'):
                    if line.strip():
                        logger.error(f"流水线错误: {line.strip()}")
            return False
    except Exception as e:
        logger.error(f"运行完整流水线失败: {str(e)}")
        return False

async def test_search():
    """测试搜索功能"""
    try:
        from services.search_service import search_audio_segments_by_text

        logger.info("=== 测试搜索功能 ===")

        # 测试1: 精准查询"高碑店"
        query1 = "高碑店"
        logger.info(f"测试查询1: '{query1}'")
        results1 = await search_audio_segments_by_text(
            query_text=query1,
            top_k=5,
            similarity_threshold=0.0  # 降低阈值查看所有结果
        )

        if results1:
            best_score = results1[0][1]
            logger.info(f"最高相似度分数: {best_score:.4f}")

            if best_score >= 0.85:
                logger.info(f"✅ 测试通过: 分数 {best_score:.4f} ≥ 0.85")
                return True, best_score
            else:
                logger.warning(f"⚠️ 测试未通过: 分数 {best_score:.4f} < 0.85")
                return False, best_score
        else:
            logger.warning("⚠️ 查询未返回任何结果")
            return False, 0.0

    except Exception as e:
        logger.error(f"测试搜索失败: {str(e)}")
        return False, 0.0

async def main():
    """主函数"""
    logger.info("=== 开始清理并重新入库 ===")

    try:
        # 1. 清理数据库
        logger.info("步骤1: 清理数据库...")
        if not await cleanup_database():
            logger.error("清理数据库失败，退出")
            return 1

        # 2. 重置向量索引
        logger.info("步骤2: 重置向量索引...")
        if not await reset_vector_index():
            logger.warning("重置向量索引失败，继续尝试...")

        # 3. 运行完整流水线
        logger.info("步骤3: 运行完整音频处理流水线...")
        if not await run_full_pipeline():
            logger.error("运行完整流水线失败")
            return 1

        # 4. 测试搜索
        logger.info("步骤4: 测试搜索功能...")
        success, score = await test_search()

        # 5. 汇总结果
        logger.info("\n" + "="*50)
        logger.info("=== 重新入库测试汇总 ===")
        logger.info(f"精准查询'高碑店'测试: {'✅ 通过' if success else '❌ 失败'}")
        if score > 0:
            logger.info(f"最高相似度分数: {score:.4f}")
            if score >= 0.85:
                logger.info("🎉 恭喜！分数达到0.85+目标")
            elif score >= 0.70:
                logger.info("📊 分数达到音频回复门槛(0.70)")
            elif score >= 0.50:
                logger.info("📈 分数有提升但未达目标")
            else:
                logger.info("📉 分数仍然较低")

        if success:
            logger.info("\n✅ 所有步骤完成，分数达标！")
            return 0
        else:
            logger.info("\n⚠️ 重新入库完成，但分数未达标")
            return 1

    except Exception as e:
        logger.error(f"清理并重新入库过程中发生错误: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)