"""
LLM Provider — 统一的 LLM 客户端管理
- 支持 OpenAI 兼容接口和 Anthropic 原生接口
- 指数退避重试
- 结构化返回（不抛异常）
- 支持 chat / function calling / embedding
"""

import time
import logging
from typing import Optional
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMProvider:
    """
    统一的 LLM 客户端
    所有 LLM 调用都通过此类进行，内置重试和错误处理
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
        embedding_model: str = "deepseek-embedding",
        max_retries: int = 3,
        timeout: float = 60.0,
        max_tokens: int = 4096,
        context_window: int = 64000,
        protocol: str = "openai",  # 新增：协议类型
    ):
        self.model = model
        self.embedding_model = embedding_model
        self.max_retries = max_retries
        self.timeout = timeout
        self.max_tokens = max_tokens
        self.context_window = context_window
        self.protocol = protocol

        # 根据协议类型初始化客户端
        if protocol == "anthropic":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=api_key)
                self._is_anthropic = True
            except ImportError:
                raise ImportError("使用 Anthropic 协议需要安装 anthropic 包: pip install anthropic")
        else:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
            self._is_anthropic = False

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[dict] = None,
        timeout: Optional[float] = None,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,  # DeepSeek V4: "high", "medium", "low"
        enable_thinking: bool = False,  # DeepSeek V4: 启用思考模式
    ) -> dict:
        """
        调用 LLM 进行对话

        Args:
            tool_choice: 工具选择策略
                - "auto"（默认，当传入 tools 时自动设置）: LLM 自主决定是否调用工具
                - "required": LLM 必须调用工具
                - "none": LLM 不能调用工具
            reasoning_effort: DeepSeek V4 推理强度 ("high", "medium", "low")
            enable_thinking: DeepSeek V4 是否启用思考模式

        Returns:
            成功: {"success": True, "content": str, "tool_calls": list|None, "usage": dict}
            失败: {"success": False, "error": str}
        """
        if self._is_anthropic:
            return self._chat_anthropic(messages, temperature, tools, tool_choice, max_tokens)
        else:
            return self._chat_openai(
                messages, temperature, tools, tool_choice,
                response_format, timeout, max_tokens,
                reasoning_effort, enable_thinking
            )

    def _chat_openai(
        self,
        messages: list[dict],
        temperature: float,
        tools: Optional[list[dict]],
        tool_choice: Optional[str],
        response_format: Optional[dict],
        timeout: Optional[float],
        max_tokens: Optional[int],
        reasoning_effort: Optional[str] = None,
        enable_thinking: bool = False,
    ) -> dict:
        """OpenAI 兼容接口调用"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout or self.timeout,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"
        if response_format:
            kwargs["response_format"] = response_format

        # DeepSeek V4 新参数
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if enable_thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                choice = resp.choices[0]

                result = {
                    "success": True,
                    "content": choice.message.content,
                    "tool_calls": None,
                    "usage": {
                        "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
                        "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
                        "total_tokens": resp.usage.total_tokens if resp.usage else 0,
                    },
                }

                # DeepSeek V4: reasoning_content 有内容但 content 为空时回退
                if not result["content"]:
                    rc = getattr(choice.message, "reasoning_content", None)
                    if rc:
                        result["content"] = rc

                # 提取 tool_calls（如果存在）
                if choice.message.tool_calls:
                    result["tool_calls"] = [
                        {
                            "id": tc.id,
                            "function": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                        for tc in choice.message.tool_calls
                    ]

                return result

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                logger.warning(
                    f"[LLM] 第 {attempt}/{self.max_retries} 次调用失败: "
                    f"{error_type}: {e}"
                )

                if attempt < self.max_retries:
                    wait = 2 ** attempt  # 2s, 4s, 8s...
                    logger.info(f"[LLM] {wait}s 后重试...")
                    time.sleep(wait)

        # 所有重试都失败
        error_msg = f"LLM 调用失败（已重试 {self.max_retries} 次）: {type(last_error).__name__}: {last_error}"
        logger.error(f"[LLM] {error_msg}")
        return {"success": False, "error": error_msg}

    def _chat_anthropic(
        self,
        messages: list[dict],
        temperature: float,
        tools: Optional[list[dict]],
        tool_choice: Optional[str],
        max_tokens: Optional[int],
    ) -> dict:
        """Anthropic 原生接口调用"""
        # 转换消息格式
        system_msg = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append(msg)

        kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if system_msg:
            kwargs["system"] = system_msg

        # 转换工具格式
        if tools:
            anthropic_tools = []
            for tool in tools:
                if tool.get("type") == "function":
                    func = tool["function"]
                    anthropic_tools.append({
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    })
            kwargs["tools"] = anthropic_tools

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.messages.create(**kwargs)

                # 提取内容
                content = ""
                tool_calls = None

                for block in resp.content:
                    if block.type == "text":
                        content += block.text
                    elif block.type == "tool_use":
                        if tool_calls is None:
                            tool_calls = []
                        tool_calls.append({
                            "id": block.id,
                            "function": block.name,
                            "arguments": json.dumps(block.input),
                        })

                result = {
                    "success": True,
                    "content": content,
                    "tool_calls": tool_calls,
                    "usage": {
                        "prompt_tokens": resp.usage.input_tokens,
                        "completion_tokens": resp.usage.output_tokens,
                        "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
                    },
                }

                return result

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                logger.warning(
                    f"[LLM] 第 {attempt}/{self.max_retries} 次调用失败: "
                    f"{error_type}: {e}"
                )

                if attempt < self.max_retries:
                    wait = 2 ** attempt
                    logger.info(f"[LLM] {wait}s 后重试...")
                    time.sleep(wait)

        # 所有重试都失败
        error_msg = f"LLM 调用失败（已重试 {self.max_retries} 次）: {type(last_error).__name__}: {last_error}"
        logger.error(f"[LLM] {error_msg}")
        return {"success": False, "error": error_msg}

    def chat_stream(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,  # DeepSeek V4
        enable_thinking: bool = False,  # DeepSeek V4
    ):
        """
        流式调用 LLM（逐 token 返回）

        Yields:
            - {"type": "token", "content": str}          文本 token
            - {"type": "tool_calls", "tool_calls": list}  工具调用（完整）
            - {"type": "usage", "usage": dict}            token 用量
            - {"type": "error", "error": str}             错误
        """
        if self._is_anthropic:
            yield from self._stream_anthropic(messages, temperature, tools, tool_choice, max_tokens)
        else:
            yield from self._stream_openai(
                messages, temperature, tools, tool_choice, max_tokens,
                reasoning_effort, enable_thinking
            )

    def _stream_openai(
        self,
        messages: list[dict],
        temperature: float,
        tools: Optional[list[dict]],
        tool_choice: Optional[str],
        max_tokens: Optional[int],
        reasoning_effort: Optional[str] = None,
        enable_thinking: bool = False,
    ):
        """OpenAI 兼容接口流式调用"""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        # DeepSeek V4 新参数
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        if enable_thinking:
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

        try:
            stream = self.client.chat.completions.create(**kwargs)

            # 用于组装 tool_calls
            assembled_tool_calls: dict[int, dict] = {}
            usage_info = None

            for chunk in stream:
                # usage 信息在最后一个 chunk
                if chunk.usage:
                    usage_info = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # DeepSeek R1 的思考内容（reasoning_content）
                reasoning = getattr(delta, 'reasoning_content', None)
                if reasoning:
                    yield {"type": "thinking_token", "content": reasoning}

                # 文本 token
                if delta.content:
                    yield {"type": "token", "content": delta.content}

                # tool_calls 片段（需要组装）
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in assembled_tool_calls:
                            assembled_tool_calls[idx] = {
                                "id": tc_delta.id or "",
                                "function": tc_delta.function.name or "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            assembled_tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function and tc_delta.function.name:
                            assembled_tool_calls[idx]["function"] = tc_delta.function.name
                        if tc_delta.function and tc_delta.function.arguments:
                            assembled_tool_calls[idx]["arguments"] += tc_delta.function.arguments

            # 流结束：返回组装好的 tool_calls
            if assembled_tool_calls:
                yield {"type": "tool_calls", "tool_calls": list(assembled_tool_calls.values())}

            if usage_info:
                yield {"type": "usage", "usage": usage_info}

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    def _stream_anthropic(
        self,
        messages: list[dict],
        temperature: float,
        tools: Optional[list[dict]],
        tool_choice: Optional[str],
        max_tokens: Optional[int],
    ):
        """Anthropic 原生接口流式调用"""
        import json

        # 转换消息格式
        system_msg = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append(msg)

        kwargs = {
            "model": self.model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if system_msg:
            kwargs["system"] = system_msg

        # 转换工具格式
        if tools:
            anthropic_tools = []
            for tool in tools:
                if tool.get("type") == "function":
                    func = tool["function"]
                    anthropic_tools.append({
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get("parameters", {}),
                    })
            kwargs["tools"] = anthropic_tools

        try:
            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield {"type": "token", "content": text}

                # 获取最终消息
                final_message = stream.get_final_message()
                if final_message.usage:
                    yield {
                        "type": "usage",
                        "usage": {
                            "prompt_tokens": final_message.usage.input_tokens,
                            "completion_tokens": final_message.usage.output_tokens,
                            "total_tokens": final_message.usage.input_tokens + final_message.usage.output_tokens,
                        },
                    }

        except Exception as e:
            yield {"type": "error", "error": str(e)}

    def embed(self, texts: list[str]) -> list[list[float]]:
        """
        调用 Embedding API

        Returns:
            成功: list[list[float]]
            失败: 抛出异常（embedding 失败通常是不可恢复的）
        """
        if self._is_anthropic:
            raise NotImplementedError("Anthropic 暂不支持 Embedding API")

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=texts,
                )
                return [r.embedding for r in resp.data]
            except Exception as e:
                last_error = e
                logger.warning(
                    f"[Embedding] 第 {attempt}/{self.max_retries} 次调用失败: {e}"
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

        raise RuntimeError(
            f"Embedding 调用失败（已重试 {self.max_retries} 次）: {last_error}"
        )

    def embed_one(self, text: str) -> list[float]:
        """单条文本 embedding"""
        return self.embed([text])[0]

    def __repr__(self):
        return (
            f"<LLMProvider model={self.model} "
            f"protocol={self.protocol} "
            f"retries={self.max_retries}>"
        )


def create_default_provider() -> LLMProvider:
    """
    从配置创建默认的 LLMProvider 实例
    """
    from config import AppConfig
    config = AppConfig.from_env()

    # 获取默认模型配置
    model_config = config.get_model_config(config.default_model)
    if not model_config:
        raise ValueError(f"未找到默认模型配置: {config.default_model}")

    if not model_config.api_key:
        raise ValueError(f"未找到 API key，请在 models.yaml 中配置")

    return LLMProvider(
        api_key=model_config.api_key,
        base_url=model_config.base_url,
        model=model_config.model,
        max_tokens=model_config.max_tokens,
        context_window=model_config.context_window,
        protocol=model_config.protocol,
    )
