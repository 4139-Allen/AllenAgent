"""
对话状态管理 — 从 ChatScreen 中分离出的状态和操作
职责：全量历史、加载/保存、压缩、命令处理
不涉及：布局、事件路由、UI 渲染细节
"""

import asyncio
import json

from textual.widgets import OptionList

from frontends.tui.widgets.chat_panel import ChatPanel
from frontends.tui.widgets.input_bar import InputBar
from frontends.shared.commands import get_help_text
from memory.conversation_store import ConversationStore


class ChatState:
    """ChatScreen 的对话状态和业务逻辑"""

    def __init__(self, screen):
        self.screen = screen
        self._full_history: list[dict] = []
        self._history_cache: list[dict] = []
        self.current_id: str | None = None
        self._generating = False

    # ── 属性快捷 ──────────────────────────

    @property
    def agent(self):
        return self.screen.agent

    @property
    def store(self) -> ConversationStore:
        return self.screen.store

    @property
    def model_manager(self):
        return self.screen.model_manager

    @property
    def panel(self) -> ChatPanel:
        return self.screen.query_one(ChatPanel)

    # ── 历史加载 ──────────────────────────

    def try_load_latest(self):
        """启动时加载最近对话"""
        saved = self.store.list_all()
        if not saved:
            return
        latest = saved[0]
        try:
            self._full_history = self.store.load_display(latest["id"])

            # 计算上下文预算
            fixed_overhead = 0
            ctx_window = 0
            try:
                if self.agent.allen_memory:
                    self.agent.allen_memory._load()
                sys_prompt = self.agent._build_system_prompt()
                from utils.token_counter import estimate_tokens
                fixed_overhead = estimate_tokens(sys_prompt)
                mc = self.model_manager.config.get_model_config(self.model_manager.current_model)
                ctx_window = mc.context_window if mc else 128000
            except Exception:
                pass

            loaded_mem = self.store.load(
                latest["id"],
                context_window=ctx_window,
                fixed_overhead_tokens=fixed_overhead,
            )
            # 过滤掉展示层专用的 thought 条目，不发给 LLM
            self.agent.memory._messages = [m for m in loaded_mem._messages if m.get("role") != "thought"]
            # 设置对话 ID，后续 auto_save 会覆盖同一文件而不是新建
            self.current_id = latest["id"]
            self.agent._current_conversation_id = latest["id"]
            repaired = self.agent.memory.repair_orphaned_tool_calls()

            self._render_full_history()
            user_msgs = [m for m in self._full_history if m.get("role") == "user"]
            title = latest.get("title", "")
            if repaired:
                self.panel.add_system_message("已修复损坏的对话记录")
        except Exception:
            pass

    def load_conversation(self, conv_id: str):
        """加载指定对话（展示层 + 推理层）"""
        self._full_history = self.store.load_display(conv_id)
        loaded_mem = self.store.load(conv_id)
        # 过滤掉展示层专用的 thought 条目，不发给 LLM
        self.agent.memory._messages = [m for m in loaded_mem._messages if m.get("role") != "thought"]
        self.current_id = conv_id
        self.agent._current_conversation_id = conv_id
        self._render_full_history()

    def _render_full_history(self, panel=None):
        """将 _full_history 渲染到 ChatPanel 中（仅显示 user / assistant / summary）"""
        if panel is None:
            panel = self.panel
        panel.clear_all()

        # 合并连续的 thought 条目后丢弃（只用于清理，不展示）
        merged = []
        buf_thought = None
        for msg in self._full_history:
            if msg.get("role") == "thought":
                segs = msg.get("segments", [])
                elapsed = msg.get("elapsed", 0)
                if not segs or elapsed == 0:
                    continue
                if buf_thought is None:
                    buf_thought = dict(msg)
                else:
                    buf_thought["segments"].extend(msg["segments"])
                    buf_thought["elapsed"] += msg["elapsed"]
            else:
                if buf_thought is not None:
                    merged.append(buf_thought)
                    buf_thought = None
                merged.append(msg)
        if buf_thought is not None:
            merged.append(buf_thought)

        # 只渲染 user / assistant(content) / system(summary)
        for msg in merged:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                panel.add_user_message(content)
            elif role == "assistant" and not msg.get("tool_calls") and content:
                widget = panel.start_assistant_message()
                widget.set_content(content)
            elif role == "system" and content and msg.get("_is_summary"):
                panel.add_system_message(content)
            # 其余角色（thought、assistant(tool_calls)、tool）均跳过
        panel.scroll_end(animate=False)

    # ── 保存 ──────────────────────────────

    def auto_save(self):
        # _full_history 是展示层全量历史，含完整内容（未截断）
        # 但它可能为空（新对话未发消息时），此时静默跳过而非降级到 agent.memory
        if self._full_history:
            self.current_id = self.store.save(
                full_history=self._full_history,
                conversation_id=self.current_id,
            )

    # ── 压缩 ──────────────────────────────

    async def run_compress(self):
        """手动压缩（异步，带进度动画）"""
        if not self.agent.memory or self.agent.memory.turn_count == 0:
            self.panel.add_system_message("暂无内容可压缩")
            return

        panel = self.panel
        panel.start_compressing()
        try:
            await asyncio.to_thread(self.agent._check_and_compress, force=True)
            # 同步摘要到 _full_history
            for msg in self.agent.memory.get_history():
                if msg.get("_is_summary"):
                    summary_content = msg.get("content", "")
                    already_exists = any(
                        m.get("_is_summary") and m.get("content") == summary_content
                        for m in self._full_history
                    )
                    if not already_exists:
                        self._full_history.append({
                            "role": "system",
                            "content": f"📋 历史摘要：{summary_content}",
                            "_is_summary": True,
                        })
                    break
            panel.finish_compressing()
            panel.add_system_message("✅ 已压缩，释放了上下文空间")
        except Exception as e:
            panel.finish_compressing()
            panel.add_system_message(f"❌ 压缩失败: {e}")

    def sync_summary_from_memory(self):
        """从 memory 同步摘要（自动压缩后调用）"""
        if not self.agent.memory:
            return
        for msg in self.agent.memory.get_history():
            if msg.get("_is_summary"):
                summary_content = msg.get("content", "")
                already_exists = any(
                    m.get("_is_summary") and m.get("content") == summary_content
                    for m in self._full_history
                )
                if not already_exists:
                    self._full_history.append({
                        "role": "system",
                        "content": f"📋 历史摘要：{summary_content}",
                        "_is_summary": True,
                    })
                break

    # ── 命令处理 ──────────────────────────

    def handle_command(self, cmd: str):
        panel = self.panel
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        match command:
            case "/help":
                self._show_command_list()

            case "/clear":
                panel.clear_all()
                self._full_history.clear()

            case "/compress":
                asyncio.create_task(self.run_compress())

            case "/new":
                self.auto_save()
                self.agent.reset_cancel()
                self.agent.memory.clear()
                self.agent.reset_auto_confirm()
                if "search_web" in self.agent.tools:
                    pass  # search_web.reset removed
                self.current_id = None
                self._full_history.clear()
                self.agent._current_conversation_id = None
                panel.clear_all()

            case "/history":
                saved = self.store.list_all()
                if not saved:
                    panel.add_system_message("暂无历史对话")
                else:
                    self._history_cache = saved[:20]
                    input_bar = self.screen.query_one(InputBar)
                    input_bar.show_history(self._history_cache)

            case "/load":
                if not arg:
                    panel.add_system_message("用法: /load <序号>")
                else:
                    arg = arg.strip()
                    conv_id = self._resolve_id(arg)
                    if conv_id is None:
                        panel.add_system_message(f"无效序号: {arg}")
                    else:
                        try:
                            self.auto_save()
                            self.load_conversation(conv_id)
                        except FileNotFoundError:
                            panel.add_system_message(f"对话 [{conv_id}] 不存在")
                        except Exception as e:
                            panel.add_system_message(f"加载失败: {e}")

            case "/save":
                self.auto_save()
                panel.add_system_message(f"已保存 [{self.current_id}]")

            case "/delete":
                if not arg:
                    panel.add_system_message("用法: /delete <序号>")
                else:
                    conv_id = self._resolve_id(arg.strip())
                    if conv_id is None:
                        panel.add_system_message(f"无效序号: {arg}")
                    elif self.store.delete(conv_id):
                        panel.add_system_message(f"已删除 [{conv_id}]")
                        if conv_id == self.current_id:
                            self.current_id = None
                            self.agent._current_conversation_id = None
                    else:
                        panel.add_system_message(f"对话 [{conv_id}] 不存在")

            case "/model":
                if arg:
                    try:
                        result = self.model_manager.switch(arg)
                        if "错误" in result:
                            panel.add_system_message(result)
                        else:
                            self.agent.set_llm_provider(self.model_manager.current_provider)
                            panel.add_system_message(result)
                    except Exception as e:
                        panel.add_system_message(f"切换失败: {e}")
                else:
                    panel.add_system_message(self.model_manager.list_models())

            case "/debug":
                panel.add_system_message("调试面板已移除")

            case "/status":
                status = (
                    f"模型: {self.screen.config.default_model}\n"
                    f"对话ID: {self.current_id or '未保存'}\n"
                    f"记忆: {self.agent.memory.turn_count} 轮"
                )
                panel.add_system_message(status)

            case "/theme":
                match self.screen.app.theme:
                    case "pure-black":
                        self.screen.app.theme = "pure-white"
                    case "pure-white":
                        self.screen.app.theme = "pure-black"
                    case _:
                        self.screen.app.theme = "pure-black"

            case "/exit":
                self.auto_save()
                self.screen.app.exit()

    def _show_command_list(self):
        self.panel.add_system_message(
            "命令:\n" + get_help_text("tui") + "\n  /debug     侧边栏"
        )

    def _resolve_id(self, arg: str) -> str | None:
        if arg.isdigit():
            idx = int(arg) - 1
            if 0 <= idx < len(self._history_cache):
                return self._history_cache[idx]["id"]
            return None
        return arg
