# Allen.md — Agent 持久记忆

## 用户偏好
- 喜欢吃冰淇淋
- 喜欢的运动：游泳

## 项目约定
- ReAct 循环架构：Think → Act → Observe，max_steps=5
- 所有工具继承 BaseTool，必须实现 execute() 和 get_schema()
- 工具结果处理三层策略互斥：语义过滤 → LLM 摘要化（>1500字）→ 按类型截断
- 含错误/异常的工具结果原样保留，不摘要不截断
- 安全护栏 Guardrail 四阶段检查：输入过滤 → 速率限制（10次/分钟）→ 工具权限 → 输出过滤
- 搜索引擎按语种分流，健康检查 + 加权轮询 + 失败自动降级下一个引擎
- 短期记忆滑动窗口 max_turns=10，超出丢弃
- 多轮对话后调用 merge_last_tool_results() 合并 tool_calls 为 LLM 摘要
- LLM Provider 统一管理，支持 openai/anthropic 双协议，指数退避重试 3 次
- 长期记忆 Allen.md 启动时加载到 System Prompt，四段结构
- 配置由 .env（密钥）+ models.yaml（模型参数）管理
- 向量数据库使用 ChromaDB，文档支持 .txt 和 .md
- 可观测性追踪：每次 LLM 调用、工具调用、Token 消耗、费用估算

## 重要事实

## 待办
