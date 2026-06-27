# Allen Agents

RAG + Agent + 多引擎搜索的智能问答系统

## 项目结构

```
Allen_agents/
├── main.py                 # 主程序入口
├── Rag_engine.py           # RAG 引擎（知识库、向量检索）
├── agents/
│   ├── __init__.py
│   ├── base.py             # Agent 基类
│   └── rag_agent.py        # RAG Agent（工具调用）
├── tools/
│   ├── __init__.py
│   ├── base.py             # 工具基类
│   ├── knowledge_tool.py   # 知识库工具
│   └── search_tool.py      # 网络搜索工具
├── search/
│   ├── __init__.py
│   ├── engines.py          # 搜索引擎（百度、Tavily、DuckDuckGo）
│   ├── health.py           # 健康检查
│   └── router.py           # 语种分流路由器
├── observability/          # 可观测性模块
│   ├── __init__.py
│   ├── models.py           # 数据类
│   ├── tracer.py           # 核心追踪器
│   ├── wrappers.py         # 封装函数
│   └── dashboard.py        # 可视化仪表盘
├── docs/                   # 知识库文档
│   ├── agent/
│   ├── rag/
│   └── deepseek/
├── data/
│   └── chroma_db/          # 向量数据库
├── .env                    # 环境变量
└── .env.example            # 环境变量示例
```

## 核心架构

```
用户提问
    ↓
┌─────────────────────────────────────┐
│            RAG Agent (LLM)          │
│  分析问题 → 决定使用哪个工具         │
└──────────────┬──────────────────────┘
               ↓
    ┌──────────┼──────────┐
    ↓          ↓          ↓
┌───────┐ ┌───────┐ ┌───────┐
│知识库  │ │搜索引擎│ │直接   │
│Tool   │ │Tool   │ │回答   │
└───────┘ └───────┘ └───────┘
    ↓          ↓          ↓
    └──────────┼──────────┘
               ↓
         汇总结果 → 生成答案

┌─────────────────────────────────────┐
│         Observability (可观测性)     │
│  追踪 LLM 调用、工具调用、Token 消耗 │
└─────────────────────────────────────┘
```

## 功能特性

### 1. RAG 引擎
- 文档加载（支持 .txt、.md）
- 文本分块（滑动窗口）
- 向量检索（ChromaDB）
- 相似度过滤

### 2. Agent 工具调用
- LLM 自主决策使用哪个工具
- 支持多工具组合
- 失败自动降级

### 3. 多引擎搜索
- 百度千帆AI搜索（中文优化，免费100次/天）
- Tavily（AI优化）
- DuckDuckGo（免费通用）
- 语种自动分流
- 健康检查 + 加权轮询

### 4. 可观测性
- Token 使用统计
- LLM 调用追踪
- 工具调用追踪
- 费用估算
- 可视化仪表盘

## 安装依赖

```bash
pip install openai chromadb sentence-transformers ddgs httpx python-dotenv
```

## 环境变量配置

复制 `.env.example` 为 `.env`，填入你的 API Key：

```bash
cp .env.example .env
```

必需：
- `DEEPSEEK_API_KEY`: DeepSeek API Key

可选（搜索引擎）：
- `BAIDU_API_KEY`: 百度搜索 API Key
- `TAVILY_API_KEY`: Tavily API Key

## 使用方法

### 1. 直接运行测试

```bash
python main.py
```

### 2. 在代码中使用

```python
from main import create_agent

# 创建 Agent
agent = create_agent()

# 提问
result = agent.run("什么是 RAG？")
print(result["answer"])
```

### 3. 单独使用 RAG

```python
from Rag_engine import RAGApp

app = RAGApp()
app.add_docs_folder()  # 加载 Rag_local_docs/ 目录
answer = app.ask("什么是 RAG？")
```

## 搜索引擎配置

### DuckDuckGo（默认，免费）
无需配置，直接使用。

### 百度千帆AI搜索（推荐）
1. 访问 [百度千帆](https://cloud.baidu.com/doc/qianfan/index.html)
2. 创建应用，获取 API Key
3. 设置环境变量 `BAIDU_API_KEY`
4. 免费额度：100次/天

### Tavily
1. 注册 [Tavily](https://tavily.com/)
2. 获取 API Key（免费 1000 次/月）
3. 设置环境变量 `TAVILY_API_KEY`

## 添加新工具

1. 在 `tools/` 目录创建新工具类
2. 继承 `BaseTool`
3. 实现 `execute` 方法
4. 在 Agent 中注册

```python
from tools.base import BaseTool, ToolResult

class MyTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="我的自定义工具"
        )

    def execute(self, query: str, **kwargs) -> ToolResult:
        # 实现逻辑
        return ToolResult(success=True, data="结果")
```

## 可观测性

独立封装的追踪系统，不修改 Agent 主逻辑。

### 使用方式

```python
from observability import AgentTracer, traced_llm_call, ObservabilityDashboard

tracer = AgentTracer()

with tracer.trace("查询天气") as trace:
    response = traced_llm_call(
        tracer, trace,
        client.chat.completions.create,
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": "今天天气怎么样？"}],
    )

dashboard = ObservabilityDashboard(tracer)
dashboard.print_summary()
```

### 自动记录

- LLM 调用：模型、Token、耗时
- 工具调用：工具名、参数、结果、耗时
- 整体追踪：任务、总耗时、总 Token、费用

### 保存位置

```
~/agent_traces/
├── trace_abc12345_20260614_120000.json
└── ...
```

## License

MIT
