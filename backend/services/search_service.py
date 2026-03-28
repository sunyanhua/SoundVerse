"""
搜索服务 - 向量检索
"""
import json
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Union
import numpy as np
import faiss
import dashvector

from config import settings
from ai_models.nlp_service import get_text_vector

logger = logging.getLogger(__name__)


class VectorSearchService:
    """
    向量搜索服务
    """

    def __init__(self):
        self.index = None
        self.segment_ids = []
        self.vector_dimension = settings.VECTOR_DIMENSION
        self.index_path = Path(settings.FAISS_INDEX_PATH)
        self.metadata_path = self.index_path.with_suffix('.json')
        self.initialized = False  # 初始化标志

        # DashVector配置
        self.use_dashvector = bool(settings.DASHVECTOR_API_KEY and settings.DASHVECTOR_ENDPOINT)
        self.dashvector_client = None
        self.dashvector_collection = None
        self.dashvector_namespace = settings.DASHVECTOR_NAMESPACE
        self.dashvector_collection_name = settings.DASHVECTOR_COLLECTION

        # 如果配置了DashVector，优先使用DashVector
        if self.use_dashvector:
            logger.info("配置使用DashVector向量检索服务")
        else:
            logger.info("DashVector未配置，使用本地FAISS索引")

    async def initialize(self):
        """
        初始化向量索引
        """
        try:
            if self.use_dashvector:
                # 初始化DashVector
                await self._initialize_dashvector()
            else:
                # 初始化FAISS
                await self._initialize_faiss()

            self.initialized = True

        except Exception as e:
            logger.error(f"初始化向量搜索服务失败: {str(e)}")
            raise

    async def create_empty_index(self):
        """
        创建空索引
        """
        # 创建Flat索引（最基础但准确）
        self.index = faiss.IndexFlatL2(self.vector_dimension)

        # 保存索引
        await self.save_index()

    async def load_index(self):
        """
        加载索引
        """
        try:
            # 加载FAISS索引
            self.index = faiss.read_index(str(self.index_path))

            # 加载元数据
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                self.segment_ids = metadata.get('segment_ids', [])

        except Exception as e:
            logger.error(f"加载索引失败: {str(e)}")
            await self.create_empty_index()

    async def save_index(self):
        """
        保存索引
        """
        try:
            # 保存FAISS索引
            faiss.write_index(self.index, str(self.index_path))

            # 保存元数据
            metadata = {
                'segment_ids': self.segment_ids,
                'vector_dimension': self.vector_dimension,
            }

            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"保存索引失败: {str(e)}")

    async def add_segment_vector(self, segment_id: str, vector: List[float]):
        """
        添加音频片段的向量到索引
        """
        if not self.initialized:
            await self.initialize()

        try:
            if self.use_dashvector and self.dashvector_collection:
                # 使用DashVector
                # 创建向量数据
                from dashvector import Doc
                doc = Doc(
                    id=segment_id,
                    vector=vector,
                    fields={"segment_id": segment_id}
                )
                # 插入文档
                result = self.dashvector_collection.upsert(doc)
                if result:
                    logger.debug(f"添加向量到DashVector: {segment_id}")
                else:
                    logger.error(f"添加向量到DashVector失败: {segment_id}")
            else:
                # 使用FAISS
                if not self.index:
                    await self._initialize_faiss()

                # 转换为numpy数组
                vector_array = np.array([vector], dtype=np.float32)

                # 添加到索引
                self.index.add(vector_array)

                # 保存segment_id
                self.segment_ids.append(segment_id)

                # 保存索引
                await self.save_index()

                logger.debug(f"添加向量到FAISS索引: {segment_id}")

        except Exception as e:
            logger.error(f"添加向量到索引失败: {str(e)}")

    async def batch_add_segment_vectors(self, segments: List[Tuple[str, List[float]]]):
        """
        批量添加音频片段向量
        """
        if not self.index:
            await self.initialize()

        try:
            vectors = []
            segment_ids = []

            for segment_id, vector in segments:
                vectors.append(vector)
                segment_ids.append(segment_id)

            if vectors:
                # 转换为numpy数组
                vector_array = np.array(vectors, dtype=np.float32)

                # 批量添加到索引
                self.index.add(vector_array)

                # 保存segment_ids
                self.segment_ids.extend(segment_ids)

                # 保存索引
                await self.save_index()

                logger.info(f"批量添加 {len(segments)} 个向量到索引")

        except Exception as e:
            logger.error(f"批量添加向量失败: {str(e)}")

    async def search_similar_segments(
        self,
        query_vector: List[float],
        top_k: int = 5,
        similarity_threshold: float = settings.SIMILARITY_THRESHOLD,
    ) -> List[Tuple[str, float]]:
        """
        搜索相似的音频片段
        """
        if not self.initialized:
            await self.initialize()

        try:
            if self.use_dashvector and self.dashvector_collection:
                # 使用DashVector搜索
                results = self.dashvector_collection.query(
                    vector=query_vector,
                    topk=top_k,
                    filter=None,  # 可添加过滤条件
                    include_vector=False
                )

                # 处理结果
                similar_segments = []
                for doc in results:
                    raw_score = doc.score
                    # 根据DashVector集合度量方式决定转换方式
                    # 假设集合使用余弦相似度度量，但返回的是余弦距离 (1 - cosine)
                    # 先检查raw_score范围以确定其含义
                    if raw_score >= 0 and raw_score <= 2:
                        # 可能是余弦距离 (0~2)，转换为余弦相似度 (-1~1)
                        # 但通常余弦距离 = 1 - cosine，所以 cosine = 1 - raw_score
                        similarity = 1.0 - raw_score
                        score_type = "余弦距离"
                    elif raw_score >= -1 and raw_score <= 1:
                        # 可能是余弦相似度 (-1~1)
                        similarity = raw_score
                        score_type = "余弦相似度"
                    else:
                        # 其他情况，使用原始转换公式作为回退
                        similarity = 1.0 / (1.0 + raw_score) if raw_score >= 0 else raw_score
                        score_type = "原始分数"
                    logger.info(f"DashVector搜索结果: 片段ID={doc.id}, 原始分数={raw_score:.4f} ({score_type}), 转换后相似度={similarity:.4f}")
                    if similarity >= similarity_threshold:
                        segment_id = doc.id
                        similar_segments.append((segment_id, similarity))
                        logger.info(f"  通过阈值过滤: 相似度={similarity:.4f} ≥ {similarity_threshold}")

                return similar_segments
            else:
                # 使用FAISS搜索
                if not self.index:
                    await self._initialize_faiss()

                if self.index.ntotal == 0:
                    return []

                # 转换为numpy数组
                query_array = np.array([query_vector], dtype=np.float32)

                # 搜索相似向量
                distances, indices = self.index.search(query_array, top_k)

                # 处理结果
                results = []
                for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                    if idx < 0 or idx >= len(self.segment_ids):
                        continue

                    # 将距离转换为相似度分数
                    # L2距离越小表示越相似，转换为0-1的相似度分数
                    similarity = 1.0 / (1.0 + distance)
                    logger.info(f"FAISS搜索结果: 索引位置={idx}, 距离={distance:.4f}, 原始分数={similarity:.4f}")

                    if similarity >= similarity_threshold:
                        segment_id = self.segment_ids[idx]
                        results.append((segment_id, similarity))
                        logger.info(f"  通过阈值过滤: 片段ID={segment_id}, 相似度={similarity:.4f} ≥ {similarity_threshold}")

                return results

        except Exception as e:
            logger.error(f"搜索相似片段失败: {str(e)}")
            return []

    async def search_by_text(
        self,
        query_text: str,
        top_k: int = 5,
        similarity_threshold: float = settings.SIMILARITY_THRESHOLD,
    ) -> List[Tuple[str, float]]:
        """
        通过文本搜索相似的音频片段
        """
        # 获取查询文本的向量（使用query类型）
        query_vector = await get_text_vector(query_text, text_type="query")
        if not query_vector:
            return []

        # 搜索相似片段
        return await self.search_similar_segments(
            query_vector,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

    async def remove_segment(self, segment_id: str) -> bool:
        """
        从索引中移除音频片段
        """
        if not self.index:
            await self.initialize()

        try:
            # 查找segment_id的索引位置
            if segment_id in self.segment_ids:
                idx = self.segment_ids.index(segment_id)

                # 在实际实现中，FAISS不支持直接删除
                # 这里需要重建索引或使用其他方法
                # 暂时记录日志
                logger.warning(f"需要从索引中移除片段: {segment_id} (索引位置: {idx})")
                return True
            else:
                return False

        except Exception as e:
            logger.error(f"移除片段失败: {str(e)}")
            return False

    async def get_index_stats(self) -> dict:
        """
        获取索引统计信息
        """
        if not self.initialized:
            await self.initialize()

        if self.use_dashvector and self.dashvector_collection:
            # 获取DashVector统计信息
            try:
                stats = self.dashvector_collection.stats()
                total_count = 0

                # DashVector stats 是一个 DashVectorResponse 对象，包含 output 字段
                if hasattr(stats, 'output'):
                    output = stats.output
                    # output 是 CollectionStats 对象
                    if hasattr(output, 'total_doc_count'):
                        total_count = output.total_doc_count
                    elif isinstance(output, dict) and 'total_doc_count' in output:
                        total_count = output['total_doc_count']
                    else:
                        # 尝试其他可能的属性名
                        for attr in ['total_count', 'total_docs', 'count', 'doc_count']:
                            if hasattr(output, attr):
                                total_count = getattr(output, attr)
                                break
                            elif isinstance(output, dict) and attr in output:
                                total_count = output[attr]
                                break
                else:
                    # 回退到直接访问 stats 对象
                    for attr in ['total_doc_count', 'total_count', 'total_docs', 'count', 'doc_count']:
                        if hasattr(stats, attr):
                            total_count = getattr(stats, attr)
                            break
                        elif isinstance(stats, dict) and attr in stats:
                            total_count = stats[attr]
                            break

                if total_count == 0:
                    logger.warning(f"无法从stats对象获取文档数: {stats}")

            except Exception as e:
                logger.warning(f"获取DashVector统计信息失败: {str(e)}")
                total_count = 0

            return {
                "engine": "dashvector",
                "total_segments": total_count,
                "vector_dimension": settings.DASHVECTOR_COLLECTION_DIMENSION,
                "segment_ids_count": total_count,
                "collection_name": self.dashvector_collection_name,
                "namespace": self.dashvector_namespace,
            }
        else:
            # FAISS统计信息
            return {
                "engine": "faiss",
                "total_segments": self.index.ntotal if self.index else 0,
                "vector_dimension": self.vector_dimension,
                "segment_ids_count": len(self.segment_ids),
                "index_type": type(self.index).__name__ if self.index else None,
            }

    async def _initialize_dashvector(self):
        """
        初始化DashVector客户端和Collection
        """
        try:
            # 创建DashVector客户端
            self.dashvector_client = dashvector.Client(
                api_key=settings.DASHVECTOR_API_KEY,
                endpoint=settings.DASHVECTOR_ENDPOINT
            )

            collection_name = self.dashvector_collection_name

            # 尝试获取现有集合
            collection = self.dashvector_client.get(collection_name)
            if collection is None:
                # 创建新的Collection，使用余弦相似度
                logger.info(f"创建DashVector Collection: {collection_name}，维度: {settings.DASHVECTOR_COLLECTION_DIMENSION}，度量: cosine")
                create_response = self.dashvector_client.create(
                    name=collection_name,
                    dimension=settings.DASHVECTOR_COLLECTION_DIMENSION,
                    metric='cosine'  # 使用余弦相似度
                )
                if create_response:
                    logger.info(f"DashVector Collection创建请求成功: {collection_name}")
                else:
                    logger.error(f"DashVector Collection创建失败: {collection_name}")
                    raise Exception(f"无法创建DashVector Collection: {collection_name}")

                # 获取新创建的集合对象
                collection = self.dashvector_client.get(collection_name)
                if collection:
                    logger.info(f"成功获取DashVector Collection: {collection_name}")
                else:
                    logger.error(f"无法获取DashVector Collection: {collection_name}")
                    raise Exception(f"无法获取DashVector Collection: {collection_name}")
            else:
                logger.info(f"加载现有DashVector Collection: {collection_name}")
                # 验证集合度量方式（可选）
                try:
                    stats = collection.stats()
                    if hasattr(stats, 'metric'):
                        logger.info(f"集合度量方式: {stats.metric}")
                    else:
                        logger.info("无法获取集合度量方式，假设为cosine")
                except Exception as e:
                    logger.warning(f"无法检查集合属性: {str(e)}")

            self.dashvector_collection = collection
            logger.info("DashVector初始化完成")

        except Exception as e:
            logger.error(f"初始化DashVector失败: {str(e)}")
            raise

    async def _initialize_faiss(self):
        """
        初始化FAISS索引
        """
        try:
            # 创建数据目录
            self.index_path.parent.mkdir(parents=True, exist_ok=True)

            if self.index_path.exists() and self.metadata_path.exists():
                # 加载现有索引
                await self.load_index()
                logger.info(f"加载FAISS向量索引: {len(self.segment_ids)} 个片段")
            else:
                # 创建新索引
                await self.create_empty_index()
                logger.info("创建新的空FAISS向量索引")

        except Exception as e:
            logger.error(f"初始化FAISS失败: {str(e)}")
            raise


# 全局搜索服务实例
search_service = VectorSearchService()


async def init_vector_index():
    """
    初始化向量索引（在应用启动时调用）
    """
    await search_service.initialize()


async def add_audio_segment_to_index(segment_id: str, text: str):
    """
    将音频片段添加到向量索引
    """
    # 获取文本向量（使用document类型）
    vector = await get_text_vector(text, text_type="document")
    if not vector:
        logger.warning(f"无法获取文本向量，跳过索引: {segment_id}")
        return

    # 添加到索引
    await search_service.add_segment_vector(segment_id, vector)


async def search_audio_segments_by_text(
    query_text: str,
    top_k: int = 5,
    similarity_threshold: float = settings.SIMILARITY_THRESHOLD,
) -> List[Tuple[str, float]]:
    """
    通过文本搜索音频片段
    """
    return await search_service.search_by_text(
        query_text,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )


async def get_search_stats() -> dict:
    """
    获取搜索统计信息
    """
    return await search_service.get_index_stats()