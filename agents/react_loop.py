"""
Streaming ReAct 循环 — 从 AllenAgent 独立出来的核心生成器

职责：
  - execute_task_stream(): 单个任务的 ReAct 循环（Think → Act → Observe → ...）
  - run_stream():          流式运行 Agent（含 Plan & Execute 架构）

调用方通过 agent 参数访问 AllenAgent 的属性和方法，避免循环导入。
"""

from __future__ import annotations

import difflib
import json
import logging
import time as _time
from pathlib import Path
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from agents.allen_agent import AllenAgent

from schemas.stream import StreamEvent


def _normalize_dedup_args(func_name: str, args: dict) -> dict:
    """归一化工具参数，提升去重命中率

    覆盖场景：
      - 文件路径：'./dir/file' vs 'dir/file' vs '/abs/path/dir/file' → 统一绝对路径
      - shell 命令：首尾空格、多余空白 → 归一化
      - 搜索查询：首尾空格 → 去除
      - 所有工具的 path/filepath 参数同上
    """
    if not args:
        return args

    import os
    normalized = dict(args)

    # ── 路径参数归一化（file_io、code_search 等带路径的工具） ──
    PATH_KEYS = {"filepath", "filepaths", "path", "source", "dest", "destination"}
    for key in PATH_KEYS:
        if key not in normalized:
            continue
        val = normalized[key]
        if isinstance(val, str):
            fp = val.strip("\"'")
            fp = os.path.normpath(fp)
            fp = os.path.abspath(fp)
            normalized[key] = fp
        elif isinstance(val, list):
            normalized[key] = [
                os.path.abspath(os.path.normpath(p.strip("\"'")))
                if isinstance(p, str) else p
                for p in val
            ]

    # ── 文本参数归一化（搜索、grep 等） ──
    for key in ("query", "pattern", "include", "exclude"):
        if key in normalized and isinstance(normalized[key], str):
            normalized[key] = normalized[key].strip()

    # ── shell 命令归一化 ──
    if func_name == "shell" and "command" in normalized and isinstance(normalized["command"], str):
        normalized["command"] = normalized["command"].strip()
        import re
        normalized["command"] = re.sub(r"\s+", " ", normalized["command"])

    return normalized



