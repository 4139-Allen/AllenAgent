# Agent TUI 设计思想：事件流驱动

> Agent 不是聊天记录，Agent 是事件流（Event Stream）。
> 聊天消息只是事件流中的一种事件。

## 核心问题

很多人开发 Agent TUI 时：

```python
print(llm_response)
```

直接把模型返回的 Markdown 输出，结果体验很差。

## 正确架构

```
LLM
 ↓
Agent Runtime
 ↓
Event Stream
 ↓
Renderer
 ↓
TUI
```

Claude Code、OpenAI Codex CLI、Aider 的核心不是聊天界面，而是：

**事件流(Event Stream) + 消息渲染(Message Rendering)**

## 推荐事件类型

```
USER
ASSISTANT
PLAN
THINKING
TOOL_CALL
TOOL_RESULT
TASK_START
TASK_END
FILE_CHANGE
ARTIFACT
ERROR
FINAL
```

每种消息对应不同 Renderer。

## 为什么体验好？

**增量渲染**——用户一直有反馈：

```
等待10秒 → 突然输出全部内容        ❌
Thinking... → Searching... → Done  ✅
```

## 分层设计

```python
class Event(BaseModel):
    id: str
    timestamp: float
    type: str
    payload: dict
```

```
TUI层不要直接渲染LLM
应该：LLM → Agent Runtime → Event Stream → Renderer → TUI
```

## 好处

CLI / Web / 桌面端 / VSCode插件 共享同一套 Event Stream。

从零设计通用 Agent TUI 时，优先设计：
1. **Event Schema**
2. **Runtime**
3. **Renderer**

而不是先设计聊天气泡。
