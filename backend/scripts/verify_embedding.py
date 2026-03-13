#!/usr/bin/env python3
"""
DashScope Embedding OpenAI兼容模式验证脚本
严格按照官方文档：https://help.aliyuncs.com/zh/model-studio/developer-reference/openai-api-compatible
"""
import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def verify_embedding():
    """验证DashScope Embedding OpenAI兼容模式"""
    try:
        # 导入openai
        from openai import OpenAI

        # 从settings获取配置
        api_key = settings.DASHSCOPE_API_KEY
        workspace_id = settings.DASHSCOPE_WORKSPACE_ID
        model = settings.DASHSCOPE_EMBEDDING_MODEL  # text-embedding-v4
        vector_dimension = settings.VECTOR_DIMENSION  # 1024

        logger.info("=== DashScope Embedding 验证开始 ===")
        logger.info(f"API密钥前8位: {api_key[:8] if api_key else 'None'}...")
        logger.info(f"工作空间ID: {workspace_id}")
        logger.info(f"Embedding模型: {model}")
        logger.info(f"向量维度: {vector_dimension}")

        if not api_key:
            logger.error("❌ DASHSCOPE_API_KEY未配置")
            return False

        if not workspace_id:
            logger.warning("⚠️ DASHSCOPE_WORKSPACE_ID未配置，可能无法访问指定工作空间")

        # 创建OpenAI客户端
        default_headers = {}
        if workspace_id:
            default_headers["X-DashScope-WorkSpace"] = workspace_id

        logger.info(f"OpenAI客户端配置:")
        logger.info(f"  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1")
        logger.info(f"  default_headers: {default_headers}")

        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_headers=default_headers
        )

        # 测试文本
        test_text = "你好，北京广播。"
        logger.info(f"测试文本: '{test_text}'")

        # 尝试调用embeddings.create
        logger.info("正在调用 embeddings.create...")
        try:
            # 先尝试带dimensions参数（text-embedding-v4支持）
            response = client.embeddings.create(
                model=model,
                input=test_text,
                dimensions=vector_dimension,
                encoding_format="float"
            )
            logger.info("✅ 带dimensions参数调用成功")
        except Exception as e:
            # 如果不支持dimensions参数，尝试不带
            logger.warning(f"带dimensions参数调用失败，尝试不带dimensions: {e}")
            try:
                response = client.embeddings.create(
                    model=model,
                    input=test_text,
                    encoding_format="float"
                )
                logger.info("✅ 不带dimensions参数调用成功")
            except Exception as e2:
                logger.error(f"❌ 所有调用尝试均失败: {e2}")
                raise

        # 检查响应
        logger.info(f"响应状态: 成功")
        embedding = response.data[0].embedding
        logger.info(f"向量维度: {len(embedding)}")
        logger.info(f"向量前5个值: {embedding[:5]}")
        logger.info(f"向量类型: {type(embedding[0])}")

        # 验证维度
        if len(embedding) == vector_dimension:
            logger.info(f"✅ 向量维度验证通过: {len(embedding)} == {vector_dimension}")
        else:
            logger.warning(f"⚠️ 向量维度不匹配: {len(embedding)} != {vector_dimension}")

        logger.info("✅✅✅ DashScope Embedding 验证成功！✅✅✅")
        return True

    except ImportError as e:
        logger.error(f"❌ 无法导入openai库: {e}")
        logger.error("请安装: pip install openai>=1.0.0")
        return False

    except Exception as e:
        logger.error(f"❌ DashScope Embedding 验证失败: {e}", exc_info=True)

        # 检查是否为401/403错误
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str:
            logger.error("❌❌❌ 401 UNAUTHORIZED 错误 ❌❌❌")
            logger.error("可能原因:")
            logger.error("1. API密钥无效")
            logger.error("2. 密钥类型错误（确保是DashScope API密钥，非DashVector密钥）")
            logger.error("3. 密钥无权限访问指定工作空间")
            logger.error("")
            logger.error("💡 请立即检查:")
            logger.error("1. 登录阿里云百炼控制台: https://bailian.console.aliyun.com/")
            logger.error("2. 进入'工作空间管理' -> 选择工作空间 'ws-d0d9y5s90m7wq7mv'")
            logger.error("3. 确认'主账号 API-KEY'是否有该空间的授权")
            logger.error("4. 确认使用的是DashScope API密钥（不是DashVector密钥）")

        elif "403" in error_str or "forbidden" in error_str:
            logger.error("❌❌❌ 403 FORBIDDEN 错误 ❌❌❌")
            logger.error("可能原因:")
            logger.error("1. API密钥无权访问指定工作空间")
            logger.error("2. 工作空间ID错误")
            logger.error("3. 账户权限不足")
            logger.error("")
            logger.error("💡 请立即检查:")
            logger.error("1. 确认工作空间ID是否正确: ws-d0d9y5s90m7wq7mv")
            logger.error("2. 确认API密钥是否有该工作空间的访问权限")
            logger.error("3. 联系阿里云管理员检查账户权限")

        return False

def main():
    """主函数"""
    success = verify_embedding()

    if success:
        logger.info("🎉 验证通过，准备启动全流程处理...")
        return 0
    else:
        logger.error("💥 验证失败，请先解决API密钥问题")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)