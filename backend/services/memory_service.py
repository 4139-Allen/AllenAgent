"""
长期记忆服务层

Allen.md 持久记忆的读取与写入。
"""


def get_memory(allen_memory):
    """读取所有长期记忆"""
    if not allen_memory:
        return {"content": "记忆功能未启用"}
    return {"content": allen_memory.get_all()}


def add_memory(allen_memory, fact: str):
    """添加一条长期记忆"""
    if not allen_memory:
        return {"status": "error", "message": "记忆功能未启用"}
    allen_memory.add_fact(fact)
    return {"status": "ok", "message": f"已记住: {fact}"}
