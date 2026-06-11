"""Locust LoadTestShape 구현 4종.

SHAPE 환경변수로 locustfile.py가 어떤 shape을 사용할지 결정한다.
  load      - 점진적 램프업 (테스트 계획 2.1)
  stress    - 부하 급증 후 복귀 (테스트 계획 2.2)
  spike     - 순간 급증 (테스트 계획 2.3)
  endurance - 장기 지속 (테스트 계획 2.4)
"""

import os

from locust import LoadTestShape


class LoadShape(LoadTestShape):
    """점진적 부하 증가 시나리오.

    단계별 사용자 수:
      0~300s   →  10명
      300~600s →  50명
      600~900s → 100명
      900~1200s → 200명
    """

    stages = [
        (300, 10),
        (600, 50),
        (900, 100),
        (1200, 200),
    ]
    spawn_rate = 20

    def tick(self) -> tuple[int, float] | None:
        elapsed = self.get_current_user_count()  # 시간 기준으로 판단
        run_time = self.get_run_time()

        for end_sec, user_count in self.stages:
            if run_time < end_sec:
                return user_count, self.spawn_rate

        return None


class StressShape(LoadTestShape):
    """스트레스 시나리오: 급증 후 복귀 구간이 핵심이다.

    단계별 사용자 수:
      0~120s   →  50명 (워밍업)
      120~420s → 300명 (최대 부하)
      420~720s →  50명 (복귀 — 성능 회복 측정)
    """

    stages = [
        (120, 50),
        (420, 300),
        (720, 50),
    ]
    spawn_rate = 20

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()

        for end_sec, user_count in self.stages:
            if run_time < end_sec:
                return user_count, self.spawn_rate

        return None


class SpikeShape(LoadTestShape):
    """스파이크 시나리오: 짧은 시간에 극단적으로 사용자가 급증한다.

    단계별 사용자 수:
      0~60s    →   5명 (정상 트래픽)
      60~75s   → 200명 (스파이크, spawn_rate=200으로 즉시 투입)
      75~300s  →   5명 (복귀)
    """

    stages = [
        (60, 5, 20),
        (75, 200, 200),
        (300, 5, 200),
    ]

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()

        for end_sec, user_count, spawn_rate in self.stages:
            if run_time < end_sec:
                return user_count, spawn_rate

        return None


class EnduranceShape(LoadTestShape):
    """장기 지속 시나리오: 일정 사용자 수를 환경변수 DURATION_SEC 동안 유지한다.

    기본 지속 시간은 6시간(21600초), 사용자 수는 20명으로 고정한다.
    """

    user_count = 20
    spawn_rate = 5

    def tick(self) -> tuple[int, float] | None:
        duration_sec = int(os.environ.get("DURATION_SEC", "21600"))
        run_time = self.get_run_time()

        if run_time < duration_sec:
            return self.user_count, self.spawn_rate

        return None
