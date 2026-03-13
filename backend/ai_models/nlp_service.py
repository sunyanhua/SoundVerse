"""
NLP服务 - 语义理解
"""
import logging
from typing import List, Optional
import numpy as np
from openai import OpenAI

from config import settings

logger = logging.getLogger(__name__)


class NLPService:
    """
    NLP服务类
    """

    def __init__(self):
        self.initialized = False
        self.vector_dimension = settings.VECTOR_DIMENSION
        self.dashscope_api_key = settings.DASHSCOPE_API_KEY
        self.embedding_model = settings.DASHSCOPE_EMBEDDING_MODEL
        self.dashscope_workspace_id = settings.DASHSCOPE_WORKSPACE_ID
        self.openai_client = None

    async def initialize(self):
        """
        初始化NLP服务
        """
        if self.initialized:
            return

        try:
            # 创建OpenAI兼容客户端
            if self.dashscope_api_key:
                # 彻底删除工作空间头部 - 直接使用API密钥调用
                default_headers = {}  # 空headers，不包含工作空间ID

                self.openai_client = OpenAI(
                    api_key=self.dashscope_api_key,
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    default_headers=default_headers
                )
                logger.info("DashScope OpenAI兼容模式客户端已配置（无工作空间头部）")
            else:
                logger.warning("DASHSCOPE_API_KEY未配置，文本向量化将使用模拟模式")

            logger.info("NLP服务初始化完成")
            self.initialized = True

        except Exception as e:
            logger.error(f"NLP服务初始化失败: {str(e)}")
            raise

    def _normalize_vector(self, vector: List[float]) -> List[float]:
        """
        对向量进行L2归一化，确保模长为1
        """
        try:
            import numpy as np
            v = np.array(vector)
            norm = np.linalg.norm(v)
            if norm > 0:
                v_normalized = v / norm
                return v_normalized.tolist()
            else:
                return vector
        except Exception as e:
            logger.error(f"向量归一化失败: {str(e)}")
            return vector

    async def get_text_embedding(self, text: str, text_type: str = "document") -> Optional[List[float]]:
        """
        获取文本向量表示（嵌入）

        Args:
            text: 输入文本
            text_type: 文本类型，'query'表示查询文本，'document'表示文档文本
                       百炼平台v4模型需要区分，以获得更好的对齐效果
        """
        try:
            # 确保服务已初始化
            if not self.initialized:
                await self.initialize()

            # 如果没有配置DashScope API密钥，使用模拟模式
            if not self.dashscope_api_key:
                logger.info("DashScope模拟模式：返回随机向量")
                np.random.seed(hash(text) % (2**32))
                vector = np.random.randn(self.vector_dimension).tolist()
                # 模拟模式下强制归一化
                norm = np.linalg.norm(vector)
                if norm > 0:
                    vector = (vector / norm).tolist()
                return vector

            # 调用OpenAI兼容API获取文本向量
            try:
                # 构建请求参数
                request_params = {
                    "model": self.embedding_model,
                    "input": text,
                    "encoding_format": "float"
                }

                # 注意：百炼平台text-embedding-v4模型不支持text_type参数
                # 模型会自动处理查询和文档的对齐，无需显式指定
                # 我们只传递基本参数，确保API兼容性

                # 添加dimensions参数（如果模型支持）
                try:
                    request_params["dimensions"] = self.vector_dimension
                except:
                    pass  # 某些模型可能不支持dimensions参数

                response = self.openai_client.embeddings.create(**request_params)
                embedding = response.data[0].embedding
                logger.debug(f"文本向量获取成功: {len(embedding)} 维度")

                # 对向量进行L2归一化，确保模长为1
                # 百炼平台的text-embedding-v4返回的向量可能已经归一化，但为了保险起见，再次归一化
                embedding_normalized = self._normalize_vector(embedding)

                # 验证归一化结果
                norm_after = np.linalg.norm(np.array(embedding_normalized))
                logger.debug(f"向量归一化后模长: {norm_after:.6f}")

                return embedding_normalized

            except Exception as api_error:
                logger.error(f"DashScope OpenAI兼容API调用失败: {str(api_error)}")
                # 尝试不带dimensions参数调用
                try:
                    response = self.openai_client.embeddings.create(
                        model=self.embedding_model,
                        input=text,
                        encoding_format="float"
                    )
                    embedding = response.data[0].embedding
                    logger.debug(f"文本向量获取成功(不带dimensions): {len(embedding)} 维度")

                    # 归一化
                    embedding_normalized = self._normalize_vector(embedding)
                    return embedding_normalized

                except Exception as fallback_error:
                    logger.error(f"DashScope API回退调用失败: {str(fallback_error)}")
                    # 严格模式：API失败时返回None
                    return None

        except Exception as e:
            logger.error(f"获取文本向量失败: {str(e)}")
            return None

    async def batch_get_text_embeddings(self, texts: List[str], text_type: str = "document") -> List[Optional[List[float]]]:
        """
        批量获取文本向量

        Args:
            texts: 文本列表
            text_type: 文本类型，'query'表示查询文本，'document'表示文档文本
        """
        results = []
        for text in texts:
            embedding = await self.get_text_embedding(text, text_type=text_type)
            results.append(embedding)
        return results

    async def calculate_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """
        计算向量相似度（余弦相似度）
        """
        try:
            v1 = np.array(vector1)
            v2 = np.array(vector2)

            # 计算余弦相似度
            similarity = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            return float(similarity)

        except Exception as e:
            logger.error(f"计算相似度失败: {str(e)}")
            return 0.0

    async def extract_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """
        提取关键词
        """
        try:
            # 在实际实现中，这里应该：
            # 1. 调用阿里云关键词提取API
            # 2. 或使用本地模型

            # 模拟返回
            keywords = ["示例", "关键词", "测试"]
            return keywords[:top_k]

        except Exception as e:
            logger.error(f"提取关键词失败: {str(e)}")
            return []

    async def analyze_sentiment(self, text: str) -> dict:
        """
        情感分析
        """
        try:
            # 在实际实现中，这里应该：
            # 1. 调用阿里云情感分析API

            # 模拟返回
            return {
                "sentiment": "positive",  # positive, negative, neutral
                "score": 0.8,  # -1 到 1
                "confidence": 0.9,
            }

        except Exception as e:
            logger.error(f"情感分析失败: {str(e)}")
            return {"sentiment": "neutral", "score": 0.0, "confidence": 0.0}

    async def classify_text(self, text: str, categories: List[str]) -> dict:
        """
        文本分类
        """
        try:
            # 在实际实现中，这里应该：
            # 1. 调用阿里云文本分类API

            # 模拟返回
            results = {}
            for category in categories:
                results[category] = np.random.random()

            # 归一化
            total = sum(results.values())
            if total > 0:
                for key in results:
                    results[key] /= total

            return results

        except Exception as e:
            logger.error(f"文本分类失败: {str(e)}")
            return {category: 0.0 for category in categories}


# 全局NLP服务实例
nlp_service = NLPService()


async def init_nlp_service():
    """
    初始化NLP服务（在应用启动时调用）
    """
    await nlp_service.initialize()


async def get_text_vector(text: str, text_type: str = "document") -> Optional[List[float]]:
    """
    获取文本向量（便捷函数）

    Args:
        text: 输入文本
        text_type: 文本类型，'query'表示查询文本，'document'表示文档文本
    """
    return await nlp_service.get_text_embedding(text, text_type=text_type)


async def batch_get_text_vectors(texts: List[str], text_type: str = "document") -> List[Optional[List[float]]]:
    """
    批量获取文本向量（便捷函数）

    Args:
        texts: 文本列表
        text_type: 文本类型，'query'表示查询文本，'document'表示文档文本
    """
    return await nlp_service.batch_get_text_embeddings(texts, text_type=text_type)