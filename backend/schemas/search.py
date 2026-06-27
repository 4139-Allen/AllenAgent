"""搜索相关数据模型"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    snippet: str
    url: str
    source: str  # 来源引擎


@dataclass
class EngineHealth:
    """单个引擎的健康状态"""
    name: str
    total_requests: int = 0
    success_count: int = 0
    fail_count: int = 0
    total_latency: float = 0.0
    last_success: Optional[datetime] = None
    last_fail: Optional[datetime] = None
    consecutive_fails: int = 0

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_requests == 0:
            return 0.5  # 默认 50%
        return self.success_count / self.total_requests

    @property
    def avg_latency(self) -> float:
        """平均延迟（秒）"""
        if self.success_count == 0:
            return 5.0  # 默认 5 秒
        return self.total_latency / self.success_count

    @property
    def weight(self) -> float:
        """
        动态权重计算
        权重 = 成功率 * 0.7 + 速度分 * 0.3
        速度分 = 1 / (1 + avg_latency)，延迟越低分数越高
        """
        speed_score = 1 / (1 + self.avg_latency)
        return self.success_rate * 0.7 + speed_score * 0.3

    @property
    def is_healthy(self) -> bool:
        """是否健康（连续失败超过 5 次则认为不健康）"""
        return self.consecutive_fails < 5

    def record_success(self, latency: float):
        """记录成功"""
        self.total_requests += 1
        self.success_count += 1
        self.total_latency += latency
        self.last_success = datetime.now()
        self.consecutive_fails = 0

    def record_fail(self):
        """记录失败"""
        self.total_requests += 1
        self.fail_count += 1
        self.last_fail = datetime.now()
        self.consecutive_fails += 1

    def reset(self):
        """重置统计（用于恢复不健康的引擎）"""
        self.consecutive_fails = 0
