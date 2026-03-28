"""
聊天服务
"""
import logging
import random
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
from services.prompt_generation_service import generate_prompts_for_audio_segment
from services.conversational_prompt_service import (
    generate_conversational_suggestions_from_audio,
    enrich_chat_suggestions_with_audio_context,
    get_default_conversational_suggestions,
)

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
            # "ai-sun.vbegin.com.cn",  # 旧格式，无法访问
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

            # 找出所有达到音频回复门槛的候选音频
            eligible_results = [
                result for result in search_result.results
                if result.similarity_score >= settings.AUDIO_REPLY_THRESHOLD
            ]

            if eligible_results:
                # 随机选择一个达到门槛的音频片段
                selected_result = random.choice(eligible_results)
                has_audio_match = True
                audio_segment = selected_result.segment
                best_similarity = selected_result.similarity_score  # 使用选中片段的相似度
                logger.info(f"找到 {len(eligible_results)} 个匹配音频片段（相似度≥{settings.AUDIO_REPLY_THRESHOLD}），随机选择片段ID={audio_segment.id}，相似度 {best_similarity:.4f}")

        if has_audio_match:
            # 创建助手消息（带音频）
            assistant_message = ChatMessage(
                session_id=session.id,
                audio_segment_id=audio_segment.id,
                role="assistant",
                content="",  # 不显示转录文字
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
                "title": "广播音频片段",  # 固定标题，不显示转录文字
                "duration": None,  # 不显示时长
                "source_title": audio_segment.source_title if audio_segment else None,
            } if audio_segment else None,
        )

        # 生成建议：根据用户要求，只在页面加载时通过独立API获取建议
        # 聊天响应中不返回建议，避免每次聊天都刷新提示语句
        suggestions = []

        return ChatResponse(
            message=assistant_response,
            session=session_response if session_id is None else None,  # 新会话时返回会话信息
            suggestions=suggestions,  # 返回空列表，提示语句只通过独立API获取
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
    生成聊天建议（基于音频内容的对话式建议）
    优先从音频内容生成自然的口语化聊天语句
    """
    from sqlalchemy import select, desc
    from shared.models.chat import ChatMessage, ChatSession

    try:
        # 1. 首先从音频内容生成对话式建议
        audio_suggestions = await generate_conversational_suggestions_from_audio(
            db,
            suggestion_count=100  # 生成100个基于音频的建议
        )

        logger.info(f"从音频内容生成 {len(audio_suggestions)} 个对话式建议")

        # 2. 获取用户最近的聊天消息（最多10条）用于主题分析
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

        # 3. 如果有历史消息，分析主题并获取相关建议
        if recent_messages:
            topics = _extract_topics_from_messages(recent_messages)
            topic_suggestions = _generate_suggestions_by_topics(topics)
            # 合并音频建议和主题建议
            all_suggestions = list(set(audio_suggestions + topic_suggestions))
            logger.info(f"结合用户历史主题，合并后建议数: {len(all_suggestions)}")
        else:
            all_suggestions = audio_suggestions

        # 4. 如果建议数量不足，用默认对话建议补充
        if len(all_suggestions) < 80:
            default_suggestions = get_default_conversational_suggestions()
            # 合并，确保不重复
            for suggestion in default_suggestions:
                if suggestion not in all_suggestions:
                    all_suggestions.append(suggestion)
                if len(all_suggestions) >= 120:
                    break
            logger.info(f"用默认建议补充后，建议数: {len(all_suggestions)}")

        # 5. 随机打乱建议列表
        random.shuffle(all_suggestions)

        # 6. 返回足够多的建议（最多150条），让前端随机选择
        return all_suggestions[:150]

    except Exception as e:
        logger.error(f"生成聊天建议失败: {str(e)}")
        # 失败时返回默认对话建议
        return get_default_conversational_suggestions()


def _get_default_suggestions() -> List[str]:
    """返回默认建议列表（扩展版，约150个自然问句）"""
    return [
        # 时间相关（15个）
        "现在几点了？",
        "请问现在是什么时间？",
        "北京时间现在几点了？",
        "能告诉我当前时间吗？",
        "现在是什么时辰了？",
        "您知道现在几点钟了吗？",
        "请问现在准确时间是？",
        "现在时间是多少？",
        "我想知道现在几点了",
        "麻烦您报一下时间",
        "请问现在时刻是？",
        "能报时一下吗？",
        "现在钟点是多少？",
        "请问北京时间？",
        "现在具体是什么时间了？",

        # 新闻相关（20个）
        "今天有什么重要新闻？",
        "最近有什么热点新闻吗？",
        "国际上有哪些重要事件？",
        "国内新闻有哪些值得关注的？",
        "经济新闻有什么最新动态？",
        "社会新闻有什么新进展？",
        "政治新闻有哪些要点？",
        "科技新闻有什么突破？",
        "娱乐新闻有哪些新鲜事？",
        "体育新闻有什么亮点？",
        "今天头条新闻是什么？",
        "最近国际局势怎么样？",
        "国内政策有什么新变化？",
        "财经市场有什么动向？",
        "今天有什么突发新闻吗？",
        "最近有哪些热点话题？",
        "新闻联播有什么重要内容？",
        "广播里有什么新闻节目？",
        "晚间新闻主要报道什么？",
        "早间新闻有哪些内容？",

        # 天气相关（15个）
        "今天天气怎么样？",
        "明天会下雨吗？",
        "最近气温变化大吗？",
        "周末天气适合出行吗？",
        "空气质量怎么样？",
        "今天温度多少度？",
        "明天天气如何？",
        "最近会降温吗？",
        "今天适合户外活动吗？",
        "天气预报说今天怎么样？",
        "今天有风吗？",
        "明天需要带伞吗？",
        "最近天气趋势如何？",
        "今天湿度大吗？",
        "天气对出行有什么影响？",

        # 体育相关（15个）
        "最近有什么体育赛事？",
        "中国女排最近比赛怎么样？",
        "足球联赛有什么最新消息？",
        "篮球比赛有什么看点？",
        "奥运会有哪些项目值得期待？",
        "体育新闻有什么动态？",
        "最近有重要比赛吗？",
        "国家队表现如何？",
        "体育赛事直播有哪些？",
        "运动员有什么新成就？",
        "体育政策有什么变化？",
        "健身运动有什么建议？",
        "体育产业有什么发展？",
        "体育节目有哪些推荐？",
        "运动健康有什么提示？",

        # 生活相关（20个）
        "今天有什么值得关注的事情？",
        "最近流行什么话题？",
        "有什么有趣的故事吗？",
        "能分享一些生活小常识吗？",
        "如何保持健康的生活方式？",
        "生活中有哪些小技巧？",
        "日常消费有什么建议？",
        "家庭生活有什么经验分享？",
        "节假日有什么安排建议？",
        "生活品质如何提升？",
        "日常安全有哪些注意事项？",
        "生活中如何节约时间？",
        "生活节奏怎么调节？",
        "日常生活有什么窍门？",
        "生活压力如何缓解？",
        "生活乐趣从哪里寻找？",
        "生活质量如何改善？",
        "生活方式有哪些选择？",
        "生活态度怎么调整？",
        "生活目标如何设定？",

        # 交通出行（15个）
        "交通状况怎么样？",
        "出行有什么需要注意的？",
        "公共交通有什么最新消息？",
        "自驾出行要注意什么？",
        "旅游景点有什么推荐？",
        "路上堵车吗？",
        "交通政策有什么变化？",
        "出行安全有什么提示？",
        "旅游攻略有哪些？",
        "交通工具有什么选择？",
        "出行方式怎么规划？",
        "旅行目的地推荐哪里？",
        "交通信息如何获取？",
        "出行费用怎么节省？",
        "旅行注意事项有哪些？",

        # 娱乐文化（15个）
        "最近有什么好看的电影？",
        "音乐方面有什么推荐？",
        "文化节庆有哪些活动？",
        "艺术展览有什么值得看的？",
        "传统文化有哪些有趣的内容？",
        "娱乐节目有哪些好看？",
        "文化活动有什么参与方式？",
        "文化艺术如何欣赏？",
        "娱乐产业有什么动态？",
        "文化传承有什么意义？",
        "娱乐休闲怎么安排？",
        "文化差异如何理解？",
        "娱乐方式有哪些选择？",
        "文化体验怎么获得？",
        "娱乐活动有什么推荐？",

        # 教育科技（15个）
        "教育方面有什么新政策？",
        "科技发展有什么最新突破？",
        "人工智能有哪些新应用？",
        "学习方法有什么建议？",
        "数字生活有什么小技巧？",
        "教育趋势有什么变化？",
        "科技创新有什么成果？",
        "学习资源怎么获取？",
        "科技产品如何选择？",
        "教育质量怎么提升？",
        "科技影响有哪些方面？",
        "学习效率如何提高？",
        "科技应用有什么场景？",
        "教育方式有哪些创新？",
        "科技前沿有什么动态？",

        # 财经投资（15个）
        "股市最近行情怎么样？",
        "投资理财有什么建议？",
        "经济形势如何分析？",
        "消费趋势有什么变化？",
        "理财规划要注意什么？",
        "金融市场有什么动向？",
        "投资风险怎么控制？",
        "经济政策有什么影响？",
        "理财方式有哪些选择？",
        "经济指标如何解读？",
        "投资策略怎么制定？",
        "消费行为有什么变化？",
        "财经新闻有什么要点？",
        "理财目标如何实现？",
        "经济前景怎么看？",

        # 健康养生（15个）
        "如何保持身体健康？",
        "饮食养生有什么建议？",
        "运动锻炼要注意什么？",
        "心理健康如何维护？",
        "常见疾病如何预防？",
        "健康管理怎么做？",
        "养生方法有哪些？",
        "运动方式怎么选择？",
        "心理压力如何缓解？",
        "健康饮食怎么安排？",
        "养生保健有什么窍门？",
        "运动效果怎么提升？",
        "心理状态如何调整？",
        "健康检查有什么项目？",
        "养生理念有哪些？",
    ]


def _extract_topics_from_messages(messages: List[str]) -> List[str]:
    """从消息中提取主题"""
    topics = []

    # 关键词到主题的映射（扩展版）
    keyword_to_topic = {
        # 天气相关
        "天气": "天气",
        "气候": "天气",
        "温度": "天气",
        "下雨": "天气",
        "晴天": "天气",
        "刮风": "天气",
        "湿度": "天气",
        "空气质量": "天气",
        "预报": "天气",
        # 新闻相关
        "新闻": "新闻",
        "广播": "新闻",
        "电台": "新闻",
        "时事": "新闻",
        "头条": "新闻",
        "报道": "新闻",
        "事件": "新闻",
        "热点": "新闻",
        "动态": "新闻",
        # 体育相关
        "体育": "体育",
        "运动": "体育",
        "比赛": "体育",
        "赛事": "体育",
        "运动员": "体育",
        "健身": "体育",
        "锻炼": "体育",
        "奥运": "体育",
        "球队": "体育",
        # 时间相关
        "时间": "时间",
        "几点": "时间",
        "钟表": "时间",
        "报时": "时间",
        "时刻": "时间",
        "钟点": "时间",
        "时辰": "时间",
        "现在": "时间",
        # 音乐相关
        "音乐": "音乐",
        "歌曲": "音乐",
        "唱歌": "音乐",
        "旋律": "音乐",
        "歌词": "音乐",
        "歌手": "音乐",
        "演唱会": "音乐",
        "专辑": "音乐",
        # 生活相关
        "生活": "生活",
        "日常": "生活",
        "家庭": "生活",
        "家居": "生活",
        "消费": "生活",
        "品质": "生活",
        "方式": "生活",
        "习惯": "生活",
        # 交通相关
        "交通": "交通",
        "出行": "交通",
        "堵车": "交通",
        "地铁": "交通",
        "公交": "交通",
        "自驾": "交通",
        "旅行": "交通",
        "旅游": "交通",
        # 娱乐相关
        "娱乐": "娱乐",
        "电影": "娱乐",
        "电视": "娱乐",
        "综艺": "娱乐",
        "节目": "娱乐",
        "演出": "娱乐",
        "艺术": "娱乐",
        "文化": "娱乐",
        # 教育相关
        "教育": "教育",
        "学习": "教育",
        "学校": "教育",
        "课程": "教育",
        "教师": "教育",
        "学生": "教育",
        "知识": "教育",
        "培训": "教育",
        # 科技相关
        "科技": "科技",
        "技术": "科技",
        "科学": "科技",
        "创新": "科技",
        "智能": "科技",
        "数字": "科技",
        "网络": "科技",
        "互联网": "科技",
        # 财经相关
        "财经": "财经",
        "经济": "财经",
        "金融": "财经",
        "股票": "财经",
        "投资": "财经",
        "理财": "财经",
        "消费": "财经",
        "市场": "财经",
        # 健康相关
        "健康": "健康",
        "养生": "健康",
        "饮食": "健康",
        "锻炼": "健康",
        "心理": "健康",
        "疾病": "健康",
        "医疗": "健康",
        "保健": "健康",
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
    """基于主题生成相关建议（扩展版，每个主题15个建议）"""
    # 主题到建议的映射（扩展版，包含所有主题）
    topic_to_suggestions = {
        "天气": [
            "今天天气怎么样？",
            "明天会下雨吗？",
            "最近气温变化大吗？",
            "空气质量怎么样？",
            "周末天气适合出行吗？",
            "今天温度多少度？",
            "明天天气如何？",
            "最近会降温吗？",
            "今天适合户外活动吗？",
            "天气预报说今天怎么样？",
            "今天有风吗？",
            "明天需要带伞吗？",
            "最近天气趋势如何？",
            "今天湿度大吗？",
            "天气对出行有什么影响？",
        ],
        "新闻": [
            "今天有什么重要新闻？",
            "最近有什么热点新闻吗？",
            "国际上有哪些重要事件？",
            "国内新闻有哪些值得关注的？",
            "经济新闻有什么最新动态？",
            "社会新闻有什么新进展？",
            "政治新闻有哪些要点？",
            "科技新闻有什么突破？",
            "娱乐新闻有哪些新鲜事？",
            "体育新闻有什么亮点？",
            "今天头条新闻是什么？",
            "最近国际局势怎么样？",
            "国内政策有什么新变化？",
            "财经市场有什么动向？",
            "今天有什么突发新闻吗？",
        ],
        "体育": [
            "最近有什么体育赛事？",
            "中国女排最近比赛怎么样？",
            "足球联赛有什么最新消息？",
            "篮球比赛有什么看点？",
            "奥运会有哪些项目值得期待？",
            "体育新闻有什么动态？",
            "最近有重要比赛吗？",
            "国家队表现如何？",
            "体育赛事直播有哪些？",
            "运动员有什么新成就？",
            "体育政策有什么变化？",
            "健身运动有什么建议？",
            "体育产业有什么发展？",
            "体育节目有哪些推荐？",
            "运动健康有什么提示？",
        ],
        "时间": [
            "现在几点了？",
            "请问现在是什么时间？",
            "北京时间现在几点了？",
            "能告诉我当前时间吗？",
            "现在是什么时辰了？",
            "您知道现在几点钟了吗？",
            "请问现在准确时间是？",
            "现在时间是多少？",
            "我想知道现在几点了",
            "麻烦您报一下时间",
            "请问现在时刻是？",
            "能报时一下吗？",
            "现在钟点是多少？",
            "请问北京时间？",
            "现在具体是什么时间了？",
        ],
        "音乐": [
            "有什么好听的音乐推荐吗？",
            "最近流行什么歌曲？",
            "经典老歌有哪些值得回味？",
            "音乐节有什么活动？",
            "音乐创作有什么新趋势？",
            "音乐方面有什么推荐？",
            "音乐节目有哪些？",
            "音乐风格有哪些变化？",
            "音乐教育有什么建议？",
            "音乐产业有什么动态？",
            "音乐欣赏怎么入门？",
            "音乐创作需要什么条件？",
            "音乐表演有什么技巧？",
            "音乐历史有什么故事？",
            "音乐治疗有什么效果？",
        ],
        "生活": [
            "今天有什么值得关注的事情？",
            "最近流行什么话题？",
            "有什么有趣的故事吗？",
            "能分享一些生活小常识吗？",
            "如何保持健康的生活方式？",
            "生活中有哪些小技巧？",
            "日常消费有什么建议？",
            "家庭生活有什么经验分享？",
            "节假日有什么安排建议？",
            "生活品质如何提升？",
            "日常安全有哪些注意事项？",
            "生活中如何节约时间？",
            "生活节奏怎么调节？",
            "日常生活有什么窍门？",
            "生活压力如何缓解？",
        ],
        "交通": [
            "交通状况怎么样？",
            "出行有什么需要注意的？",
            "公共交通有什么最新消息？",
            "自驾出行要注意什么？",
            "旅游景点有什么推荐？",
            "路上堵车吗？",
            "交通政策有什么变化？",
            "出行安全有什么提示？",
            "旅游攻略有哪些？",
            "交通工具有什么选择？",
            "出行方式怎么规划？",
            "旅行目的地推荐哪里？",
            "交通信息如何获取？",
            "出行费用怎么节省？",
            "旅行注意事项有哪些？",
        ],
        "娱乐": [
            "最近有什么好看的电影？",
            "音乐方面有什么推荐？",
            "文化节庆有哪些活动？",
            "艺术展览有什么值得看的？",
            "传统文化有哪些有趣的内容？",
            "娱乐节目有哪些好看？",
            "文化活动有什么参与方式？",
            "文化艺术如何欣赏？",
            "娱乐产业有什么动态？",
            "文化传承有什么意义？",
            "娱乐休闲怎么安排？",
            "文化差异如何理解？",
            "娱乐方式有哪些选择？",
            "文化体验怎么获得？",
            "娱乐活动有什么推荐？",
        ],
        "教育": [
            "教育方面有什么新政策？",
            "科技发展有什么最新突破？",
            "人工智能有哪些新应用？",
            "学习方法有什么建议？",
            "数字生活有什么小技巧？",
            "教育趋势有什么变化？",
            "科技创新有什么成果？",
            "学习资源怎么获取？",
            "科技产品如何选择？",
            "教育质量怎么提升？",
            "科技影响有哪些方面？",
            "学习效率如何提高？",
            "科技应用有什么场景？",
            "教育方式有哪些创新？",
            "科技前沿有什么动态？",
        ],
        "财经": [
            "股市最近行情怎么样？",
            "投资理财有什么建议？",
            "经济形势如何分析？",
            "消费趋势有什么变化？",
            "理财规划要注意什么？",
            "金融市场有什么动向？",
            "投资风险怎么控制？",
            "经济政策有什么影响？",
            "理财方式有哪些选择？",
            "经济指标如何解读？",
            "投资策略怎么制定？",
            "消费行为有什么变化？",
            "财经新闻有什么要点？",
            "理财目标如何实现？",
            "经济前景怎么看？",
        ],
        "健康": [
            "如何保持身体健康？",
            "饮食养生有什么建议？",
            "运动锻炼要注意什么？",
            "心理健康如何维护？",
            "常见疾病如何预防？",
            "健康管理怎么做？",
            "养生方法有哪些？",
            "运动方式怎么选择？",
            "心理压力如何缓解？",
            "健康饮食怎么安排？",
            "养生保健有什么窍门？",
            "运动效果怎么提升？",
            "心理状态如何调整？",
            "健康检查有什么项目？",
            "养生理念有哪些？",
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