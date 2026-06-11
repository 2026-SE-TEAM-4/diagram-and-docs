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

# 부하 강도(intensity) 허용 범위. 레벨이 곧 배율이다(레벨 N → ×N).
MIN_INTENSITY = 1
MAX_INTENSITY = 4


def factor(intensity: int = 1) -> int:
    """강도 레벨을 배율로 변환한다. 선형이라 레벨이 곧 배율이다(레벨 N → ×N).

    범위를 벗어나면 [MIN_INTENSITY, MAX_INTENSITY]로 클램프한다. 레벨 1은 ×1이라
    기존 동작과 byte-for-byte 동일하다.
    """
    clamped = max(MIN_INTENSITY, min(MAX_INTENSITY, intensity))
    return clamped


def scale_user(user_count: int, intensity: int = 1) -> int:
    """사용자 수에 강도 배율을 적용한다(정수, 최소 1)."""
    return max(1, round(user_count * factor(intensity)))


def scale_rate(spawn_rate: int, intensity: int = 1) -> int:
    """spawn_rate에 강도 배율을 적용한다(정수, 최소 1)."""
    return max(1, round(spawn_rate * factor(intensity)))


def timeline(
    shape: str,
    duration_sec: int | None = None,
    intensity: int = 1,
) -> list[tuple[int, int]]:
    """진행률 표시용 단계 타임라인을 (누적 종료초, 목표 사용자수) 목록으로 반환한다.

    각 shape의 tick() 단계 경계와 동일해 진행 바가 '몇 단계 중 몇 번째'를 계산할 수
    있게 한다. intensity로 목표 사용자수만 배율 조정하며(지속 시간은 불변), 기본값
    1은 기존 값과 동일하다. 알 수 없는 shape이면 빈 목록을 반환한다.
    """
    if shape == "load":
        return [(end, scale_user(users, intensity)) for end, users in LOAD_STAGES]
    if shape == "stress":
        return [(end, scale_user(users, intensity)) for end, users in STRESS_STAGES]
    if shape == "spike":
        return [(end, scale_user(users, intensity)) for end, users, _rate in SPIKE_STAGES]
    if shape == "endurance":
        total = duration_sec if duration_sec is not None else ENDURANCE_DEFAULT_SEC
        return [(total, scale_user(ENDURANCE_USER_COUNT, intensity))]
    return []
