# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Allen Agents 是一个基于 LLM 的智能问答系统，采用 RAG + Agent（ReAct 推理循环）+ 多引擎搜索架构。Python 3.11+，中文优先。

## 常用命令

```bash
# 运行
python main.py          # CLI 终端模式
python main.py --tui    # TUI 图形界面（Textual）
allen                   # 等同于 --tui（pyproject.toml 注册的入口）

# 安装依赖
pip install -e .

# 运行单个模块测试
python -c "from config import AppConfig; c = AppConfig.from_env(); print(c.available_models)"
```

## 架构

分层架构，数据流：用户输入 → 感知层 → Agent(ReAct循环) → 工具调度 → LLM/搜索/知识库 → 安全护栏 → 输出

```
main.py                    # 入口，create_agent() 组装所有组件
├── agents/                # AllenAgent（ReAct循环）、ReflectEngine（自我反思）
├── tools/                 # 7个工具：知识库、搜索、文件、图片、PDF、Shell、记忆
├── services/              # RAGEngine（检索生成）、搜索引擎路由（百度/Tavily/DDG）
├── infrastructure/        # LLMProvider（双协议）、ModelManager、Embedding、ChromaDB
├── memory/                # 三层记忆：短期(滑动窗口) → 中期(JSONL) → 长期(Allen.md)
├── guardrails/            # 四层防护：输入过滤、输出脱敏、工具权限、频率限制
├── frontends/             # CLI + TUI，共享命令注册表
├── perception/            # 输入类型检测、截断清洗、语言检测
├── schemas/               # 数据类：ToolResult、StreamEvent、SearchResult 等
└── config.py              # AppConfig.from_env() 从 models.yaml + .env 加载
```

## 核心设计模式

**工具扩展**：继承 `BaseTool`，实现 `execute()` 和 `_get_parameters()`，返回 `ToolResult`。新工具在 `main.py` 的 `create_agent()` 中注册。

**流式优先**：`AllenAgent.run_stream()` yield `StreamEvent` 供前端实时消费。同步版 `run()` 内部调用流式实现。

**模型配置外部化**：`models.yaml` 集中管理所有提供商配置（API key、模型列表、协议类型）。支持 OpenAI 兼容和 Anthropic 原生两种协议，通过 `protocol` 字段切换。

**安全护栏贯穿全链路**：输入 → `InputFilter`（Prompt注入检测）；工具调用 → `ToolPolicy`（权限分级）+ `RateLimiter`（频率限制）；输出 → `OutputFilter`（脱敏）。

**记忆三层结构**：`ConversationMemory`（内存滑动窗口）→ `ConversationStore`（JSONL持久化）→ `AllenMemory`（Allen.md跨会话记忆）。

**搜索纪律**：`SearchWebTool` 内置相似度去重（阈值0.92）和会话搜索次数限制（10次）。

## 配置文件

| 文件 | 内容 | 提交Git |
|------|------|---------|
| `models.yaml` | 模型提供商配置（含API key） | ❌ |
| `models.yaml.example` | 模板文件 | ✅ |
| `.env` | 搜索引擎API key | ❌ |
| `Allen.md` | Agent持久记忆 | 可选 |
| `Rag_local_docs/` | RAG知识库文档 | 可选 |

## 关键文件

- `agents/allen_agent.py` — Agent 核心，`run_stream()` 是最核心方法（~400行）
- `infrastructure/llm_provider.py` — 统一 LLM 客户端，支持 OpenAI/Anthropic 双协议
- `config.py` — 配置入口，`AppConfig` 数据类
- `services/search/router.py` — 搜索路由，语种检测 + 引擎选择 + 容错切换
- `guardrails/guardrail.py` — 安全护栏统一入口
