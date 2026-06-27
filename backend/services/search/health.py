"""
搜索引擎健康检查
- 记录成功率、响应时间
- 动态计算权重
- 自动降级策略
"""

from datetime import datetime, timedelta

from schemas.search import EngineHealth


class HealthChecker:
    """健康检查管理器"""

    def __init__(self, recovery_interval: int = 300):
        """
        Args:
            recovery_interval: 不健康引擎的恢复检查间隔（秒）
        """
        self.engines: dict[str, EngineHealth] = {}
        self.recovery_interval = recovery_interval

    def register(self, engine_name: str):
        """注册引擎"""
        if engine_name not in self.engines:
            self.engines[engine_name] = EngineHealth(name=engine_name)

    def record_success(self, engine_name: str, latency: float):
        """记录成功"""
        if engine_name not in self.engines:
            self.register(engine_name)
        self.engines[engine_name].record_success(latency)

    def record_fail(self, engine_name: str):
        """记录失败"""
        if engine_name not in self.engines:
            self.register(engine_name)
        self.engines[engine_name].record_fail()

    def get_weight(self, engine_name: str) -> float:
        """获取引擎权重"""
        if engine_name not in self.engines:
            self.register(engine_name)
        return self.engines[engine_name].weight

    def is_healthy(self, engine_name: str) -> bool:
        """检查引擎是否健康"""
        if engine_name not in self.engines:
            return True
        health = self.engines[engine_name]

        # 如果不健康，检查是否到了恢复时间
        if not health.is_healthy and health.last_fail:
            time_since_fail = datetime.now() - health.last_fail
            if time_since_fail > timedelta(seconds=self.recovery_interval):
                health.reset()  # 尝试恢复
                return True
        return health.is_healthy

    def get_sorted_engines(self, engine_names: list[str]) -> list[str]:
        """
        按权重排序引擎（健康的优先，权重高的优先）
        """
        healthy = [name for name in engine_names if self.is_healthy(name)]
        unhealthy = [name for name in engine_names if not self.is_healthy(name)]

        # 按权重降序排序
        healthy.sort(key=lambda x: self.get_weight(x), reverse=True)

        return healthy + unhealthy  # 健康的在前，不健康的在后

    def get_stats(self) -> dict:
        """获取所有引擎的统计信息"""
        stats = {}
        for name, health in self.engines.items():
            stats[name] = {
                "success_rate": f"{health.success_rate:.1%}",
                "avg_latency": f"{health.avg_latency:.2f}s",
                "weight": f"{health.weight:.3f}",
                "total": health.total_requests,
                "healthy": health.is_healthy,
            }
        return stats
