"""
搜索引擎实现
- BaiduAISearchEngine: 百度千帆AI搜索（国内，免费额度）
- TavilyEngine: Tavily搜索（AI优化）
- DuckDuckGoEngine: DuckDuckGo搜索（免费通用）
"""

import os
import logging
import httpx
from abc import ABC, abstractmethod

from schemas.search import SearchResult

logger = logging.getLogger(__name__)


class BaseEngine(ABC):
    """搜索引擎基类"""

    def __init__(self, name: str, timeout: float = 30.0):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        """执行搜索"""
        pass


class BaiduAISearchEngine(BaseEngine):
    """
    百度千帆AI搜索
    优点：国内服务、无需代理、免费额度100次/天、搜索+智能总结
    文档：https://cloud.baidu.com/doc/qianfan/index.html
    """

    def __init__(self, api_key: str = None, timeout: float = 60.0):
        super().__init__("baidu_ai", timeout)
        self.api_key = api_key or os.getenv("BAIDU_API_KEY", "")

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        logger.info(f"[{self.name}] API Key: %s...", self.api_key[:20] if self.api_key else "空")

        if not self.api_key:
            logger.warning(f"[{self.name}] 未配置 API Key，跳过")
            return []

        try:
            url = "https://qianfan.baidubce.com/v2/ai_search/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            json_data = {
                "model": "ernie-4.5-turbo-32k",
                "messages": [{"role": "user", "content": query}]
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=json_data)

            logger.info(f"[{self.name}] 状态码: %d", response.status_code)

            if response.status_code != 200:
                logger.warning(f"[{self.name}] 请求失败: %s", response.text[:200])
                return []

            data = response.json()
            logger.debug(f"[{self.name}] 响应keys: %s", list(data.keys()))

            # 检查是否是错误响应
            if "code" in data:
                logger.warning(f"[{self.name}] 错误: code=%s, message=%s", data.get('code'), data.get('message'))

                # 如果是模型错误，尝试其他模型
                if "invalid_model" in str(data.get('code')):
                    logger.info(f"[{self.name}] 尝试其他模型...")
                    models = ["ernie-4.0-8k", "ernie-3.5-8k", "ernie-speed-128k"]
                    for model in models:
                        try:
                            json_data["model"] = model
                            with httpx.Client(timeout=self.timeout) as client:
                                resp = client.post(url, headers=headers, json=json_data)
                            if resp.status_code == 200:
                                resp_data = resp.json()
                                if "choices" in resp_data:
                                    logger.info(f"[{self.name}] 使用模型: %s", model)
                                    data = resp_data
                                    break
                        except Exception:
                            continue
                    else:
                        logger.warning(f"[{self.name}] 所有模型都不可用")
                        return []
                else:
                    return []

            # 提取AI回答
            answer = ""
            if "choices" in data and data["choices"]:
                answer = data["choices"][0].get("message", {}).get("content", "")

            # 提取搜索引用
            results = []
            if answer:
                results.append(SearchResult(
                    title=f"百度AI搜索: {query}",
                    snippet=answer,
                    url="https://qianfan.baidubce.com",
                    source="baidu_ai"
                ))

            # 添加引用来源
            for ref in data.get("references", [])[:num_results-1]:
                results.append(SearchResult(
                    title=ref.get("title", ""),
                    snippet=ref.get("content", "")[:200],
                    url=ref.get("url", ""),
                    source="baidu_web"
                ))

            return results

        except Exception as e:
            logger.error(f"[{self.name}] 搜索失败: %s: %s", type(e).__name__, e)
            return []


class TavilyEngine(BaseEngine):
    """
    Tavily 搜索引擎
    优点：专为AI设计，结果结构化，有免费额度
    缺点：需要API Key
    """

    def __init__(self, api_key: str = None, timeout: float = 30.0):
        super().__init__("tavily", timeout)
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        if not self.api_key:
            logger.warning(f"[{self.name}] 未配置 API Key，跳过")
            return []

        url = "https://api.tavily.com/search"
        headers = {"Content-Type": "application/json"}
        json_data = {
            "api_key": self.api_key,
            "query": query,
            "max_results": num_results,
            "search_depth": "basic",
            "include_answer": True
        }

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                response = client.post(url, headers=headers, json=json_data)

            if response.status_code != 200:
                return []

            data = response.json()
            results = []
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    snippet=item.get("content", ""),
                    url=item.get("url", ""),
                    source="tavily"
                ))
            return results[:num_results]

        except Exception as e:
            logger.error(f"[{self.name}] 搜索失败: %s", e)
            return []


class DuckDuckGoEngine(BaseEngine):
    """
    DuckDuckGo 搜索引擎
    优点：免费、无需API Key、稳定
    缺点：结果可能不如其他引擎丰富
    """

    def __init__(self, timeout: float = 30.0):
        super().__init__("duckduckgo", timeout)

    def search(self, query: str, num_results: int = 5) -> list[SearchResult]:
        try:
            from ddgs import DDGS
        except ImportError:
            logger.error(f"[{self.name}] 请安装: pip install ddgs")
            return []

        try:
            results = []
            for item in DDGS().text(query, max_results=num_results):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    snippet=item.get("body", ""),
                    url=item.get("href", ""),
                    source="duckduckgo"
                ))
            return results
        except Exception as e:
            logger.error(f"[{self.name}] 搜索失败: %s", e)
            return []
