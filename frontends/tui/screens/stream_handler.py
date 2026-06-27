"""
流式事件消费 — 从 ChatScreen 中分离出的流处理逻辑

职责：消费 agent.run_stream() 的事件，更新 ChatPanel 和 ChatState
      渲染逻辑委托给 RendererRegistry，本模块只负责状态跟踪和收尾。

架构：LLM → Agent Runtime → Event Stream → RendererRegistry → TUI
"""

import asyncio
import json
import queue
import threading
import time

from frontends.tui.widgets.chat_panel import ChatPanel
from frontends.tui.widgets.confirm_widget import ConfirmWidget
from frontends.tui.widgets.artifact import ArtifactWidget
from frontends.tui.renderers.registry import RendererRegistry
from frontends.tui.renderers.confirm import ConfirmRenderer


def _summarize_diff(diff_text: str) -> str:
    """统计 diff 中所有 chunk 的 Added/removed 总行数"""
    added = removed = 0
    for line in diff_text.split("\n"):
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    parts = []
    if added:
        parts.append(f"Added {added} line{'s' if added > 1 else ''}")
    if removed:
        parts.append(f"removed {removed} line{'s' if removed > 1 else ''}")
    return ", ".join(parts)


class StreamHandler:
    """处理 Agent 流式事件，更新 UI 和对话状态"""

    def __init__(self, screen, state):
        self.screen = screen
        self.state = state
        self._tool_seq = 0
        self._confirm_future = None
        self._confirm_widget = None
        self._task = None  # asyncio.Task 引用，用于取消
        self._pending_file_changes: list[dict] = []

    def cancel(self):
        """ESC 中断当前生成"""
        self.agent.cancel()

    @property
    def panel(self) -> ChatPanel:
        return self.screen.query_one(ChatPanel)

    @property
    def agent(self):
        return self.screen.agent

    async def run(self, query: str):
        """运行 Agent 流并消费事件"""
        panel = self.panel

        # 重置取消状态（新一次生成）
        self.agent.reset_cancel()

        assistant_msg = None
        current_tool = None
        self._tool_seq = 0
        _current_tc_id = ""
        _final_content = ""
        _last_subtask_idx: int | None = None
        q: queue.Queue = queue.Queue()
        _SENTINEL = object()
        _cancelled = False
        _start_time = time.time()
        # 推理过程转录（保存用）
        _transcript_segments: list[tuple[str, str | None]] = []
        # 是否有推理/工具内容
        _has_thought = False
        self._pending_file_changes.clear()

        # 立即创建推理块，不等 LLM 首 token
        panel.start_thought_block()
        _has_thought = True

        def _producer():
            try:
                for event in self.agent.run_stream(query):
                    q.put(event)
            except Exception as e:
                q.put(e)
            finally:
                q.put(_SENTINEL)

        threading.Thread(target=_producer, daemon=True).start()

        _last_event_time = time.time()
        _timeout_shown = False
        _HEARTBEAT_TIMEOUT = 30  # 30 秒无事件判定为超时

        try:
            while True:
                # 使用 timeout 以便 ESC 取消时能及时响应
                try:
                    event = await asyncio.to_thread(lambda: q.get(timeout=0.3))
                    _last_event_time = time.time()
                    _timeout_shown = False
                except queue.Empty:
                    if self.agent._cancel_event.is_set():
                        _cancelled = True
                        break
                    # 检测是否超时（LLM 无响应）
                    if not _timeout_shown and time.time() - _last_event_time > _HEARTBEAT_TIMEOUT:
                        panel.append_thought_thinking("\n⚠️ LLM 长时间无响应，可能已中断（按 Esc 取消）")
                        _timeout_shown = True
                    continue

                if event is _SENTINEL:
                    break
                if isinstance(event, Exception):
                    panel.add_system_message(f"错误: {event}")
                    break

                # token 事件：确保渲染前 AssistantMessage 已创建（防首 token 丢失）
                if event.type == "token" and assistant_msg is None:
                    assistant_msg = panel.start_assistant_message()

                # 委托 RendererRegistry 处理渲染
                RendererRegistry.render(panel, event)

                # 以下为状态跟踪逻辑（不涉及渲染）
                match event.type:
                    case "thinking_token":
                        _has_thought = True
                        if _transcript_segments and _transcript_segments[-1][1] is None:
                            prev = _transcript_segments[-1][0]
                            _transcript_segments[-1] = (prev + event.content, None)
                        else:
                            _transcript_segments.append((event.content, None))

                    case "tool_call":
                        _has_thought = True
                        if event.count > 1:
                            _seg_text = f"● {event.name} ({event.count} 项)"
                            _transcript_segments.append((_seg_text, "bold #4caf50"))
                        elif event.count == 0:
                            pass  # 批量内部调用，不写显示
                        else:
                            _seg_text = f"● {event.name} {json.dumps(event.args, ensure_ascii=False)}"
                            _transcript_segments.append((_seg_text, "bold #4caf50"))
                        # 持久化到 _full_history（使用 LLM 返回的原始 id）
                        _current_tc_id = event.tool_call_id or f"{self._tool_seq}"
                        self._tool_seq += 1
                        self.state._full_history.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": _current_tc_id,
                                "type": "function",
                                "function": {"name": event.name, "arguments": json.dumps(event.args, ensure_ascii=False)},
                            }],
                            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                        })

                    case "tool_result":
                        _has_thought = True
                        result_preview = str(event.result)[:200] if event.result else "无返回"
                        _transcript_segments.append((f"● {result_preview}", "bold #4a9eff"))
                        self.state._full_history.append({
                            "role": "tool",
                            "tool_call_id": _current_tc_id,
                            "content": str(event.result) if event.result else "",
                            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                        })

                    case "file_change":
                        # 缓冲文件变更事件，等 done 时渲染为永久 artifact
                        self._pending_file_changes.append({
                            "file_action": event.file_action,
                            "file_path": event.file_path,
                            "content": event.content,
                        })

                    case "token":
                        # assistant_msg 已在渲染前创建，此处只累加内容
                        _final_content += event.content

                    case "done":
                        total_elapsed = int(time.time() - _start_time)
                        if _has_thought:
                            panel.finish_thought_block()
                            thought_elapsed = (
                                panel._last_thought._final_elapsed
                                if panel._last_thought else total_elapsed
                            )
                            self.state._full_history.append({
                                "role": "thought",
                                "segments": _transcript_segments,
                                "elapsed": thought_elapsed,
                                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                            })

                        # ── 永久展示文件变更 artifact（在 assistant 回复之前） ──
                        for fc in self._pending_file_changes:
                            fa, fp, ct = fc["file_action"], fc["file_path"], fc["content"]
                            if fa == "read":
                                continue
                            if fa in ("update", "created") and ct:
                                label = "Update" if fa == "update" else "Create"
                                title = f"[bold green]●[/bold green] {label} {fp}"
                                stat = _summarize_diff(ct)
                                widget = ArtifactWidget(content=ct, language="diff", title=title, stat_line=stat)
                            else:
                                # delete / read 等不需要永久 artifact
                                continue
                            # 插到 assistant 消息之前（如果已存在）
                            if assistant_msg is not None:
                                panel.mount(widget, before=assistant_msg)
                            else:
                                panel.mount(widget)
                        panel._auto_scroll()
                        self._pending_file_changes.clear()

                        if not assistant_msg and _has_thought:
                            thought_text = " ".join(
                                c for c, s in _transcript_segments
                                if s is None or "dim" not in str(s)
                            )[:500] or "已处理。"
                            assistant_msg = panel.start_assistant_message()
                            panel.append_token(thought_text)
                            _final_content += thought_text
                        if assistant_msg:
                            # 直接 finalize 确保耗时始终写入
                            assistant_msg.finalize(elapsed=total_elapsed)
                            panel._current_assistant = None
                            if _final_content.strip():
                                self.state._full_history.append({
                                    "role": "assistant",
                                    "content": _final_content,
                                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                                })
                            assistant_msg = None

                    case "confirm":
                        # RendererRegistry.render(panel, event) 已在第 110 行统一执行
                        # 此处只做异步等待和拆卸，避免重复挂载
                        confirm_widget = panel.query_one(ConfirmWidget)
                        accepted, auto_all = await self._wait_for_confirm(confirm_widget)
                        event.confirm_callback(accepted, auto_all)
                        ConfirmRenderer.cleanup(panel)

                    case "cancelled":
                        _cancelled = True
                        break

        except asyncio.CancelledError:
            _cancelled = True
        except Exception as e:
            panel.add_system_message(f"错误: {e}")
        finally:
            self.state._generating = False
            if assistant_msg:
                panel.finalize_assistant_message()
            self.state.sync_summary_from_memory()
            if _has_thought:
                panel.finish_thought_block()
            self.state.auto_save()

    async def _wait_for_confirm(self, widget) -> tuple:
        self._confirm_future = asyncio.get_running_loop().create_future()
        self._confirm_widget = widget
        return await self._confirm_future

    def resolve_confirm(self, event):
        """由 ChatScreen.on_confirm_widget_confirmed 调用"""
        if self._confirm_future and not self._confirm_future.done():
            self._confirm_future.set_result((event.accepted, event.auto_all))
        if self._confirm_widget:
            self._confirm_widget.remove()
            self._confirm_widget = None