def execute_task_stream(
    agent: AllenAgent, query: str, max_steps: int = 25
) -> Generator[StreamEvent, None, None]:
    """执行单个任务的 ReAct 循环

    Args:
        agent: AllenAgent 实例（通过 agent.xxx 访问属性/方法）
        query: 用户输入
        max_steps: 最大步骤数

    Yields:
        StreamEvent: 包含 thinking/tool_call/tool_result/token/done
    """
    _tools_used: list[str] = []
    _tool_retry_count: dict[str, int] = {}
    _recent_tool_calls: dict[str, bool] = {}  # 去重：tool_name:args → 是否已执行
    _MAX_TOOL_RETRIES = 3
    _api_error_count: int = 0       # 本轮连续 API 错误次数
    _MAX_API_ERRORS = 2             # 超过则放弃
    turn_thinking_started = False
    turn_thinking_content = ""

    for step in range(1, max_steps + 1):
        if agent._cancel_event.is_set():
            yield StreamEvent(type="cancelled")
            if turn_thinking_started:
                yield StreamEvent(type="thinking_end")
            yield StreamEvent(type="done")
            return
        agent._check_and_compress()

        if agent.memory:
            agent.memory.repair_orphaned_tool_calls()
        messages = agent.memory.get_messages() if agent.memory else [
            {"role": "system", "content": agent._build_system_prompt()},
            {"role": "user", "content": query},
        ]
        tools_schema = agent.get_tools_schema()

        content_buffer = ""
        assembled_tool_calls = []
        usage_info = {}
        thinking_buffer = ""
        in_think_tag = False
        THINK_MIN_LEN = 20

        for chunk in agent.llm_provider.chat_stream(
            messages=messages,
            tools=tools_schema if tools_schema else None,
            temperature=0.1,
        ):
            if chunk["type"] == "thinking_token":
                thinking_buffer += chunk["content"]
                turn_thinking_content += chunk["content"]
                if len(thinking_buffer) >= THINK_MIN_LEN:
                    if not turn_thinking_started:
                        turn_thinking_started = True
                        yield StreamEvent(type="thinking_start")
                    yield StreamEvent(type="thinking_token", content=thinking_buffer)
                    thinking_buffer = ""

            elif chunk["type"] == "token":
                token = chunk["content"]
                content_buffer += token

                if thinking_buffer.strip():
                    if len(thinking_buffer.strip()) >= THINK_MIN_LEN:
                        if not turn_thinking_started:
                            turn_thinking_started = True
                            yield StreamEvent(type="thinking_start")
                        yield StreamEvent(type="thinking_token", content=thinking_buffer)
                    thinking_buffer = ""

                while token:
                    if not in_think_tag:
                        think_start = token.find("<think>")
                        if think_start != -1:
                            before = token[:think_start]
                            if before:
                                yield StreamEvent(type="token", content=before)
                            in_think_tag = True
                            token = token[think_start + 6:]
                        else:
                            yield StreamEvent(type="token", content=token)
                            token = ""
                    else:
                        think_end = token.find("</think>")
                        if think_end != -1:
                            think_content_part = token[:think_end]
                            if think_content_part:
                                thinking_buffer += think_content_part
                                turn_thinking_content += think_content_part
                                if len(thinking_buffer) >= THINK_MIN_LEN:
                                    if not turn_thinking_started:
                                        turn_thinking_started = True
                                        yield StreamEvent(type="thinking_start")
                                    yield StreamEvent(type="thinking_token", content=thinking_buffer)
                                    thinking_buffer = ""
                            in_think_tag = False
                            token = token[think_end + 7:]
                        else:
                            thinking_buffer += token
                            turn_thinking_content += token
                            if len(thinking_buffer) >= THINK_MIN_LEN:
                                if not turn_thinking_started:
                                    turn_thinking_started = True
                                    yield StreamEvent(type="thinking_start")
                                yield StreamEvent(type="thinking_token", content=thinking_buffer)
                                thinking_buffer = ""
                            token = ""

            elif chunk["type"] == "tool_calls":
                assembled_tool_calls = chunk["tool_calls"]

            elif chunk["type"] == "usage":
                usage_info = chunk["usage"]
                agent._stream_usage = usage_info

            elif chunk["type"] == "error":
                logging.error(f"API error: {chunk['error']}")
                for i, m in enumerate(messages):
                    role = m.get("role", "?")
                    tc = m.get("tool_calls")
                    tcid = m.get("tool_call_id")
                    if tc:
                        logging.error(f"  [{i}] {role} tool_calls={[t['id'] for t in tc]}")
                    elif tcid:
                        logging.error(f"  [{i}] {role} tool_call_id={tcid}")
                    else:
                        logging.error(f"  [{i}] {role}: {str(m.get('content', ''))[:80]}")

                _api_error_count += 1
                error_text = chunk["error"]

                if turn_thinking_started:
                    yield StreamEvent(type="thinking_end")
                    turn_thinking_started = False

                if _api_error_count >= _MAX_API_ERRORS:
                    # 连续失败太多次，放弃
                    yield StreamEvent(
                        type="tool_result",
                        result=f"AI 连续 {_MAX_API_ERRORS} 次调用失败：{error_text}。请直接回复用户说明情况。",
                        duration=0, tool_status="error",
                    )
                    if agent.memory:
                        agent.memory.add_message(
                            "assistant",
                            f"[系统] AI 连续 {_MAX_API_ERRORS} 次调用失败：{error_text}，任务终止。",
                        )
                    yield StreamEvent(type="done")
                    return

                # 把错误塞回 memory，让 LLM 自己决定怎么处理
                err_content = (
                    f"[系统] AI 调用异常（第 {_api_error_count} 次）：{error_text}\n"
                    "将继续重试。请确保之前获取的工具结果完整，如有必要可调整策略。"
                )
                if agent.memory:
                    agent.memory.add_message("user", err_content)
                yield StreamEvent(
                    type="tool_result",
                    result=err_content,
                    duration=0, tool_status="error",
                )
                break  # 退出流式循环，走下面的 _api_error_occurred 逻辑

            if agent._cancel_event.is_set():
                yield StreamEvent(type="cancelled")
                if turn_thinking_started:
                    yield StreamEvent(type="thinking_end")
                yield StreamEvent(type="done")
                return

        # ── API 错误重试 ──
        if _api_error_count > 0:
            continue  # 让 LLM 在下一轮看到错误信息后自己决策

        # ── 处理 tool_calls ──
        if assembled_tool_calls:
            if agent.tracer:
                agent.tracer.add_step("tool_calls", assembled_tool_calls,
                                      tokens=usage_info.get("total_tokens", 0), latency=0)
            if agent.memory:
                agent.memory.add_tool_calls(assembled_tool_calls)

            any_rejected = False
            batch_approved = None
            batch_results = []

            # 按工具名分组（执行层合并确认，事件层逐条发出确保数据完整）
            _groups = []
            for _tc in assembled_tool_calls:
                _fn = _tc["function"]
                if _groups and _groups[-1][0] == _fn:
                    _groups[-1][1].append(_tc)
                else:
                    _groups.append((_fn, [_tc]))

            for func_name, calls in _groups:
                batch_size = len(calls)

                for tc_idx, tc in enumerate(calls):
                    call_id = tc["id"]
                    func_name = tc["function"]
                    args_str = tc["arguments"]

                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except json.JSONDecodeError:
                        args = {}

                    # 发出 tool_call 事件（携带原始 LLM id）
                    yield StreamEvent(type="tool_call", name=func_name, args=args, step=step,
                                     count=(batch_size if tc_idx == 0 else 0),
                                     tool_call_id=call_id)

                    # 重试次数检查
                    if _tool_retry_count.get(func_name, 0) >= _MAX_TOOL_RETRIES:
                        result_content = f"工具 '{func_name}' 已连续失败 {_MAX_TOOL_RETRIES} 次，跳过执行，请直接给出回答"
                        yield StreamEvent(type="tool_result", result=result_content, duration=0, tool_status="error")
                        if agent.tracer:
                            agent.tracer.add_step("tool_result", result_content[:200])
                        if agent.memory:
                            agent.memory.add_tool_result(call_id, func_name, result_content,
                                                          action=args.get("action", ""))
                        continue

                    # 安全检查
                    if agent.guardrail:
                        tool_check = agent.guardrail.check_tool(func_name, args)
                        if not tool_check.passed:
                            result_content = f"工具调被安全策略拒绝：{tool_check.reason}"
                            yield StreamEvent(type="tool_result", result=result_content, duration=0, tool_status="rejected")
                            if agent.tracer:
                                agent.tracer.add_step("tool_result", result_content[:200])
                            if agent.memory:
                                agent.memory.add_tool_result(call_id, func_name, result_content,
                                                              action=args.get("action", ""))
                            continue

                        if tool_check.needs_confirm:
                            if agent._auto_confirm:
                                pass
                            elif batch_approved is not None:
                                if not batch_approved:
                                    if agent.memory:
                                        agent.memory.add_tool_result(call_id, func_name, "用户拒绝执行此操作",
                                                                      action=args.get("action", ""))
                                    yield StreamEvent(type="tool_result", result="用户拒绝执行此操作", duration=0, tool_status="rejected")
                                    continue
                            else:
                                import threading
                                confirmed = threading.Event()
                                user_choice = [True, False]

                                def _on_confirm(accepted, auto_all=False):
                                    user_choice[0] = accepted
                                    user_choice[1] = auto_all
                                    confirmed.set()

                                confirm_count = sum(
                                    1 for t2 in assembled_tool_calls[assembled_tool_calls.index(tc):]
                                    if agent.guardrail.check_tool(
                                        t2["function"],
                                        json.loads(t2["arguments"]) if isinstance(t2["arguments"], str) else t2["arguments"]
                                    ).needs_confirm
                                )
                                question = tool_check.reason
                                if confirm_count > 1:
                                    question = f"批量操作（共 {confirm_count} 项）：{tool_check.reason}"

                                # ── 预计算文件变更的 diff 预览（确认前展示给用户） ──
                                diff_preview = ""
                                if func_name == "file_io" and args.get("action") == "write":
                                    _fp = args.get("filepath", "")
                                    _new_content = args.get("content", "")
                                    if _fp:
                                        _fp_path = Path(_fp)
                                        if _fp_path.exists():
                                            try:
                                                _old_lines = _fp_path.read_text(encoding="utf-8").splitlines()
                                            except Exception:
                                                _old_lines = []
                                        else:
                                            _old_lines = []
                                        _new_lines = _new_content.splitlines()
                                        _raw_diff = list(difflib.unified_diff(
                                            _old_lines, _new_lines, lineterm="",
                                        ))
                                        # 取前 30 行（避免过长），跳过 unified_diff 的文件头 ---/+++ 行
                                        _body_lines = [l for l in _raw_diff[2:] if not l.startswith("@@ ")]
                                        _body = "\n".join(_body_lines[:30])
                                        if _body.strip():
                                            diff_preview = _body
                                elif func_name == "file_io" and args.get("action") == "delete":
                                    _fp = args.get("filepath", "")
                                    if _fp:
                                        _fp_path = Path(_fp)
                                        if _fp_path.exists():
                                            diff_preview = f"⚠ 将删除文件：{_fp}"
                                        else:
                                            diff_preview = f"⚠ 文件不存在：{_fp}"

                                yield StreamEvent(
                                    type="confirm",
                                    confirm_question=question,
                                    content=diff_preview,
                                    name=func_name,
                                    args=args,
                                    confirm_callback=_on_confirm,
                                )
                                while not confirmed.is_set():
                                    if agent._cancel_event.is_set():
                                        user_choice[0] = False
                                        confirmed.set()
                                        yield StreamEvent(type="cancelled")
                                        if turn_thinking_started:
                                            yield StreamEvent(type="thinking_end")
                                        yield StreamEvent(type="done")
                                        return
                                    confirmed.wait(timeout=0.3)
                                batch_approved = user_choice[0]
                                auto_all = user_choice[1]
                                if auto_all:
                                    agent._auto_confirm = True
                                if not batch_approved:
                                    reject_summary = f"用户拒绝执行 {func_name}"
                                    if args:
                                        for k in ("command", "filepath", "query", "url", "action"):
                                            if k in args:
                                                val = str(args[k])
                                                if len(val) > 60:
                                                    val = val[:57] + "..."
                                                reject_summary += f" {k}={val}"
                                                break
                                    reject_summary += "。请勿重试该工具，直接回复用户。"
                                    if agent.memory:
                                        agent.memory.undo_last_tool_calls()
                                        agent.memory.add_message("assistant", f"[系统] {reject_summary}")
                                    yield StreamEvent(type="tool_result", result=reject_summary, duration=0, tool_status="rejected")
                                    any_rejected = True
                                    break

                    if any_rejected:
                        break

                    if agent._cancel_event.is_set():
                        yield StreamEvent(type="cancelled")
                        if turn_thinking_started:
                            yield StreamEvent(type="thinking_end")
                        yield StreamEvent(type="done")
                        return

                    # 参数校验
                    if func_name in agent.tools:
                        is_valid, err_msg = agent.tools[func_name].validate_params(args)
                        if not is_valid:
                            result_content = f"参数校验失败：{err_msg}，请修正参数后重试"
                            _tool_retry_count[func_name] = _tool_retry_count.get(func_name, 0) + 1
                            yield StreamEvent(type="tool_result", result=result_content, duration=0, tool_status="error")
                            if agent.tracer:
                                agent.tracer.add_step("tool_result", result_content[:200])
                            if agent.memory:
                                agent.memory.add_tool_result(call_id, func_name, result_content,
                                                              action=args.get("action", ""))
                            continue

                    # 去重
                    _dedup_args = _normalize_dedup_args(func_name, args)
                    _cache_key = f"{func_name}:{json.dumps(_dedup_args, sort_keys=True, ensure_ascii=False)}"
                    # read 操作跳过去重，允许二次确认
                    if func_name == "file_io" and args.get("action") in ("read", "list"):
                        pass
                    elif _cache_key in _recent_tool_calls:
                        result_content = f"工具 '{func_name}'（相同参数）已在之前成功执行，结果仍有效，无需重复执行，直接使用已有结果即可。"
                        yield StreamEvent(type="tool_result", result=result_content, duration=0, tool_status="skipped")
                        if agent.tracer:
                            agent.tracer.add_step("tool_result", result_content[:200])
                        if agent.memory:
                            agent.memory.add_tool_result(call_id, func_name, result_content,
                                                          action=args.get("action", ""))
                        continue
                    _recent_tool_calls[_cache_key] = True

                    # 执行工具
                    t0 = _time.time()
                    _tool_success = False
                    if func_name not in agent.tools:
                        result_content = f"错误：工具 '{func_name}' 不存在。可用工具：{list(agent.tools.keys())}"
                        duration = 0
                    else:
                        # ── 缓存文件修改前的旧内容（用于后续 diff 预览） ──
                        _pre_old_lines: list[str] = []
                        if func_name == "file_io" and args.get("action") == "write":
                            _pre_fp = args.get("filepath", "")
                            if _pre_fp:
                                _pre_path = Path(_pre_fp)
                                if _pre_path.exists():
                                    try:
                                        _pre_old_lines = _pre_path.read_text(encoding="utf-8").splitlines()
                                    except Exception:
                                        pass
                        tool_result = agent.execute_tool(func_name, **args)
                        duration = int((_time.time() - t0) * 1000)
                        if tool_result.success:
                            result_content = agent._format_tool_result(func_name, tool_result)
                            _tool_success = True
                            if func_name not in _tools_used:
                                _tools_used.append(func_name)
                        else:
                            result_content = f"工具执行失败：{tool_result.error}"

                    if agent.guardrail:
                        output_check = agent.guardrail.check_output(result_content, tool_name=func_name)
                        result_content = output_check.sanitized_text

                    if not _tool_success:
                        _status = "error"
                    elif "已跳过" in result_content or "skipped" in result_content.lower():
                        _status = "skipped"
                    else:
                        _status = "success"

                    if _status == "success":
                        _tool_retry_count.pop(func_name, None)
                    elif _status == "error":
                        _tool_retry_count[func_name] = _tool_retry_count.get(func_name, 0) + 1

                    agent._last_tool_results[func_name] = result_content
                    yield StreamEvent(type="tool_result", result=result_content, duration=duration, tool_status=_status)

                    # 文件操作后续事件
                    if _tool_success and func_name == "file_io":
                        _fa = args.get("action", "")
                        _fps = args.get("filepaths", None) or ([args["filepath"]] if args.get("filepath") else [])
                        if _fa in ("write", "delete") and _fps:
                            for _single_fp in _fps:
                                _fc = args.get("content", "")
                                if _fa == "write" and _fc:
                                    _file_existed = bool(_pre_old_lines)
                                    _file_action = "update" if _file_existed else "created"
                                    # 展示完整 diff（不截断）
                                    _diff = list(difflib.unified_diff(
                                        _pre_old_lines, _fc.splitlines(), lineterm="",
                                    ))
                                    _diff_body = [l for l in _diff[2:] if not l.startswith("@@ ")]
                                    _fc_preview = "\n".join(_diff_body)
                                else:
                                    _fc_preview = ""
                                    _file_action = "deleted"
                                yield StreamEvent(
                                    type="file_change",
                                    file_action=_file_action,
                                    file_path=_single_fp,
                                    content=_fc_preview,
                                )
                        elif _fa == "read":
                            _read_fp = args.get("filepath", "")
                            if _read_fp:
                                yield StreamEvent(
                                    type="file_change",
                                    file_action="read",
                                    file_path=_read_fp,
                                )

                    if agent.tracer:
                        agent.tracer.add_step("tool_result", result_content[:200])
                    if agent.memory:
                        from utils.tool_summarizer import maybe_summarize
                        memory_content = maybe_summarize(
                            func_name, result_content, agent.llm_provider,
                            action=args.get("action", ""),
                        ) or result_content
                        agent.memory.add_tool_result(call_id, func_name, memory_content,
                                                      action=args.get("action", ""))
                    batch_results.append({"tool": func_name, "success": _tool_success, "duration": duration, "args": args})

                if any_rejected:
                    break

            # 反思
            if agent.reflect_engine:
                re = agent.reflect_engine
                for tc in assembled_tool_calls:
                    func_name = tc["function"]
                    args_str = tc["arguments"]
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    except json.JSONDecodeError:
                        args = {}
                    if func_name not in agent.tools:
                        continue
                    last_result = agent._get_last_tool_result(func_name)
                    if last_result is None or not re.should_reflect_tool(func_name, last_result):
                        continue
                    reflection = re.reflect_on_tool_result(
                        query=query, tool_name=func_name, tool_args=args, tool_result=str(last_result)
                    )
                    yield StreamEvent(
                        type="reflection",
                        ref_type=f"工具 {func_name}",
                        summary=f"quality={reflection.quality}, action={reflection.action}",
                    )
                    if reflection.action == "retry" and re.can_retry(func_name):
                        re.record_retry(func_name)
                        new_args = agent._apply_reflection_suggestion(func_name, args, reflection.suggestion)
                        retry_result = agent.execute_tool(func_name, **new_args)
                        if retry_result.success and retry_result.data:
                            retry_content = agent._format_tool_result(func_name, retry_result)
                            if agent.guardrail:
                                retry_content = agent.guardrail.check_output(
                                    retry_content, tool_name=func_name
                                ).sanitized_text
                            if agent.memory:
                                agent.memory.add_message(
                                    "user", f"[系统：根据反思重试 {func_name}，新结果如下]"
                                )
                                agent.memory.add_message("assistant", retry_content)

            if any_rejected:
                if turn_thinking_started:
                    yield StreamEvent(type="thinking_end")
                yield StreamEvent(type="done")
                return

            continue

        # ── 最终答案 ──
        final_answer = content_buffer

        # 模型未输出任何内容时的兜底处理
        if not final_answer.strip():
            if turn_thinking_started:
                yield StreamEvent(type="thinking_end")
                turn_thinking_started = False

            if _tools_used:
                summary_items = []
                for tname in _tools_used:
                    tres = agent._last_tool_results.get(tname, "")
                    if isinstance(tres, str):
                        short = tres[:100].replace("\n", " ").replace("  ", " ").strip()
                        if short.startswith("{") and "deleted" in short:
                            try:
                                parsed = json.loads(short.replace("'", '"'))
                                count = parsed.get("count", 0)
                                deleted = parsed.get("deleted", [])
                                names = [d.split("/")[-1] if "/" in d else d for d in deleted[:3]]
                                n_str = ", ".join(names)
                                if len(deleted) > 3:
                                    n_str += f" 等 {len(deleted)} 个"
                                summary_items.append(f"已删除 {count} 个文件（{n_str}）")
                                continue
                            except Exception:
                                pass
                        summary_items.append(short)
                if summary_items:
                    summary_text = "；".join(summary_items)
                    if len(summary_text) > 200:
                        summary_text = summary_text[:197] + "..."
                    final_answer = summary_text
                else:
                    final_answer = "操作已完成。"
                yield StreamEvent(type="token", content=final_answer)
            else:
                final_answer = turn_thinking_content.strip() or "已处理。"
                yield StreamEvent(type="token", content=final_answer)

        else:
            if turn_thinking_started:
                yield StreamEvent(type="thinking_end")
                turn_thinking_started = False

        if agent.guardrail and final_answer:
            try:
                output_check = agent.guardrail.check_output(final_answer)
                final_answer = output_check.sanitized_text
            except Exception:
                pass

        if agent.memory and final_answer:
            try:
                agent.memory.add_message("assistant", final_answer)
            except Exception:
                pass

        if agent.tracer:
            try:
                agent.tracer.add_step("final_answer", final_answer[:200],
                                      tokens=usage_info.get("total_tokens", 0))
            except Exception:
                pass

        if turn_thinking_started:
            yield StreamEvent(type="thinking_end")

        yield StreamEvent(type="done")
        return

    # 超过最大步数
    if turn_thinking_started:
        yield StreamEvent(type="thinking_end")
    final_answer = agent._force_answer()
    yield StreamEvent(type="token", content=final_answer)
    yield StreamEvent(type="done")


