"""
文本处理器
- 超长截断策略（保留头尾，丢中间）
- 语言检测
- 去噪（HTML 标签、多余空白）
"""

import re
from schemas.context import PerceptionContext


class TextHandler:
    """
    文本输入处理器

    截断策略：
        输入 > max_chars 时，保留前 head_ratio + 后 tail_ratio，
        中间替换为省略提示。
    """

    def __init__(
        self,
        max_chars: int = 12000,
        head_ratio: float = 0.6,
        tail_ratio: float = 0.3,
    ):
        """
        Args:
            max_chars: 最大字符数（约等于 token 数 * 2）
            head_ratio: 截断时保留头部比例
            tail_ratio: 截断时保留尾部比例
        """
        self.max_chars = max_chars
        self.head_ratio = head_ratio
        self.tail_ratio = tail_ratio

    def process(self, text: str, metadata: dict = None) -> PerceptionContext:
        """
        处理文本输入

        Args:
            text: 原始文本
            metadata: 附加信息

        Returns:
            PerceptionContext
        """
        if metadata is None:
            metadata = {}

        # 1. 去噪
        cleaned = self._clean(text)
        original_size = len(cleaned)

        # 2. 检测语言
        lang = self._detect_language(cleaned)
        metadata["language"] = lang

        # 3. 截断
        truncated = False
        if len(cleaned) > self.max_chars:
            cleaned = self._truncate(cleaned)
            truncated = True

        return PerceptionContext(
            text=cleaned,
            source_type="text",
            original_size=original_size,
            truncated=truncated,
            metadata=metadata,
        )

    def _clean(self, text: str) -> str:
        """去噪：HTML 标签、多余空白、特殊字符"""
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除多余空白行（保留最多 2 个连续换行）
        text = re.sub(r'\n{3,}', '\n\n', text)
        # 移除行首行尾空白
        text = '\n'.join(line.strip() for line in text.splitlines())
        return text.strip()

    def _detect_language(self, text: str) -> str:
        """简单语言检测"""
        if not text:
            return "unknown"

        chinese_chars = len(re.findall(r'[一-鿿]', text))
        total_chars = len(text)

        if total_chars > 0 and chinese_chars / total_chars > 0.3:
            return "zh"

        english_chars = len(re.findall(r'[a-zA-Z]', text))
        if total_chars > 0 and english_chars / total_chars > 0.5:
            return "en"

        return "mixed"

    def _truncate(self, text: str) -> str:
        """
        截断策略：保留头尾，丢中间

        ┌─ 前 60%（开头，通常是摘要/标题/背景）
        ├─ [...已省略 N 字符...]
        └─ 后 30%（结尾，通常是结论/总结）
        """
        head_len = int(self.max_chars * self.head_ratio)
        tail_len = int(self.max_chars * self.tail_ratio)

        head = text[:head_len]
        tail = text[-tail_len:]
        omitted = len(text) - head_len - tail_len

        # 在句子边界截断（避免截在句子中间）
        head = self._cut_at_sentence_end(head)
        tail = self._cut_at_sentence_start(tail)

        return f"{head}\n\n[...已省略 {omitted} 字符...]\n\n{tail}"

    def _cut_at_sentence_end(self, text: str) -> str:
        """在句子结束处截断（向前找最近的句号/换行）"""
        # 从末尾向前找句子结束符
        for i in range(len(text) - 1, max(len(text) - 200, 0), -1):
            if text[i] in '。！？.!?\n':
                return text[:i + 1]
        return text  # 找不到就硬截

    def _cut_at_sentence_start(self, text: str) -> str:
        """在句子开始处截断（向后找最近的句号+换行）"""
        for i in range(min(200, len(text))):
            if text[i] in '。！？.!?\n':
                return text[i + 1:].lstrip()
        return text  # 找不到就硬截
