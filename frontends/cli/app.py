"""终端 REPL — 纯文本交互模式"""

from memory.conversation_store import ConversationStore
from frontends.shared.commands import get_cli_commands, get_help_text, find_command

def run_cli(agent, model_manager, allen_memory=None):
    """终端对话模式"""
    memory = agent.memory
    store = ConversationStore()
    current_id = None

    # 尝试加载上次对话
    saved = store.list_all()
    if saved:
        latest = saved[0]
        print(f"\n  发现上次对话: [{latest['id']}] {latest['title']} ({latest['turn_count']}轮)")
        try:
            choice = input("  是否加载？(y/n, 默认n): ").strip().lower()
            if choice == "y":
                loaded = store.load(latest["id"])
                memory.set_messages(loaded.get_history())
                current_id = latest["id"]
                print(f"  已加载 {memory.turn_count} 轮对话历史")
        except (EOFError, KeyboardInterrupt):
            pass

    print("\n" + "=" * 60)
    print("  对话模式（输入 / 查看命令）")
    print("=" * 60)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            if memory.turn_count > 0:
                cid = store.save(memory, current_id)
                print(f"\n  对话已保存 [{cid}]")
            print("\n再见！")
            break

        if not user_input:
            continue

        # ── 命令处理 ─────────────────────────
        if user_input.startswith("/"):
            result = _handle_command(user_input, agent, model_manager, memory, store, current_id)
            if result is None:
                continue
            if result == "__QUIT__":
                if memory.turn_count > 0:
                    cid = store.save(memory, current_id)
                    print(f"  对话已保存 [{cid}]")
                print("再见！")
                break
            if result == "__SAVED__":
                current_id = result
                continue
            print(result)
            continue

        # ── 普通对话 ─────────────────────────
        result = agent.run(user_input, verbose=True)
        answer = result["answer"].strip()
        print(f"\n助手: {answer}")

        if result["tools_used"]:
            print(f"  使用工具: {', '.join(result['tools_used'])}")

        # 每轮自动保存
        current_id = store.save(memory, current_id)


def _handle_command(cmd: str, agent, model_manager, memory, store, current_id) -> str | None:
    """处理 / 命令，返回响应文本或特殊标记"""
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    match command:
        case "/help":
            return "可用命令：\n" + get_help_text("cli")

        case "/new":
            if memory.turn_count > 0:
                store.save(memory, current_id)
            agent.memory.clear()
            agent.reset_auto_confirm()
            if "search_web" in agent.tools:
                pass  # reset removed
            return "新对话已开始"

        case "/load":
            if not arg:
                return "用法: /load <序号> 或 /load <对话ID>"
            saved = store.list_all()
            arg = arg.strip()
            conv_id = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(saved):
                    conv_id = saved[idx]["id"]
            else:
                conv_id = arg
            if conv_id is None:
                return f"无效的序号: {arg}"
            try:
                if memory.turn_count > 0:
                    store.save(memory, current_id)
                loaded = store.load(conv_id)
                memory.set_messages(loaded.get_history())
                return f"已加载对话 [{conv_id}]"
            except FileNotFoundError:
                return f"对话 [{conv_id}] 不存在"
            except Exception as e:
                return f"加载失败: {e}"

        case "/save":
            cid = store.save(memory, current_id)
            return f"已保存 [{cid}]"

        case "/delete":
            if not arg:
                return "用法: /delete <序号> 或 /delete <对话ID>"
            saved = store.list_all()
            arg = arg.strip()
            conv_id = None
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(saved):
                    conv_id = saved[idx]["id"]
            else:
                conv_id = arg
            if conv_id is None:
                return f"无效的序号: {arg}"
            if store.delete(conv_id):
                return f"已删除 [{conv_id}]"
            return f"对话 [{conv_id}] 不存在"

        case "/model":
            if arg:
                try:
                    result = model_manager.switch(arg)
                    if "❌" in result:
                        return result
                    agent.set_llm_provider(model_manager.current_provider)
                    return result
                except Exception as e:
                    return f"切换失败: {e}"
            return model_manager.list_models()

        case "/memory":
            if allen_memory:
                return allen_memory.get_all()
            return "记忆功能未启用"

        case "/remember":
            if not arg:
                return "用法: /remember <内容>"
            if allen_memory:
                allen_memory.add_fact(arg)
                return f"已记住: {arg}"
            return "记忆功能未启用"

        case "/exit" | "/quit":
            return "__QUIT__"

        case _:
            return f"未知命令: {command}，输入 /help 查看帮助"

    return None
