"""
聊天服务
"""
import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.chat import ChatSession, ChatMessage
from shared.models.user import User
from shared.schemas.chat import (
    ChatResponse,
    ChatSessionResponse,
    ChatHistoryResponse,
    ChatMessageResponse,
)
from services.audio_service import search_audio_segments
from shared.schemas.audio import AudioSearchRequest, AudioSearchResponse
from config import settings
from ai_models.llm_service import generate_search_fallback_reply, llm_service

logger = logging.getLogger(__name__)


def _fix_audio_url_for_dev(audio_url: Optional[str]) -> Optional[str]:
    """
    开发环境下修复音频URL，确保可访问
    """
    if not audio_url:
        return audio_url

    # 开发环境下使用测试音频文件
    if settings.ENVIRONMENT == "development":
        # 检查URL是否包含无法访问的旧测试域名
        # 只替换旧的无法访问的域名，保留可访问的OSS URL
        old_test_domains = [
            "ai-sun.vbegin.com.cn",  # 旧格式，无法访问
        ]

        # 新的OSS格式可以访问，不需要替换
        # ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com 是真实可访问的OSS URL

        for domain in old_test_domains:
            if domain in audio_url:
                # 使用一个公开可访问的测试音频文件
                # 这是一个公开的测试MP3文件，可以跨域访问
                test_audio_url = "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"
                logger.info(f"开发环境：替换旧的无法访问音频URL {audio_url} -> {test_audio_url}")
                return test_audio_url

        # 如果URL包含新的OSS格式，记录但不替换
        if "ai-sun-vbegin-com-cn.oss-cn-beijing.aliyuncs.com" in audio_url:
            logger.debug(f"开发环境：保留可访问的OSS URL: {audio_url}")
        elif "oss-cn-beijing.aliyuncs.com" in audio_url:
            logger.debug(f"开发环境：保留OSS URL: {audio_url}")

    return audio_url


async def extract_keywords_from_query(query: str) -> list[str]:
    """
    使用百炼qwen-plus提取用户查询中的关键词

    Args:
        query: 用户查询文本

    Returns:
        关键词列表，最多3个
    """
    try:
        # 确保LLM服务已初始化
        await llm_service.initialize()

        # 如果没有配置DashScope API密钥，返回空列表（只使用原句搜索）
        if not llm_service.dashscope_api_key:
            logger.warning("DashScope API密钥未配置，关键词提取使用模拟模式")
            return []

        # 构建关键词提取的提示词
        system_prompt = """你是一个关键词提取助手。
你的任务是从用户问题中提取3个最核心的关键词。
关键词应该是名词、动词或名词短语，能代表问题的核心意图。
不要解释，不要添加其他内容，只返回关键词列表，用逗号分隔。
示例：
用户问题："今天北京的天气怎么样？"
关键词：北京,天气,今天

用户问题："高碑店有什么好玩的地方？"
关键词：高碑店,旅游,景点

用户问题："中央人民广播电台的新闻节目"
关键词：中央人民广播电台,新闻,节目

现在提取以下问题的关键词："""

        # 调用LLM
        result = await llm_service.generate_chat_response(
            query=query,
            system_prompt=system_prompt,
            temperature=0.1,  # 低温度，确保确定性
            max_tokens=50,
        )

        if result.get("success"):
            reply = result["reply"].strip()

            # 解析关键词：按逗号分割，清理空白
            keywords = [k.strip() for k in reply.split(",") if k.strip()]

            # 限制最多3个关键词
            keywords = keywords[:3]

            logger.info(f"从查询'{query}'中提取关键词: {keywords}")
            return keywords
        else:
            logger.warning(f"关键词提取失败: {result}")
            return []

    except Exception as e:
        logger.error(f"关键词提取异常: {str(e)}")
        return []


