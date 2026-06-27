"""
长期记忆管理
Allen.md — Agent 的持久化笔记，跨会话存在
启动时读入 system prompt，通过命令手动写入
"""

import re
from pathlib import Path
from datetime import datetime


class AllenMemory:
    """
    Allen.md 持久记忆管理

    文件结构：
        # Allen.md
        ## 用户偏好
        - xxx
        ## 项目约定
        - xxx
        ## 重要事实
        - 2026-06-16: xxx
        ## 待办
        - [ ] xxx
    """

    # 默认段落（按顺序）
    DEFAULT_SECTIONS = [
        "用户偏好",
        "项目约定",
        "重要事实",
        "待办",
    ]

    def __init__(self, filepath: str = None):
        if filepath is None:
            filepath = str(Path(__file__).parent.parent / "Allen.md")
        self.filepath = Path(filepath)
        self.sections: dict[str, list[str]] = {}
        self._load()

    def _load(self):
        """启动时读取 Allen.md"""
        if not self.filepath.exists():
            # 文件不存在，初始化空结构
            for section in self.DEFAULT_SECTIONS:
                self.sections[section] = []
            return

        content = self.filepath.read_text(encoding="utf-8")
        self._parse(content)

    def _parse(self, content: str):
        """解析 markdown 为段落字典"""
        current_section = None

        for line in content.splitlines():
            # 匹配 ## 标题
            match = re.match(r'^##\s+(.+)', line)
            if match:
                current_section = match.group(1).strip()
                if current_section not in self.sections:
                    self.sections[current_section] = []
                continue

            # 匹配列表项 "- xxx"
            if current_section and line.strip().startswith("- "):
                item = line.strip()[2:].strip()
                if item:
                    self.sections[current_section].append(item)

        # 确保默认段落存在
        for section in self.DEFAULT_SECTIONS:
            if section not in self.sections:
                self.sections[section] = []

    def _save(self):
        """写回 Allen.md"""
        lines = ["# Allen.md — Agent 持久记忆", ""]

        # 按默认顺序输出，额外段落追加到末尾
        ordered = list(self.DEFAULT_SECTIONS)
        for section in self.sections:
            if section not in ordered:
                ordered.append(section)

        for section in ordered:
            items = self.sections.get(section, [])
            lines.append(f"## {section}")
            if items:
                for item in items:
                    lines.append(f"- {item}")
            lines.append("")

        self.filepath.write_text("\n".join(lines), encoding="utf-8")

    def get_context(self) -> str:
        """返回要注入 system prompt 的内容"""
        if not self.sections or all(not v for v in self.sections.values()):
            return ""

        parts = []
        for section in self.DEFAULT_SECTIONS:
            items = self.sections.get(section, [])
            if items:
                items_text = "\n".join(f"  - {item}" for item in items)
                parts.append(f"【{section}】\n{items_text}")

        # 追加非默认段落
        for section, items in self.sections.items():
            if section not in self.DEFAULT_SECTIONS and items:
                items_text = "\n".join(f"  - {item}" for item in items)
                parts.append(f"【{section}】\n{items_text}")

        if not parts:
            return ""

        return "以下是关于用户和项目的持久记忆：\n" + "\n\n".join(parts)

    def add(self, section: str, text: str) -> str:
        """
        向指定段落追加一条记录

        Args:
            section: 段落名称
            text: 要追加的内容

        Returns:
            操作结果描述
        """
        if section not in self.sections:
            self.sections[section] = []

        # 为重要事实自动加日期
        if section == "重要事实":
            today = datetime.now().strftime("%Y-%m-%d")
            text = f"{today}: {text}"

        # 去重
        if text in self.sections[section]:
            return f"  ⚠️  已存在，未重复添加"

        self.sections[section].append(text)
        self._save()
        return f"  ✅ 已写入 [{section}]"

    def remove(self, section: str, index: int) -> str:
        """删除指定段落的第 N 条记录（从 1 开始）"""
        if section not in self.sections:
            return f"  ❌ 段落 [{section}] 不存在"

        items = self.sections[section]
        if index < 1 or index > len(items):
            return f"  ❌ 序号 {index} 超出范围（1-{len(items)}）"

        removed = items.pop(index - 1)
        self._save()
        return f"  🗑️  已删除: {removed}"

    def get_content(self) -> str:
        """返回完整 markdown 内容（用于 /memory 命令展示）"""
        if not self.filepath.exists():
            return "  📭 Allen.md 不存在，还没有持久记忆"

        return self.filepath.read_text(encoding="utf-8")

    def clear(self) -> str:
        """清空所有记忆"""
        for section in self.sections:
            self.sections[section] = []
        self._save()
        return "  🗑️  已清空所有持久记忆"

    def has_content(self) -> bool:
        """是否有内容"""
        return any(bool(v) for v in self.sections.values())

    def __repr__(self):
        total = sum(len(v) for v in self.sections.values())
        return f"<AllenMemory sections={len(self.sections)} items={total}>"