def run_stream(agent: AllenAgent, query: str) -> Generator[StreamEvent, None, None]:
    """流式运行 Agent — Plan & Execute 架构

    Args:
        agent: AllenAgent 实例
        query: 用户输入

    Yields:
        StreamEvent
    """
    if not query or not query.strip():
        yield StreamEvent(type="error", content="请输入有效的问题。")
        return

    if agent.reflect_engine:
        agent.reflect_engine.reset()

    if agent.guardrail:
        input_check = agent.guardrail.check_input(query)
        if not input_check.passed:
            yield StreamEvent(type="error", content=f"输入被安全策略拦截：{input_check.reason}")
            return
        query = input_check.sanitized_text

    if agent.tracer:
        agent.tracer.start(query)
    if agent.memory:
        agent.memory.set_system_prompt(agent._build_system_prompt())
        agent.memory.add_message("user", query)
    if agent.guardrail:
        agent.guardrail.set_system_prompt(agent._build_system_prompt())

    plan = agent._plan(query)
    subtasks = plan["subtasks"]

    try:
        if len(subtasks) <= 1:
            yield from execute_task_stream(agent, query, max_steps=25)
            return

        yield StreamEvent(type="planning_start", content=f"已将任务拆分为 {len(subtasks)} 个子任务")

        subtask_results = []

        for step, task in enumerate(subtasks, 1):
            yield StreamEvent(
                type="subtask_start",
                content=f"({step}/{len(subtasks)}) {task[:80]}",
                step=step,
            )

            assistant_started = False
            subtask_answer = ""
            for event in execute_task_stream(agent, task, max_steps=25):
                if event.type == "done":
                    pass
                elif event.type == "token":
                    subtask_answer += event.content
                    if not assistant_started:
                        assistant_started = True
                elif event.type == "cancelled":
                    yield event
                    return
                else:
                    yield event

            subtask_results.append(subtask_answer.strip())
            yield StreamEvent(type="subtask_done", step=step, total=len(subtasks))

            # 🔗 上下文桥接：告知上一个子任务结果，仅提供参考不限制后续工具使用
            if step < len(subtasks) and agent.memory:
                agent.memory.add_message(
                    "user",
                    "[系统] 上一个子任务已完成。继续当前任务，按需使用工具。"
                )

        final_answer = agent._merge(subtask_results, query)

        if agent.guardrail and final_answer:
            output_check = agent.guardrail.check_output(final_answer)
            final_answer = output_check.sanitized_text

        if agent.memory and final_answer:
            agent.memory.add_message("assistant", final_answer)

        yield StreamEvent(type="token", content=final_answer)
        yield StreamEvent(type="done")

    except Exception as e:
        yield StreamEvent(type="error", content=f"Agent 执行异常：{e}")
