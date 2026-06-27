"""
Allen Agent — ReAct 多步推理 + Function Calling
核心能力：
  - 用 LLM 原生 Function Calling 自主决策和执行工具
  - ReAct 循环：Think → Act → Observe → Think → ...
  - 对话记忆：支持多轮上下文
  - 决策追踪：记录每一步
  - 安全护栏：输入过滤 + 输出脱敏 + 工具权限
"""

import json
import threading
from typing import Optional

from agents.base import BaseAgent
from agents.system_prompt import build_system_prompt
from agents.compression import ConversationCompressor
from agents.react_loop import execute_task_stream as _exec_react, run_stream as _run_react
from schemas.tool import ToolResult


class AllenAgent(BaseAgent):
    """
    Allen Agent（ReAct 模式）

    通过 LLM 原生 Function Calling 自主决策和执行工具，
    支持多步推理循环和多轮对话。
    """

    def __init__(
        self,
        name: str = "Allen_Agent",
        llm_provider=None,
        memory=None,
        tracer=None,
        allen_memory=None,
        guardrail=None,
        reflect_engine=None,
        max_steps: int = 5,
    ):
        super().__init__(name)
        self.llm_provider = llm_provider
        self.memory = memory
        self.tracer = tracer
        self.allen_memory = allen_memory
        self.guardrail = guardrail
        self.reflect_engine = reflect_engine
        self._stream_usage: dict = {}  # 最新流式 token 消耗，供状态栏读取
        self.max_steps = max_steps
        self._last_tool_results: dict[str, str] = {}  # tool_name → last result content
        self._auto_confirm = False  # 用户选择"同类自动执行"后跳过确认
        self._cancel_event = threading.Event()  # ESC 取消信号
        self._current_conversation_id: str | None = None  # 当前对话 ID（用于追加 summary）
        self.compressor = ConversationCompressor(llm_provider)

    def reset_auto_confirm(self):
        """重置自动确认状态（新对话时调用）"""
        self._auto_confirm = False

    def set_llm_provider(self, provider):
        """切换 LLM Provider（运行时模型切换）"""
        self.llm_provider = provider

    def _build_system_prompt(self) -> str:
        """构建系统提示词（运行时动态注入）"""
        tools_desc = "\n".join([
            f"- {t.name}: {t.description}"
            for t in self.tools.values()
        ])

        # 从磁盘重新读 Allen.md（确保永远是最新版）
        allen_context = ""
        if self.allen_memory:
            self.allen_memory._load()
            if self.allen_memory.has_content():
                allen_context = f"\n{self.allen_memory.get_context()}\n"

        return build_system_prompt(tools_desc, allen_context)

    def _check_and_compress(self, force: bool = False):
        """检查 token 数并在需要时触发压缩（委托给 compressor）"""
        self.compressor.check_and_compress(
            memory=self.memory,
            current_conversation_id=self._current_conversation_id,
            force=force,
        )

    def run(self, query: str, verbose: bool = True) -> dict:
        """
        运行 Agent（ReAct 循环）

        流程：
        1. 初始化 memory 和 tracer
        2. 循环：
           a. 调用 LLM（带 tools + history）
           b. 如果返回 tool_calls → 执行工具 → 结果入 memory → 继续
           c. 如果返回纯文本 → 这就是最终答案 → 结束
        3. 返回结果

        Args:
            query: 用户问题
            verbose: 是否打印详情（通过 tracer）

        Returns:
            dict: 包含答案和元信息
        """
        # ── 空问题检查 ──────────────────────────
        if not query or not query.strip():
            return {
                "query": query,
                "answer": "请输入有效的问题。",
                "tools_used": [],
                "source": "empty",
            }

        # ── 重置反思计数器 ─────────────────────
        if self.reflect_engine:
            self.reflect_engine.reset()

        # ── 安全护栏：输入检查 + 设置系统提示词 ──
        if self.guardrail:
            self.guardrail.set_system_prompt(self._build_system_prompt())
            input_check = self.guardrail.check_input(query)
            if not input_check.passed:
                return {
                    "query": query,
                    "answer": f"输入被安全策略拦截：{input_check.reason}",
                    "tools_used": [],
                    "source": "blocked",
                }
            # 使用清洗后的文本
            query = input_check.sanitized_text

        # ── 初始化 ─────────────────────────────
        if self.tracer:
            self.tracer.start(query)

        if self.memory:
            self.memory.set_system_prompt(self._build_system_prompt())
            self.memory.add_message("user", query)

        # ── Plan & Execute ──────────────────────
        plan = self._plan(query)
        subtasks = plan["subtasks"]

        tools_used = []
        final_answer = ""

        if len(subtasks) <= 1:
            # 简单任务 → 直接 ReAct
            for step in range(1, self.max_steps + 1):
                llm_result = self._call_llm(step)
                if not llm_result["success"]:
                    final_answer = f"抱歉，AI 调用失败：{llm_result['error']}"
                    if self.tracer:
                        self.tracer.add_step("error", final_answer)
                    break

                tool_calls = llm_result.get("tool_calls")
                if tool_calls:
                    if self.tracer:
                        self.tracer.add_step("tool_calls", tool_calls,
                                             tokens=llm_result["usage"]["total_tokens"], latency=0)
                    if self.memory:
                        self.memory.add_tool_calls(tool_calls)
                    for tc in tool_calls:
                        self._execute_and_record(tc, tools_used)
                    if self.reflect_engine:
                        self._reflect_on_tools(query, tool_calls, tools_used)
                    continue

                final_answer = llm_result["content"] or ""
                # LLM 返回了空 content（可能只有 reasoning）→ 使用兜底
                if not final_answer.strip():
                    if tools_used:
                        final_answer = "操作已完成。"
                    else:
                        final_answer = "已处理。"
                break

            else:
                # 超过 max_steps → 强制兜底
                final_answer = self._force_answer()

        else:
            # 复杂任务 → 执行子任务后合并
            subtask_results = []
            for task in subtasks:
                for event in self._execute_task_stream(task, max_steps=25):
                    if event.type in ("done", "cancelled", "error"):
                        break
                if self.memory:
                    hist = self.memory.get_history()
                    for msg in reversed(hist):
                        if msg["role"] == "assistant" and msg.get("content") and not msg.get("_is_summary"):
                            subtask_results.append(msg["content"])
                            break

            final_answer = self._merge(subtask_results, query)

        # 自我评估：答案质量（仅单任务）
        if self.reflect_engine and final_answer and len(subtasks) <= 1:
            answer_reflection = self._reflect_on_answer(query, final_answer, tools_used)
            if answer_reflection:
                final_answer = answer_reflection

        # 安全护栏：输出脱敏
        if self.guardrail and final_answer:
            output_check = self.guardrail.check_output(final_answer)
            final_answer = output_check.sanitized_text

        if self.tracer:
            self.tracer.add_step("final_answer", final_answer[:200], tokens=0)

        if self.memory and final_answer:
            self.memory.add_message("assistant", final_answer)

        # ── 结束追踪 ───────────────────────────
        source = self._determine_source(tools_used)

        if self.tracer:
            self.tracer.end(final_answer, source)

        return {
            "query": query,
            "answer": final_answer,
            "tools_used": tools_used,
            "source": source,
        }

    # ── Plan & Execute ──────────────────────────

    def _plan(self, query: str) -> dict:
        """将用户需求拆分为子任务列表

        Returns:
            {"subtasks": [str, ...], "reasoning": str}
        """
        plan_prompt = (
            "你是任务规划师。将用户需求拆分为可独立执行的子任务。\n"
            "规则：\n"
            "- 每个子任务一行，不要序号，不要多余文字\n"
            "- **如果需求简单不需要拆分，只输出一行用户原问题**\n"
            "- **不要拆分只有一句话、一个问题的需求**，直接输出原问题\n"
            "- 只有用户明确列出多个不同操作（如「搜索X」「查看Y」「汇总」）时才拆分\n"
            "- 一个子任务不得超过 20 字\n"
            f"用户需求：{query}"
        )
        result = self.llm_provider.chat(
            messages=[
                {"role": "system", "content": "你是一个精准的任务规划师。只输出子任务列表。没有多个独立操作时不要拆分，直接输出用户原问题。"},
                {"role": "user", "content": plan_prompt},
            ],
            tools=None,
            temperature=0.1,
        )
        if not result.get("success") or not result.get("content"):
            return {"subtasks": [query]}

        text = result["content"].strip()
        lines = [line.strip().lstrip("0123456789.- ") for line in text.split("\n") if line.strip()]
        subtasks = [line for line in lines if len(line) > 3]

        if not subtasks:
            subtasks = [query]

        # 启发式：如果原问题只有一句话（没有明确分隔符）但被拆分了，回退
        MULTI_TASK_SEPS = ("\n", "1.", "2.", "①", "②", "首先", "然后", "和", "并", "同时")
        has_multi_task_signal = any(s in query for s in MULTI_TASK_SEPS)
        if len(subtasks) > 1 and not has_multi_task_signal:
            subtasks = [query]

        return {"subtasks": subtasks[:10]}  # 最多 10 个子任务

    def _merge(self, subtask_results: list[str], query: str) -> str:
        """合并多个子任务结果为最终回答"""
        context = "\n\n".join(
            f"[结果{i + 1}] {r[:500]}" for i, r in enumerate(subtask_results) if r
        )
        merge_prompt = (
            f"基于以上子任务结果，回答用户问题。\n\n"
            f"问题：{query}\n\n"
            f"子任务结果：\n{context}\n\n"
            "请综合所有结果给出完整、准确的回答。"
        )
        result = self.llm_provider.chat(
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                *([msg for msg in self.memory.get_messages() if msg["role"] != "user" or msg.get("content") != query] if self.memory else []),
                {"role": "user", "content": merge_prompt},
            ],
            tools=None,
            temperature=0.1,
        )
        return result.get("content", "") if result.get("success") else ""

    def _execute_task_stream(self, query: str, max_steps: int = 25):
        """委托给 react_loop.execute_task_stream"""
        yield from _exec_react(self, query, max_steps)

    def run_stream(self, query: str):
        """委托给 react_loop.run_stream"""
        yield from _run_react(self, query)

    def cancel(self):
        """取消当前生成（ESC 中断）"""
        self._cancel_event.set()

    def reset_cancel(self):
        """重置取消状态（新对话/新问题时调用）"""
        self._cancel_event.clear()

    def switch_model(self, model_name: str):
        """切换 LLM 模型"""
        if self.llm_provider and hasattr(self.llm_provider, 'switch_model'):
            self.llm_provider.switch_model(model_name)
        elif self.llm_provider:
            self.llm_provider.model = model_name

    def _call_llm(self, step: int) -> dict:
        """
        调用 LLM

        Args:
            step: 当前步骤号（用于追踪）

        Returns:
            LLMProvider.chat() 的返回值
        """
        messages = self.memory.get_messages() if self.memory else [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._last_query()},
        ]
        tools_schema = self.get_tools_schema()

        result = self.llm_provider.chat(
            messages=messages,
            tools=tools_schema if tools_schema else None,
            temperature=0.1,
        )

        return result

    def _execute_and_record(self, tool_call: dict, tools_used: list):
        """
        执行单个 tool_call 并记录到 memory 和 tracer

        Args:
            tool_call: LLM 返回的单个 tool_call
                {"id": "xxx", "function": "name", "arguments": "{...}"}
            tools_used: 已使用的工具名列表（累加）
        """
        call_id = tool_call["id"]
        func_name = tool_call["function"]
        args_str = tool_call["arguments"]

        # 解析参数
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {}

        # 安全护栏：工具调用检查
        if self.guardrail:
            tool_check = self.guardrail.check_tool(func_name, args)
            if not tool_check.passed:
                result_content = f"工具调用被安全策略拒绝：{tool_check.reason}"
                if self.tracer:
                    self.tracer.add_step("tool_result", result_content[:200])
                if self.memory:
                    self.memory.add_tool_result(call_id, func_name, result_content,
                                                  action=args.get("action", ""))
                return

            # 需要用户确认
            if tool_check.needs_confirm:
                try:
                    confirm = input(f"  ⚠️  工具 {func_name} 需要确认，是否执行？(y/n): ").strip().lower()
                    if confirm != "y":
                        result_content = "用户拒绝执行此操作"
                        if self.tracer:
                            self.tracer.add_step("tool_result", result_content[:200])
                        if self.memory:
                            self.memory.add_tool_result(call_id, func_name, result_content,
                                                          action=args.get("action", ""))
                        return
                except (EOFError, KeyboardInterrupt):
                    return

        # 执行工具
        if func_name not in self.tools:
            result_content = f"错误：工具 '{func_name}' 不存在。可用工具：{list(self.tools.keys())}"
        else:
            tool_result = self.execute_tool(func_name, **args)
            if tool_result.success:
                result_content = self._format_tool_result(func_name, tool_result)
                if func_name not in tools_used:
                    tools_used.append(func_name)
            else:
                result_content = f"工具执行失败：{tool_result.error}"

        # 安全护栏：工具结果脱敏（在发给 LLM 之前）
        if self.guardrail:
            output_check = self.guardrail.check_output(result_content, tool_name=func_name)
            result_content = output_check.sanitized_text

        # 记录到工具结果缓存（供反思使用）
        self._last_tool_results[func_name] = result_content

        # 记录到 tracer
        if self.tracer:
            self.tracer.add_step(
                "tool_result",
                result_content[:200],
            )

        # 记录到 memory
        if self.memory:
            # Phase 3：需要摘要的长内容 → 提炼后存 memory
            from utils.tool_summarizer import maybe_summarize
            memory_content = maybe_summarize(
                func_name, result_content, self.llm_provider,
                action=args.get("action", ""),
            ) or result_content
            self.memory.add_tool_result(call_id, func_name, memory_content,
                                          action=args.get("action", ""))

    def _format_tool_result(self, tool_name: str, result: ToolResult) -> str:
        """格式化工具结果为文本（供 LLM 阅读）"""
        if not result.data:
            return "工具未返回任何结果。"

        source = result.source or tool_name
        data = result.data

        # 知识库结果（list[dict] with "content"）
        if source == "knowledge_base" or (isinstance(data, list) and data and isinstance(data[0], dict) and "content" in data[0]):
            texts = []
            for i, item in enumerate(data[:5], 1):
                texts.append(f"[{i}] {item['content']}")
            return "知识库检索结果：\n" + "\n\n".join(texts)

        # 搜索结果（list[dict] with "title"）
        if source == "web_search" or (isinstance(data, list) and data and isinstance(data[0], dict) and "title" in data[0]):
            # 搜索被跳过（去重或超限）
            if isinstance(data, dict) and data.get("skipped"):
                return f"搜索已跳过：{data.get('reason', '重复查询')}。请基于已有信息回答。"
            texts = []
            for i, item in enumerate(data[:5], 1):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                url = item.get("url", "")
                texts.append(f"[{i}] {title}\n   {snippet}\n   来源: {url}")
            return "网络搜索结果：\n" + "\n\n".join(texts)

        # 文件/目录结果（dict）
        if isinstance(data, dict):
            if data.get("type") == "directory":
                entries = data.get("entries", [])
                return f"目录 [{data['filepath']}] 内容：\n" + "\n".join(entries)
            if data.get("type") == "file":
                return f"文件 [{data['filepath']}] 内容：\n{data['content']}"

        # 兜底
        return str(data)

    def _reflect_on_tools(self, query: str, tool_calls: list, tools_used: list):
        """
        自我评估：工具调用结果是否有用
        如果结果不好，自动重试（换关键词/策略）
        """
        re = self.reflect_engine

        for tc in tool_calls:
            func_name = tc["function"]
            args_str = tc["arguments"]

            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}

            # 获取最后一次该工具的结果
            if func_name not in self.tools:
                continue

            tool = self.tools[func_name]
            last_result = self._get_last_tool_result(func_name)

            if last_result is None or not re.should_reflect_tool(func_name, last_result):
                continue

            # 进行反思
            reflection = re.reflect_on_tool_result(
                query=query,
                tool_name=func_name,
                tool_args=args,
                tool_result=str(last_result),
            )

            if self.tracer:
                self.tracer.add_step(
                    "react_think",
                    f"反思 {func_name}: quality={reflection.quality}, action={reflection.action}",
                )

            # 根据反思结果决定行动
            if reflection.action == "retry" and re.can_retry(func_name):
                # 用建议的关键词重试
                re.record_retry(func_name)
                new_args = self._apply_reflection_suggestion(func_name, args, reflection.suggestion)

                if self.tracer:
                    self.tracer.add_step("react_think", f"重试 {func_name}: {new_args}")

                retry_result = self.execute_tool(func_name, **new_args)
                if retry_result.success and retry_result.data:
                    retry_content = self._format_tool_result(func_name, retry_result)
                    if self.guardrail:
                        retry_content = self.guardrail.check_output(retry_content, tool_name=func_name).sanitized_text
                    if self.memory:
                        # 添加重试结果到 memory
                        self.memory.add_message("user", f"[系统：根据反思重试 {func_name}，新结果如下]")
                        self.memory.add_message("assistant", retry_content)

    def _reflect_on_answer(self, query: str, answer: str, tools_used: list) -> str | None:
        """
        自我评估：最终答案质量
        如果质量不好，返回修正后的答案
        """
        re = self.reflect_engine

        # 收集工具结果摘要
        tool_summary = ""
        for tool_name in tools_used:
            result = self._get_last_tool_result(tool_name)
            if result:
                tool_summary += f"{tool_name}: {str(result)[:200]}\n"

        reflection = re.reflect_on_answer(
            query=query,
            answer=answer,
            tools_used=tools_used,
            tool_results_summary=tool_summary,
        )

        if self.tracer:
            self.tracer.add_step(
                "react_think",
                f"答案评估: quality={reflection.quality}, action={reflection.action}",
            )

        if reflection.quality == "failed" and reflection.action == "retry":
            # 重新生成答案（不调用工具）
            retry_result = self.llm_provider.chat(
                messages=[
                    *self._get_messages_for_retry(query, reflection.suggestion),
                ],
                tools=None,
                temperature=0.1,
            )
            if retry_result["success"]:
                return retry_result["content"]

        return None

    def _get_last_tool_result(self, tool_name: str) -> str | None:
        """获取指定工具的最后一次执行结果"""
        return self._last_tool_results.get(tool_name)

    def _apply_reflection_suggestion(self, tool_name: str, args: dict, suggestion: str) -> dict:
        """根据反思建议修改工具参数"""
        import copy
        new_args = copy.deepcopy(args)

        # 对搜索类工具，尝试用建议中的关键词替换 query
        if tool_name in ("search_knowledge_base", "search_web") and "query" in new_args:
            # 如果建议中提到了新关键词，用它替换
            if "换" in suggestion or "用" in suggestion or "改" in suggestion:
                # 简单提取：建议中引号内的内容
                import re
                quoted = re.findall(r'["""「]([^"""」]+)["""」]', suggestion)
                if quoted:
                    new_args["query"] = quoted[0]

        return new_args

    def _get_messages_for_retry(self, query: str, suggestion: str) -> list[dict]:
        """构建重新生成答案的消息列表"""
        messages = self.memory.get_messages() if self.memory else []
        # 追加反思建议
        messages = list(messages)
        messages.append({
            "role": "user",
            "content": f"[之前的回答不够好：{suggestion}。基于已有信息重新回答，简洁准确。]",
        })
        return messages

    def _force_answer(self) -> str:
        """
        当 ReAct 循环达到最大步数时，强制 LLM 给出最终答案
        """
        if self.memory:
            self.memory.add_message(
                "user",
                "根据已有信息直接回答，不要再调工具。简洁，不要废话。",
            )

        result = self.llm_provider.chat(
            messages=self.memory.get_messages() if self.memory else [],
            tools=None,  # 不传 tools → LLM 无法再调用工具
            temperature=0.1,
        )

        if result["success"]:
            answer = result["content"]
            if self.memory:
                self.memory.add_message("assistant", answer)
            if self.tracer:
                self.tracer.add_step("final_answer", answer[:200])
            return answer

        return "抱歉，处理超时，未能生成答案。"

    def _determine_source(self, tools_used: list) -> str:
        """根据使用的工具判断答案来源"""
        if not tools_used:
            return "llm_direct"
        if "search_knowledge_base" in tools_used and "search_web" in tools_used:
            return "knowledge_base + web_search"
        if "search_knowledge_base" in tools_used:
            return "knowledge_base"
        if "search_web" in tools_used:
            return "web_search"
        return "tools"

    def _last_query(self) -> str:
        """从 memory 中获取最后一条 user 消息"""
        if self.memory:
            history = self.memory.get_history()
            for msg in reversed(history):
                if msg["role"] == "user":
                    return msg["content"]
        return ""