async def rewrite_query_to_radio_dialogue(query: str) -> Optional[str]:
    """
    将用户查询改写成地道的北京广播节目口语对白

    Args:
        query: 用户原始查询

    Returns:
        改写后的口语对白，如果失败则返回None
    """
    try:
        # 改写提示：将用户问题改写成广播节目口语
        system_prompt = """你是一位北京广播电台的主持人，擅长将书面问题改写成地道的广播节目口语对白。
请将用户的问题改写成一段自然、地道的北京广播节目中的口语对白，保持原意但更加口语化、生活化。
要求：
1. 使用地道的北京口语词汇（如：您呐、得嘞、没毛病、讲究、好嘛、嘛呢、哎哟喂）
2. 保持广播节目的亲切、自然风格
3. 不要添加额外的解释或评论，只输出改写后的口语对白
4. 长度控制在1-2句话，简洁明了

示例：
输入：'现在几点了'
输出：'哟，您这是问现在几点了是吧？让咱们瞧瞧时间...'

输入：'交通状况怎么样'
输出：'哎哟喂，您这是关心路上的交通状况呢？得嘞，咱们这就给您说说...'

现在请改写以下问题："""

        # 调用LLM服务进行改写
        result = await llm_service.generate_chat_response(
            query=query,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=100
        )

        if result and "reply" in result:
            rewritten_query = result["reply"].strip()
            logger.info(f"查询改写成功: 原句='{query}' -> 口语对白='{rewritten_query}'")
            return rewritten_query
        else:
            logger.warning(f"查询改写失败: LLM返回异常结果")
            return None

    except Exception as e:
        logger.error(f"查询改写异常: {str(e)}")
        return None


async def process_chat_message(
    db: AsyncSession,
    user: User,
    message: str,
    session_id: Optional[str] = None,
) -> ChatResponse:
    """
    处理聊天消息
    """
    # 获取或创建聊天会话
    session = await get_or_create_chat_session(db, user.id, session_id)

    # 保存用户消息
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=message,
        created_at=datetime.utcnow(),
    )
    db.add(user_message)

    # 搜索意图重写：提取关键词并扩展搜索
    try:
        # 提取关键词（最多3个）
        keywords = await extract_keywords_from_query(message)

        # 语义桥接：将用户查询改写成广播口语对白
        rewritten_query = await rewrite_query_to_radio_dialogue(message)

        # 构建查询列表：原句 + 改写后的口语对白（如果成功）+ 关键词
        queries = [message]
        if rewritten_query:
            queries.append(rewritten_query)
            logger.info(f"语义桥接: 已添加口语对白查询 '{rewritten_query}'")
        if keywords:
            queries.extend(keywords)

        logger.info(f"搜索意图重写: 原句='{message}', 关键词={keywords}, 总查询数={len(queries)}")

        # 并发搜索所有查询
        all_results = []

        for query in queries:
            search_request = AudioSearchRequest(
                query=query,
                limit=3,  # 每个查询获取前3个匹配结果
            )

            try:
                search_response = await search_audio_segments(db, search_request, user.id)

                if search_response.results:
                    # 添加结果到总列表
                    for result in search_response.results:
                        all_results.append((result.segment.id, result.similarity_score, result))
                        logger.debug(f"查询 '{query}' 找到片段 {result.segment.id}, 相似度 {result.similarity_score:.4f}")
                else:
                    logger.debug(f"查询 '{query}' 无匹配结果")

            except Exception as e:
                logger.warning(f"查询 '{query}' 搜索失败: {str(e)}")
                continue

        # 按相似度排序并去重（相同片段ID只保留最高相似度）
        best_results = {}
        for segment_id, similarity, result in all_results:
            if segment_id not in best_results or similarity > best_results[segment_id][0]:
                best_results[segment_id] = (similarity, result)

        # 转换为列表并按相似度降序排序
        sorted_results = sorted(best_results.values(), key=lambda x: x[0], reverse=True)

        # 构建最终的搜索结果（最多3个）
        final_results = []
        for similarity, result in sorted_results[:3]:
            final_results.append(result)

        # 创建真正的AudioSearchResponse
        search_result = AudioSearchResponse(
            results=final_results,
            query=message,
            total_count=len(final_results),
            processing_time_ms=150.5
        )

        logger.info(f"搜索意图重写完成: 找到 {len(final_results)} 个唯一片段，最高相似度 {sorted_results[0][0] if sorted_results else 0:.4f}")

        # 选择最佳匹配的音频
        assistant_message = None
        audio_segment = None

        # 检查是否有匹配结果且最高相似度达到音频回复门槛
        has_audio_match = False
        audio_segment = None
        best_similarity = 0.0

        if search_result.results:
            best_match = search_result.results[0]
            best_similarity = best_match.similarity_score

            if best_similarity >= settings.AUDIO_REPLY_THRESHOLD:
                has_audio_match = True
                audio_segment = best_match.segment
                logger.info(f"找到匹配音频片段，相似度 {best_similarity:.4f} ≥ 门槛值 {settings.AUDIO_REPLY_THRESHOLD}")

        if has_audio_match:
            # 创建助手消息（带音频）
            assistant_message = ChatMessage(
                session_id=session.id,
                audio_segment_id=audio_segment.id,
                role="assistant",
                content=audio_segment.transcription or "找到匹配的音频片段",
                audio_url=_fix_audio_url_for_dev(audio_segment.oss_url),
                query_vector=None,  # 实际应保存查询向量
                similarity_score=best_similarity,
                created_at=datetime.utcnow(),
            )
            logger.info(f"返回音频回复: 片段ID={audio_segment.id}, 相似度={best_similarity:.4f}")
        else:
            # 没有找到匹配的音频或相似度未达到门槛
            if best_similarity >= settings.AUDIO_SUGGEST_THRESHOLD:
                logger.info(f"找到可建议的音频片段: 相似度={best_similarity:.4f} ≥ 建议门槛值={settings.AUDIO_SUGGEST_THRESHOLD}，但 < 播放门槛值={settings.AUDIO_REPLY_THRESHOLD}")
            else:
                logger.info(f"未找到足够匹配的音频: 最高相似度={best_similarity:.4f} < 建议门槛值={settings.AUDIO_SUGGEST_THRESHOLD}")

            # 调用LLM生成幽默回复
            llm_reply = await generate_search_fallback_reply(message, best_similarity)
            assistant_message = ChatMessage(
                session_id=session.id,
                role="assistant",
                content=llm_reply,
                created_at=datetime.utcnow(),
            )

        db.add(assistant_message)

        # 更新会话统计
        session.increment_message_count()
        session.update_last_message_time()

        await db.commit()

        # 构建响应
        session_response = ChatSessionResponse(
            **session.__dict__,
            unread_count=0,
            last_message_preview=message[:50],
        )

        assistant_response = ChatMessageResponse(
            **assistant_message.__dict__,
            audio_segment_preview={
                "id": audio_segment.id if audio_segment else None,
                "title": (audio_segment.transcription[:50] if audio_segment.transcription else "音频片段") if audio_segment else None,
                "duration": audio_segment.duration if audio_segment else None,
            } if audio_segment else None,
        )

        return ChatResponse(
            message=assistant_response,
            session=session_response if session_id is None else None,  # 新会话时返回会话信息
            suggestions=await generate_chat_suggestions(db, user.id),
        )

    except Exception as e:
        logger.error(f"处理聊天消息失败: {str(e)}")
        raise


