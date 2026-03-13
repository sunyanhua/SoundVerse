"""
LLM服务 - 大语言模型对话
"""
import logging
from typing import Optional, Dict, Any

import dashscope
from dashscope import Generation

from config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM服务类 - 调用百炼平台大语言模型
    """

    def __init__(self):
        self.initialized = False
        self.dashscope_api_key = settings.DASHSCOPE_API_KEY
        self.default_model = "qwen-plus"  # 百炼平台Qwen-Plus模型
        self.dashscope_workspace_id = settings.DASHSCOPE_WORKSPACE_ID

    async def initialize(self):
        """
        初始化LLM服务
        """
        if self.initialized:
            return

        try:
            # 设置DashScope API密钥
            if self.dashscope_api_key:
                dashscope.api_key = self.dashscope_api_key
                logger.info("DashScope API密钥已配置")
            else:
                logger.warning("DASHSCOPE_API_KEY未配置，LLM服务将使用模拟模式")

            logger.info("LLM服务初始化完成")
            self.initialized = True

        except Exception as e:
            logger.error(f"LLM服务初始化失败: {str(e)}")
            raise

    async def generate_chat_response(
        self,
        query: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        生成聊天回复

        Args:
            query: 用户查询
            context: 上下文信息
            system_prompt: 系统提示词
            **kwargs: 其他参数（temperature, max_tokens等）

        Returns:
            包含回复和相关信息的字典
        """
        try:
            # 确保服务已初始化
            if not self.initialized:
                await self.initialize()

            # 如果没有配置DashScope API密钥，使用模拟模式
            if not self.dashscope_api_key:
                logger.info("DashScope模拟模式：返回模拟回复")
                return await self._generate_mock_response(query, context)

            # 构建消息列表
            messages = []

            # 添加系统提示
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            else:
                # 默认系统提示 - '听听FM'的AI首席播音员'大黄蜂'
                messages.append({
                    "role": "system",
                    "content": """你是'听听FM'的AI首席播音员'大黄蜂'。
语言风格：亲切、爽朗，灵活使用北京方言词汇（如：您呐、得嘞、没毛病、讲究、好嘛、嘛呢、哎哟喂）。
你的任务是当用户的问题在音频库中找不到合适匹配时，用轻松幽默的方式与用户聊天。
回复要简短、有趣、亲切，不超过100字，带有广播播音员的韵味。
如果匹配度不高（相似度低于0.7），先幽默地'打个哈哈'承认匹配度不高，然后自然引导用户搜索'路况'、'天气'或'相声'等广播特色内容。
避免提供实质性的信息回答，而是用玩笑、调侃或电台主持人的口吻回应。
记住：你是电台播音员，要用播音员的口吻与用户互动，营造轻松愉快的广播氛围，让用户感受到老北京广播的亲切感。"""
                })

            # 添加上下文（如果有）
            if context:
                messages.append({"role": "assistant", "content": context})

            # 添加用户查询
            messages.append({"role": "user", "content": query})

            # 调用DashScope Generation API
            call_kwargs = {
                "model": self.default_model,
                "messages": messages,
                "result_format": "message",  # 返回消息格式
                "temperature": 0.8,  # 创造性温度
                "max_tokens": 200,   # 最大token数
                **kwargs
            }
            if self.dashscope_workspace_id:
                call_kwargs["workspace_id"] = self.dashscope_workspace_id
            response = Generation.call(**call_kwargs)

            if response.status_code == 200:
                # 提取回复内容
                reply = response.output.choices[0].message.content
                usage = response.usage

                logger.info(f"LLM生成回复成功: {len(reply)} 字符")

                return {
                    "reply": reply,
                    "usage": {
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.total_tokens,
                    },
                    "model": self.default_model,
                    "success": True,
                }
            else:
                logger.error(f"DashScope API调用失败: {response.code} - {response.message}")
                # API失败时返回模拟回复
                return await self._generate_mock_response(query, context)

        except Exception as e:
            logger.error(f"生成聊天回复失败: {str(e)}")
            # 发生异常时返回模拟回复
            return await self._generate_mock_response(query, context)

    async def _generate_mock_response(
        self,
        query: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成模拟回复（用于开发环境或API失败时）
        """
        # 幽默回复模板 - '听听FM'的AI首席播音员'大黄蜂'风格
        humorous_responses = [
            f"🎵 得嘞您呐！这个问题把我的磁带机卡住了！没毛病，咱们先聊聊实时路况？",
            f"📻 讲究！正在为您翻找合适的广播片段... 这盘磁带有点调皮，不如听听今天的天气播报？",
            f"🎧 您呐，我听不清您在说什么，让我调调天线。对了，想听段相声乐呵乐呵？",
            f"📻 电台信号有点不稳定，让我转动一下旋钮。趁这空档，跟您推荐个广播特色：路况、天气、相声，您想听哪个？",
            f"🎵 这个问题让我想起了老式录音机的倒带声，咻~~~ 咱们换个话题，聊聊广播特色内容怎么样？",
        ]

        # 根据查询长度选择回复
        index = len(query) % len(humorous_responses)
        reply = humorous_responses[index]

        # 如果需要，添加上下文关联
        if context:
            reply = f"（接上文）{reply}"

        logger.info(f"LLM模拟模式回复: {reply}")

        return {
            "reply": reply,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
            "model": "mock",
            "success": True,
        }

    async def generate_search_fallback_response(self, query: str, similarity_score: float = 0.0) -> str:
        """
        生成搜索失败时的专用回复
        当音频搜索找不到合适匹配时调用

        Args:
            query: 用户查询
            similarity_score: 最高相似度分数（0-1之间）
        """
        # 专用提示词 - '听听FM'的AI首席播音员'大黄蜂'
        system_prompt = f"""你是'听听FM'的AI首席播音员'大黄蜂'。
语言风格：亲切、爽朗，适当使用北京方言词汇（如：您呐、得嘞、没毛病、讲究）。
当前情况：用户的问题在音频库中匹配度不高（相似度 {similarity_score:.2f}，低于0.7门槛）。
回复策略：先幽默地'打个哈哈'承认匹配度不高，然后引导用户搜索'路况'、'天气'或'相声'等广播特色内容。
回复要非常简短（1-2句话），充满电台播音员的俏皮感和北京腔。
不要提供实质性的答案，保持轻松调侃的播音员口吻。
示例回复风格：
- "得嘞您呐！这段儿匹配度({similarity_score:.2f})不太高，没毛病！要不咱们聊聊实时路况？"
- "讲究！这个关键词匹配度({similarity_score:.2f})有点低，先跟您打个哈哈。想听听相声还是天气播报？"
- "您呐，这个问题匹配度({similarity_score:.2f})不高，让我先幽默一下。广播特色内容比如路况、天气、相声，您想听哪个？"
直接回复，不要加引号。"""

        try:
            result = await self.generate_chat_response(
                query=query,
                system_prompt=system_prompt,
                temperature=0.9,
                max_tokens=50,  # 更短的回复
            )

            return result["reply"]

        except Exception as e:
            logger.error(f"生成搜索后备回复失败: {str(e)}")
            return f"得嘞您呐！匹配度({similarity_score:.2f})不高，没毛病！要不咱们聊聊路况、天气或相声？"


# 全局LLM服务实例
llm_service = LLMService()


async def init_llm_service():
    """
    初始化LLM服务（在应用启动时调用）
    """
    await llm_service.initialize()


async def generate_chat_reply(
    query: str,
    context: Optional[str] = None,
    system_prompt: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    生成聊天回复（便捷函数）
    """
    return await llm_service.generate_chat_response(
        query=query,
        context=context,
        system_prompt=system_prompt,
        **kwargs
    )


async def generate_search_fallback_reply(query: str, similarity_score: float = 0.0) -> str:
    """
    生成搜索失败时的专用回复（便捷函数）

    Args:
        query: 用户查询
        similarity_score: 最高相似度分数（0-1之间）
    """
    return await llm_service.generate_search_fallback_response(query, similarity_score)