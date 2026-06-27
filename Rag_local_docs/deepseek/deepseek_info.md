# DeepSeek 大语言模型

## 公司介绍

DeepSeek（深度求索）是一家专注于 AI 大模型研发的公司，致力于实现通用人工智能（AGI）。公司以技术创新著称，在模型效率和推理能力方面取得显著突破。

## 模型系列

### 1. DeepSeek-V3（通用对话）

- **定位**：通用大语言模型
- **上下文窗口**：64K tokens
- **特点**：
  - 强大的中文理解和生成能力
  - 支持工具调用（Tool Use / Function Calling）
  - 支持 JSON Mode 结构化输出
  - 性价比极高

### 2. DeepSeek-R1（推理增强）

- **定位**：推理专用模型
- **特点**：
  - 内置 Chain-of-Thought（思维链）
  - 适合数学、代码、复杂逻辑任务
  - 推理过程透明可见
  - 在多项推理基准测试中表现优异

### 3. DeepSeek-Coder（代码专用）

- **定位**：代码生成和理解
- **特点**：
  - 支持多种编程语言
  - 代码补全、解释、重构
  - 上下文理解能力强

## API 使用

### 兼容性

DeepSeek API **完全兼容 OpenAI SDK**，只需修改两个参数：

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-deepseek-api-key",
    base_url="https://api.deepseek.com"  # 唯一区别
)

# 之后的用法与 OpenAI 完全相同
response = client.chat.completions.create(
    model="deepseek-v4-flash",  # 或 "deepseek-v4-pro"
    messages=[{"role": "user", "content": "你好"}]
)
```

### 模型选择指南

| 场景 | 推荐模型 | 原因 |
|------|----------|------|
| 日常对话 | deepseek-v4-flash | 速度快，成本低 |
| 数学计算 | deepseek-v4-pro | 推理能力强 |
| 代码生成 | deepseek-v4-flash | 代码优化 |
| 工具调用 | deepseek-v4-flash | 支持 Function Calling |
| 长文档处理 | deepseek-v4-pro | 1M 上下文，384K 输出 |

### 价格优势

相比 GPT-4，DeepSeek 价格低一个数量级：

| 模型 | 输入价格 | 输出价格 |
|------|----------|----------|
| DeepSeek-Chat | ¥1/百万tokens | ¥2/百万tokens |
| GPT-4 | $30/百万tokens | $60/百万tokens |

适合学习、原型开发和中小规模应用。

## Function Calling（工具调用）

DeepSeek 支持标准的 Function Calling 格式：

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            }
        }
    }
]

response = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "北京天气怎么样？"}],
    tools=tools,
    tool_choice="auto"
)
```

## 使用技巧

### 1. System Prompt 设计

```
你是一个专业的Python开发助手。
- 代码风格遵循PEP8
- 优先使用标准库
- 给出完整可运行的代码示例
```

### 2. 温度参数（Temperature）

| 值 | 适用场景 |
|----|----------|
| 0.0-0.3 | 事实问答、代码生成、RAG |
| 0.5-0.7 | 通用对话、文案写作 |
| 0.8-1.0 | 创意写作、头脑风暴 |

### 3. 长文本处理

- 利用 64K 窗口处理长文档
- 关键信息放在 prompt 开头或结尾（避免中间遗忘）
- 使用分段处理超长文本

## 局限性

1. **知识截止**：训练数据有时间限制
2. **多模态**：目前主要支持文本，图像能力有限
3. **实时信息**：无法获取最新资讯（需配合搜索工具）
4. **数学计算**：复杂计算仍需借助工具

## 最佳实践

1. **明确指令**：清晰描述任务要求
2. **提供示例**：用 few-shot 提升输出质量
3. **结构化输出**：需要 JSON 时明确说明格式
4. **错误处理**：API 调用可能失败，做好重试机制
5. **流式输出**：长回答使用 stream=True 提升用户体验