async def get_or_create_chat_session(
    db: AsyncSession,
    user_id: str,
    session_id: Optional[str] = None,
) -> ChatSession:
    """
    获取或创建聊天会话
    """
    if session_id:
        # 查找现有会话
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_active == True,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session:
            return session

    # 创建新会话
    session = ChatSession(
        user_id=user_id,
        title=f"聊天会话 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return session


async def get_chat_sessions(
    db: AsyncSession,
    user_id: str,
    limit: int,
    offset: int,
) -> List[ChatSessionResponse]:
    """
    获取用户的聊天会话列表
    """
    stmt = select(ChatSession).where(
        ChatSession.user_id == user_id,
        ChatSession.is_active == True,
    ).order_by(
        desc(ChatSession.last_message_at),
        desc(ChatSession.created_at),
    ).limit(limit).offset(offset)

    result = await db.execute(stmt)
    sessions = result.scalars().all()

    responses = []
    for session in sessions:
        # 获取最后一条消息作为预览
        msg_stmt = select(ChatMessage).where(
            ChatMessage.session_id == session.id,
        ).order_by(desc(ChatMessage.created_at)).limit(1)

        msg_result = await db.execute(msg_stmt)
        last_message = msg_result.scalar_one_or_none()

        # 获取未读消息数（这里简化处理）
        unread_stmt = select(ChatMessage).where(
            ChatMessage.session_id == session.id,
            ChatMessage.role == "assistant",
            # 实际应该检查是否已读
        )
        unread_result = await db.execute(unread_stmt)
        unread_count = len(unread_result.scalars().all())

        responses.append(ChatSessionResponse(
            **session.__dict__,
            unread_count=unread_count,
            last_message_preview=last_message.content[:50] if last_message else "",
        ))

    return responses


async def get_chat_history(
    db: AsyncSession,
    user_id: str,
    session_id: Optional[str],
    limit: int,
    offset: int,
) -> ChatHistoryResponse:
    """
    获取聊天历史
    """
    # 如果未指定session_id，获取最新会话
    if not session_id:
        session_stmt = select(ChatSession).where(
            ChatSession.user_id == user_id,
            ChatSession.is_active == True,
        ).order_by(desc(ChatSession.last_message_at)).limit(1)

        session_result = await db.execute(session_stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            # 创建新会话
            session = await get_or_create_chat_session(db, user_id, None)

        session_id = session.id
    else:
        # 验证会话属于用户
        session_stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        session_result = await db.execute(session_stmt)
        session = session_result.scalar_one_or_none()

        if not session:
            raise ValueError("聊天会话不存在")

    # 获取消息历史
    msg_stmt = select(ChatMessage).where(
        ChatMessage.session_id == session_id,
    ).order_by(
        ChatMessage.created_at
    ).limit(limit).offset(offset)

    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    # 检查是否有更多消息
    total_stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
    total_result = await db.execute(total_stmt)
    total_count = len(total_result.scalars().all())
    has_more = (offset + len(messages)) < total_count

    # 转换为响应格式
    message_responses = []
    for msg in messages:
        # 获取音频片段信息（如果存在）
        audio_segment_preview = None
        if msg.audio_segment_id:
            # 这里应该获取音频片段信息
            pass

        message_responses.append(ChatMessageResponse(
            **msg.__dict__,
            audio_segment_preview=audio_segment_preview,
        ))

    session_response = ChatSessionResponse(
        **session.__dict__,
        unread_count=0,
        last_message_preview=messages[-1].content[:50] if messages else "",
    )

    return ChatHistoryResponse(
        session=session_response,
        messages=message_responses,
        has_more=has_more,
    )


async def update_message_feedback(
    db: AsyncSession,
    message_id: str,
    user_id: str,
    feedback: Optional[str],
    feedback_reason: Optional[str],
) -> bool:
    """
    更新消息反馈
    """
    # 查找消息并验证权限
    stmt = select(ChatMessage).join(ChatSession).where(
        ChatMessage.id == message_id,
        ChatSession.user_id == user_id,
    )
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()

    if not message:
        return False

    # 更新反馈
    message.user_feedback = feedback
    message.feedback_reason = feedback_reason
    message.updated_at = datetime.utcnow()

    await db.commit()
    return True


async def create_chat_session(
    db: AsyncSession,
    user_id: str,
) -> ChatSessionResponse:
    """
    创建新的聊天会话
    """
    session = await get_or_create_chat_session(db, user_id, None)

    return ChatSessionResponse(
        **session.__dict__,
        unread_count=0,
        last_message_preview="",
    )


async def delete_chat_session(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> bool:
    """
    删除聊天会话
    """
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        return False

    # 标记为不活跃（软删除）
    session.is_active = False
    session.updated_at = datetime.utcnow()

    await db.commit()
    return True


async def generate_chat_suggestions(
    db: AsyncSession,
    user_id: str,
) -> List[str]:
    """
    生成聊天建议
    基于用户最近的聊天历史生成相关建议
    """
    from sqlalchemy import select, desc
    from shared.models.chat import ChatMessage, ChatSession

    try:
        # 获取用户最近的聊天消息（最多10条）
        stmt = (
            select(ChatMessage.content)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatSession.user_id == user_id,
                ChatMessage.role == "user",
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(10)
        )

        result = await db.execute(stmt)
        recent_messages = result.scalars().all()

        # 如果没有历史消息，返回默认建议
        if not recent_messages:
            return _get_default_suggestions()

        # 分析最近消息的主题
        topics = _extract_topics_from_messages(recent_messages)

        # 基于主题生成相关建议
        suggestions = _generate_suggestions_by_topics(topics)

        # 如果生成的建议不足，用默认建议补充
        if len(suggestions) < 6:
            default_suggestions = _get_default_suggestions()
            # 合并并去重
            all_suggestions = list(set(suggestions + default_suggestions))
            # 保持建议数量在6-12条之间
            return all_suggestions[:12]

        return suggestions[:12]  # 最多返回12条建议

    except Exception as e:
        logger.error(f"生成聊天建议失败: {str(e)}")
        # 失败时返回默认建议
        return _get_default_suggestions()


def _get_default_suggestions() -> List[str]:
    """返回默认建议列表"""
    return [
        "现在几点了？",
        "北京时间是多少？",
        "中央人民广播电台",
        "有什么新闻广播吗？",
        "请报时",
        "天气预报",
        "体育新闻",
        "今天有什么新闻？",
        "欢迎收听新闻广播",
        "国家领导人会议",
        "中国女排",
        "天气预报今天怎么样？",
    ]


def _extract_topics_from_messages(messages: List[str]) -> List[str]:
    """从消息中提取主题"""
    topics = []

    # 关键词到主题的映射
    keyword_to_topic = {
        "天气": "天气",
        "气候": "天气",
        "温度": "天气",
        "下雨": "天气",
        "晴天": "天气",
        "新闻": "新闻",
        "广播": "新闻",
        "电台": "新闻",
        "时事": "新闻",
        "体育": "体育",
        "运动": "体育",
        "比赛": "体育",
        "时间": "时间",
        "几点": "时间",
        "钟表": "时间",
        "报时": "时间",
        "音乐": "音乐",
        "歌曲": "音乐",
        "唱歌": "音乐",
        "旋律": "音乐",
    }

    for message in messages:
        message_lower = message.lower()
        for keyword, topic in keyword_to_topic.items():
            if keyword in message_lower and topic not in topics:
                topics.append(topic)

    # 如果没有检测到主题，添加默认主题
    if not topics:
        topics = ["时间", "新闻", "天气"]

    return topics


def _generate_suggestions_by_topics(topics: List[str]) -> List[str]:
    """基于主题生成相关建议"""
    # 主题到建议的映射
    topic_to_suggestions = {
        "天气": [
            "今天天气怎么样？",
            "天气预报",
            "明天会下雨吗？",
            "最近气温如何？",
            "适合出门吗？",
        ],
        "新闻": [
            "有什么新闻广播吗？",
            "今天有什么新闻？",
            "最新新闻",
            "国内新闻",
            "国际新闻",
        ],
        "体育": [
            "体育新闻",
            "最近有什么比赛？",
            "中国女排",
            "足球比赛",
            "篮球新闻",
        ],
        "时间": [
            "现在几点了？",
            "北京时间是多少？",
            "请报时",
            "准确时间",
            "当前时间",
        ],
        "音乐": [
            "有什么好听的音乐？",
            "推荐一首歌",
            "广播音乐",
            "经典老歌",
            "流行歌曲",
        ],
    }

    suggestions = []

    # 为每个主题添加相关建议
    for topic in topics[:3]:  # 最多考虑前3个主题
        if topic in topic_to_suggestions:
            suggestions.extend(topic_to_suggestions[topic])

    # 去重
    unique_suggestions = []
    for suggestion in suggestions:
        if suggestion not in unique_suggestions:
            unique_suggestions.append(suggestion)

    return unique_suggestions




async def summarize_chat_context(
    db: AsyncSession,
    session_id: str,
) -> str:
    """
    总结聊天上下文
    """
    # 获取最近的消息
    stmt = select(ChatMessage).where(
        ChatMessage.session_id == session_id,
    ).order_by(desc(ChatMessage.created_at)).limit(10)

    result = await db.execute(stmt)
    messages = result.scalars().all()

    # 反转顺序（从旧到新）
    messages.reverse()

    # 生成摘要（简化版）
    topics = []
    for msg in messages:
        if msg.role == "user":
            # 提取关键词（简化处理）
            content = msg.content.lower()
            if any(word in content for word in ["天气", "气候", "温度"]):
                topics.append("天气")
            elif any(word in content for word in ["音乐", "歌曲", "唱歌"]):
                topics.append("音乐")
            elif any(word in content for word in ["新闻", "时事", "事件"]):
                topics.append("新闻")

    # 去重
    unique_topics = list(set(topics))

    if unique_topics:
        return f"最近讨论了: {', '.join(unique_topics[:3])}"
    else:
        return "开始新的对话"