"""부하 단계 정의(순수 데이터).

locust에 의존하지 않으므로 CLI 부모 프로세스에서 import해도 gevent 몽키패치가
일어나지 않는다(부모는 asyncio/asyncpg를 쓰므로 monkey.patch_all 오염을 피해야 한다).
shapes.py(자식 locust 프로세스)와 loadtest.py(부모 CLI)가 이 한 곳을 함께 참조한다.

각 단계는 (누적 종료초, 목표 사용자수) 형식이다. spike만 spawn_rate를 단계별로 달리
지정하므로 (누적 종료초, 목표 사용자수, spawn_rate) 3-튜플을 쓴다.
"""

LOAD_STAGES: list[tuple[int, int]] = [
    (300, 10),
    (600, 50),
    (900, 100),
    (1200, 200),
]
LOAD_SPAWN_RATE = 20

STRESS_STAGES: list[tuple[int, int]] = [
    (120, 50),
    (420, 300),
    (720, 50),
]
STRESS_SPAWN_RATE = 20

SPIKE_STAGES: list[tuple[int, int, int]] = [
    (60, 5, 20),
    (75, 200, 200),
    (300, 5, 200),
]

ENDURANCE_USER_COUNT = 20
ENDURANCE_SPAWN_RATE = 5
ENDURANCE_DEFAULT_SEC = 21600


def timeline(shape: str, duration_sec: int | None = None) -> list[tuple[int, int]]:
    """진행률 표시용 단계 타임라인을 (누적 종료초, 목표 사용자수) 목록으로 반환한다.

    각 shape의 tick() 단계 경계와 동일해 진행 바가 '몇 단계 중 몇 번째'를 계산할 수
    있게 한다. 알 수 없는 shape이면 빈 목록을 반환한다.
    """
    if shape == "load":
        return list(LOAD_STAGES)
    if shape == "stress":
        return list(STRESS_STAGES)
    if shape == "spike":
        return [(end, users) for end, users, _rate in SPIKE_STAGES]
    if shape == "endurance":
        total = duration_sec if duration_sec is not None else ENDURANCE_DEFAULT_SEC
        return [(total, ENDURANCE_USER_COUNT)]
    return []
