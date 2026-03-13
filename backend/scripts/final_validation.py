#!/usr/bin/env python3
"""
最终验证：测试完整的聊天流程
"""
import sys
import logging
import asyncio
from pathlib import Path
import httpx
import json

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_chat_api():
    """测试聊天API"""
    logger.info("=" * 60)
    logger.info("  最终验证：测试完整的聊天流程")
    logger.info("=" * 60)

    # API端点
    base_url = "http://localhost:8000"
    chat_endpoint = f"{base_url}/api/v1/chat/message"

    # 测试查询
    test_queries = [
        "有什么新闻广播吗",
        "我想去河北定居",  # 用户指定的测试查询
        "天气预报",
        "今天有什么新闻",
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for query in test_queries:
            logger.info(f"\n测试查询: '{query}'")

            # 构造请求
            request_data = {
                "content": query,
                "session_id": "test_session_final_validation"
            }

            try:
                # 发送请求
                response = await client.post(chat_endpoint, json=request_data)

                logger.info(f"响应状态码: {response.status_code}")

                if response.status_code == 200:
                    response_data = response.json()
                    logger.info(f"响应数据:")

                    # 检查是否有音频回复
                    if "audio_segment" in response_data and response_data["audio_segment"]:
                        audio_info = response_data["audio_segment"]
                        similarity = audio_info.get("similarity", 0)
                        logger.info(f"  [音频回复] 相似度: {similarity:.4f}")
                        logger.info(f"  音频URL: {audio_info.get('oss_url', 'N/A')[:80]}...")
                        logger.info(f"  转录文本: {audio_info.get('transcription', 'N/A')[:100]}...")

                        if similarity >= settings.AUDIO_REPLY_THRESHOLD:
                            logger.info(f"  [正确] 相似度 {similarity:.4f} ≥ 阈值 {settings.AUDIO_REPLY_THRESHOLD}")
                        else:
                            logger.warning(f"  [问题] 相似度 {similarity:.4f} < 阈值 {settings.AUDIO_REPLY_THRESHOLD}")
                    else:
                        logger.info(f"  [AI文字回复]")
                        logger.info(f"  回复内容: {response_data.get('content', 'N/A')[:150]}...")

                    # 检查建议问题
                    if "suggestions" in response_data and response_data["suggestions"]:
                        logger.info(f"  建议问题: {response_data['suggestions']}")

                else:
                    logger.error(f"请求失败: {response.status_code}")
                    logger.error(f"响应体: {response.text}")

            except Exception as e:
                logger.error(f"请求异常: {str(e)}")

    # 特别验证阈值逻辑
    logger.info("\n" + "=" * 60)
    logger.info("  验证阈值逻辑 (0.70)")
    logger.info("=" * 60)

    # 获取搜索服务统计
    from services.search_service import search_service
    await search_service.initialize()
    stats = await search_service.get_index_stats()
    logger.info(f"搜索服务统计: {stats}")

    # 测试阈值边界
    logger.info(f"当前阈值设置: AUDIO_REPLY_THRESHOLD = {settings.AUDIO_REPLY_THRESHOLD}")
    logger.info(f"当前阈值设置: SIMILARITY_THRESHOLD = {settings.SIMILARITY_THRESHOLD}")

    logger.info("\n系统配置验证:")
    logger.info(f"1. DashVector配置: {'已启用' if settings.DASHVECTOR_API_KEY else '未启用'}")
    logger.info(f"2. 向量维度: {settings.VECTOR_DIMENSION}")
    logger.info(f"3. 搜索阈值: {settings.SIMILARITY_THRESHOLD}")
    logger.info(f"4. 音频回复阈值: {settings.AUDIO_REPLY_THRESHOLD}")
    logger.info(f"5. DashScope API密钥: {'已配置' if settings.DASHSCOPE_API_KEY else '未配置'}")

    logger.info("\n" + "=" * 60)
    logger.info("  验证完成")
    logger.info("=" * 60)


async def main():
    try:
        await test_chat_api()
        return 0
    except Exception as e:
        logger.error(f"验证失败: {str(e)}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)