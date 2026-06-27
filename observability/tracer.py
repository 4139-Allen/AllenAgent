"""
Agent 决策追踪器
- 记录 ReAct 循环的每一步（Thought / Action / Observation）
- 控制台实时输出（verbose 模式）
- 结构化数据存储，供未来扩展（持久化、dashboard）
"""

import time
from typing import Any

from schemas.trace import TraceStep


class Tracer:
    """
    Agent 决策追踪器

    用法：
        tracer = Tracer(verbose=True)
        tracer.start("今天北京天气怎么样？")

        tracer.add_step("llm_call", "决定调用 search_web", tokens=120, latency=0.8)
        tracer.add_step("tool_calls", [{"function": "search_web", "args": {...}}])
        tracer.add_step("tool_result", "晴天，25°C...")
        tracer.add_step("final_answer", "今天北京天气晴朗...")

        summary = tracer.get_summary()
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.steps: list[TraceStep] = []
        self._query: str = ""
        self._start_time: float = 0.0
        self._total_tokens: int = 0

    def start(self, query: str):
        """开始一次新的追踪"""
        self.steps.clear()
        self._query = query
        self._start_time = time.time()
        self._total_tokens = 0

        if self.verbose:
            print(f"\n{'─' * 50}")
            print(f"[Trace] 🚀 开始: {query}")
            print(f"{'─' * 50}")

    def add_step(
        self,
        step_type: str,
        content: Any,
        tokens: int = 0,
        latency: float = 0.0,
        **metadata,
    ):
        """
        记录一步

        Args:
            step_type: 步骤类型
            content: 步骤内容
            tokens: 消耗的 token 数
            latency: 耗时（秒）
            **metadata: 附加元数据
        """
        step = TraceStep(
            step=len(self.steps) + 1,
            type=step_type,
            content=content,
            tokens=tokens,
            latency=latency,
            metadata=metadata,
        )
        self.steps.append(step)
        self._total_tokens += tokens

        if self.verbose:
            self._print_step(step)

    def end(self, answer: str, source: str = "agent"):
        """结束追踪，输出总结"""
        total_latency = time.time() - self._start_time

        if self.verbose:
            print(f"\n{'─' * 50}")
            print(f"[Trace] ✅ 完成 ({total_latency:.1f}s, {self._total_tokens} tokens)")
            print(f"[Trace] 来源: {source}")
            print(f"[Trace] 步骤数: {len(self.steps)}")
            print(f"{'─' * 50}")

    def get_summary(self) -> dict:
        """获取追踪摘要"""
        total_latency = time.time() - self._start_time
        return {
            "query": self._query,
            "steps": len(self.steps),
            "total_tokens": self._total_tokens,
            "total_latency": round(total_latency, 2),
            "step_details": [
                {
                    "step": s.step,
                    "type": s.type,
                    "tokens": s.tokens,
                    "latency": round(s.latency, 2),
                }
                for s in self.steps
            ],
        }

    def _print_step(self, step: TraceStep):
        """控制台输出单步"""
        icons = {
            "llm_call": "🧠",
            "tool_calls": "🔧",
            "tool_result": "📦",
            "final_answer": "💡",
            "error": "❌",
            "react_think": "💭",
        }
        icon = icons.get(step.type, "📌")

        # 截断过长的内容
        content_str = str(step.content)
        if len(content_str) > 200:
            content_str = content_str[:200] + "..."

        # 格式化输出
        token_info = f" ({step.tokens} tokens)" if step.tokens else ""
        latency_info = f" [{step.latency:.1f}s]" if step.latency else ""

        print(f"  {icon} Step {step.step} [{step.type}]{token_info}{latency_info}")

        # 对不同类型的步骤做不同的缩进处理
        if step.type == "tool_calls":
            for tc in (step.content if isinstance(step.content, list) else [step.content]):
                if isinstance(tc, dict):
                    fn = tc.get("function", tc)
                    name = fn.get("name", fn) if isinstance(fn, dict) else fn
                    args = fn.get("arguments", "") if isinstance(fn, dict) else ""
                    print(f"      → {name}({args})")
        elif step.type == "tool_result":
            print(f"      ← {content_str}")
        elif step.type == "react_think":
            print(f"      💭 {content_str}")
        else:
            if content_str:
                print(f"      {content_str}")
