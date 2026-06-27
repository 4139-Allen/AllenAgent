"""
SSE 流式聊天接口

职责: 解析 HTTP 参数 → 调服务层 → SSE 响应
"""

import asyncio
import dataclasses
import json
import logging

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from api.schemas.chat import ChatRequest
from api.dependencies import AppState, get_app_state
from schemas.stream import StreamEvent
from services.agent_service import run_agent_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def _serialize(event: StreamEvent) -> str:
    d = {}
    for f in dataclasses.fields(event):
        if f.name == "confirm_callback":
            continue
        v = getattr(event, f.name)
        if v is None or isinstance(v, (str, int, float, bool)):
            d[f.name] = v
        elif isinstance(v, (list, dict)):
            d[f.name] = v
        else:
            d[f.name] = str(v)[:2000]
    return json.dumps(d, ensure_ascii=False)


async def _to_async(sync_gen):
    """同步生成器 → 异步迭代器"""
    loop = asyncio.get_event_loop()
    q = asyncio.Queue(maxsize=64)
    _SENTINEL = object()

    def _producer():
        try:
            for ev in sync_gen:
                loop.call_soon_threadsafe(q.put_nowait, ev)
        except Exception as e:
            loop.call_soon_threadsafe(q.put_nowait, e)
        finally:
            loop.call_soon_threadsafe(q.put_nowait, _SENTINEL)

    loop.run_in_executor(None, _producer)

    while True:
        item = await q.get()
        if item is _SENTINEL:
            return
        if isinstance(item, Exception):
            raise item
        yield item


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, state: AppState = Depends(get_app_state)):
    """发送消息并返回 SSE 流式响应"""
    stream_gen, saved_id = run_agent_session(state, body.message, body.conversation_id, reasoning_effort=body.reasoning_effort)

    async def _generate():
        yield {
            "event": "meta",
            "data": json.dumps({"type": "meta", "conversation_id": saved_id[0] or ""}, ensure_ascii=False),
        }

        try:
            async for ev in _to_async(stream_gen):
                yield {"event": ev.type, "data": _serialize(ev)}
        except Exception as e:
            logger.exception("[API] 流异常: %s", e)
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "content": f"服务端错误: {e}"}, ensure_ascii=False),
            }
        finally:
            yield {
                "event": "done",
                "data": json.dumps({"type": "done", "conversation_id": saved_id[0]}, ensure_ascii=False),
            }

    return EventSourceResponse(_generate())
