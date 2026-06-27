"""
搜索路由器
- 语种检测
- 引擎选择（按语种分流）
- 容错切换（加权轮询 + 自动降级）
"""

import re
import time
from typing import Optional
from services.search.engines import BaseEngine, BaiduAISearchEngine, TavilyEngine, DuckDuckGoEngine
from services.search.health import HealthChecker
from schemas.search import SearchResult


class SearchRouter:
    """
    搜索路由器
    按语种自动选择最佳搜索引擎，支持容错切换
    """

    def __init__(
        self,
        baidu_api_key: str = None,
        tavily_api_key: str = None,
        timeout: float = 30.0,
    ):
        # 初始化搜索引擎
        self.engines: dict[str, BaseEngine] = {
            "baidu_ai": BaiduAISearchEngine(api_key=baidu_api_key, timeout=timeout),
            "tavily": TavilyEngine(api_key=tavily_api_key, timeout=timeout),
            "duckduckgo": DuckDuckGoEngine(timeout=timeout),
        }

        # 健康检查器
        self.health = HealthChecker()
        for name in self.engines:
            self.health.register(name)

        # 语种 → 引擎优先级配置
        self.language_priority = {
            "zh": ["baidu_ai", "duckduckgo", "tavily"],      # 中文：百度AI优先
            "en": ["tavily", "duckduckgo", "baidu_ai"],       # 英文：Tavily优先
            "default": ["duckduckgo", "baidu_ai", "tavily"],  # 其他：DuckDuckGo优先
        }

    def detect_language(self, text: str) -> str:
        """
        检测文本语种
        简单实现：统计中文字符占比
        """
        if not text:
            return "default"

        # 统计中文字符
        chinese_chars = len(re.findall(r'[一-鿿]', text))
        total_chars = len(text)

        # 中文占比超过 30% 则认为是中文
        if total_chars > 0 and chinese_chars / total_chars > 0.3:
            return "zh"

        # 检查是否主要是英文
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        if total_chars > 0 and english_chars / total_chars > 0.5:
            return "en"

        return "default"

    def get_engine_priority(self, query: str) -> list[str]:
        """
        根据查询语种获取引擎优先级列表
        """
        lang = self.detect_language(query)
        priority = self.language_priority.get(lang, self.language_priority["default"])

        # 按健康状态和权重排序
        return self.health.get_sorted_engines(priority)

    def search(
        self,
        query: str,
        num_results: int = 5,
        verbose: bool = True,
    ) -> list[SearchResult]:
        """
        执行搜索（带容错切换）

        Args:
            query: 搜索查询
            num_results: 返回结果数量
            verbose: 是否打印日志

        Returns:
            搜索结果列表
        """
        # 获取按语种排序的引擎列表
        engine_priority = self.get_engine_priority(query)

        if verbose:
            lang = self.detect_language(query)
            print(f"[搜索] 语种: {lang}，引擎顺序: {engine_priority}")

        # 依次尝试各个引擎
        for engine_name in engine_priority:
            engine = self.engines[engine_name]

            if verbose:
                print(f"[搜索] 尝试 {engine_name}...")

            # 记录开始时间
            start_time = time.time()

            try:
                results = engine.search(query, num_results=num_results)
                latency = time.time() - start_time

                if results:
                    # 成功
                    self.health.record_success(engine_name, latency)
                    if verbose:
                        print(f"[搜索] {engine_name} 成功，返回 {len(results)} 条结果，耗时 {latency:.2f}s")
                    return results
                else:
                    # 空结果也算失败
                    self.health.record_fail(engine_name)
                    if verbose:
                        print(f"[搜索] {engine_name} 返回空结果，切换下一个")

            except Exception as e:
                latency = time.time() - start_time
                self.health.record_fail(engine_name)
                if verbose:
                    print(f"[搜索] {engine_name} 失败: {e}，切换下一个")

        # 所有引擎都失败
        if verbose:
            print("[搜索] 所有引擎均失败")
        return []

    def get_stats(self) -> dict:
        """获取引擎健康统计"""
        return self.health.get_stats()
