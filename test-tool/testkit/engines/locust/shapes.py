"""Locust LoadTestShape 구현 4종.

SHAPE 환경변수로 locustfile.py가 어떤 shape을 사용할지 결정한다.
  load      - 점진적 램프업 (테스트 계획 2.1)
  stress    - 부하 급증 후 복귀 (테스트 계획 2.2)
  spike     - 순간 급증 (테스트 계획 2.3)
  endurance - 장기 지속 (테스트 계획 2.4)
"""

import os

from locust import LoadTestShape

from testkit.engines.locust import stages_data


def _intensity() -> int:
    """INTENSITY 환경변수를 읽어 강도 레벨을 반환한다. 미설정/오류면 1(기존 동작)."""
    try:
        return int(os.environ.get("INTENSITY", "1"))
    except ValueError:
        return 1


class LoadShape(LoadTestShape):
    """점진적 부하 증가 시나리오.

    단계별 사용자 수:
      0~300s   →  10명
      300~600s →  50명
      600~900s → 100명
      900~1200s → 200명
    """

    stages = stages_data.LOAD_STAGES
    spawn_rate = stages_data.LOAD_SPAWN_RATE

    def tick(self) -> tuple[int, float] | None:
        elapsed = self.get_current_user_count()  # 시간 기준으로 판단
        run_time = self.get_run_time()
        intensity = _intensity()

        for end_sec, user_count in self.stages:
            if run_time < end_sec:
                return (
                    stages_data.scale_user(user_count, intensity),
                    stages_data.scale_rate(self.spawn_rate, intensity),
                )

        return None


class StressShape(LoadTestShape):
    """스트레스 시나리오: 급증 후 복귀 구간이 핵심이다.

    단계별 사용자 수:
      0~120s   →  50명 (워밍업)
      120~420s → 300명 (최대 부하)
      420~720s →  50명 (복귀 — 성능 회복 측정)
    """

    stages = stages_data.STRESS_STAGES
    spawn_rate = stages_data.STRESS_SPAWN_RATE

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()
        intensity = _intensity()

        for end_sec, user_count in self.stages:
            if run_time < end_sec:
                return (
                    stages_data.scale_user(user_count, intensity),
                    stages_data.scale_rate(self.spawn_rate, intensity),
                )

        return None


class SpikeShape(LoadTestShape):
    """스파이크 시나리오: 짧은 시간에 극단적으로 사용자가 급증한다.

    단계별 사용자 수:
      0~60s    →   5명 (정상 트래픽)
      60~75s   → 200명 (스파이크, spawn_rate=200으로 즉시 투입)
      75~300s  →   5명 (복귀)
    """

    stages = stages_data.SPIKE_STAGES

    def tick(self) -> tuple[int, float] | None:
        run_time = self.get_run_time()
        intensity = _intensity()

        for end_sec, user_count, spawn_rate in self.stages:
            if run_time < end_sec:
                return (
                    stages_data.scale_user(user_count, intensity),
                    stages_data.scale_rate(spawn_rate, intensity),
                )

        return None


class EnduranceShape(LoadTestShape):
    """장기 지속 시나리오: 일정 사용자 수를 환경변수 DURATION_SEC 동안 유지한다.

    기본 지속 시간은 6시간(21600초), 사용자 수는 20명으로 고정한다.
    """

    user_count = stages_data.ENDURANCE_USER_COUNT
    spawn_rate = stages_data.ENDURANCE_SPAWN_RATE

    def tick(self) -> tuple[int, float] | None:
        duration_sec = int(
            os.environ.get("DURATION_SEC", str(stages_data.ENDURANCE_DEFAULT_SEC))
        )
        run_time = self.get_run_time()
        intensity = _intensity()

        if run_time < duration_sec:
            return (
                stages_data.scale_user(self.user_count, intensity),
                stages_data.scale_rate(self.spawn_rate, intensity),
            )

        return None
