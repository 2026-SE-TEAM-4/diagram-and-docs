# 04. 블랙박스 통합·보안·동시성 스위트 — pytest

## 목적

현재 `/auth`만 커버된 통합 테스트를 핵심 도메인(예약·승인·쿼터)으로 확장합니다.
교재의 블랙박스 기법(동등 분할·경계값·원인-결과)을 테스트 케이스 도출 방법으로 쓰고, RBAC 보안 테스트와 **쿼터 경쟁 상태 재현 테스트**까지 한 스위트에 담습니다.

- 담당 테스트: 계획서 3.1 보안 / 5.1 동등분할 / 5.2 경계값 ★ / 5.3 원인-결과 / 5.4 커버리지
- 기반: 기존 `backend/tests/integration/conftest.py`의 testcontainers 패턴(실제 Postgres 16 + Redis 7 컨테이너, 테스트마다 스키마 재생성·Redis flush)을 **그대로 재사용**합니다. 새 프레임워크 없음.

## 파일 구조 (backend/tests/ 확장)

```text
backend/tests/
├── unit/
│   └── test_security.py          # 기존
└── integration/
    ├── conftest.py               # 기존 + 픽스처 추가 (역할별 클라이언트, 시드)
    ├── test_auth.py              # 기존
    ├── test_reservations.py      # 신규: UC04~07 — 동등분할·경계값
    ├── test_approval.py          # 신규: UC09 — 원인-결과 결정 테이블
    ├── test_quota.py             # 신규: UC10 — 쿼터 경계값
    ├── test_rbac.py              # 신규: 권한 경계 (보안)
    └── test_concurrency.py       # 신규: 쿼터 경쟁 상태·낙관적 락 재현 ★
```

## 핵심 설계

### 1) 픽스처 확장 — `conftest.py`

테스트마다 반복될 "역할별 로그인 + 시드"를 픽스처로 만듭니다.

```python
@pytest_asyncio.fixture
async def seeded(client):
    """팀 1개 + 서버 3대 + 쿼터(limit=3) + 계정(STU/MGR/ADM, 타팀 MGR) 시드."""
    ...
    return SeedData(team_id=..., server_ids=[...], quota_limit=3)

@pytest_asyncio.fixture
async def as_stu(client, seeded):   # 학생 토큰이 실린 클라이언트
@pytest_asyncio.fixture
async def as_mgr(client, seeded):   # 매니저
@pytest_asyncio.fixture
async def as_other_mgr(client, seeded):  # 다른 팀 매니저 (RBAC 경계용)
```

### 2) 동등 분할 + 경계값 — `test_reservations.py`, `test_quota.py`

케이스를 표로 먼저 만들고 `parametrize`로 그대로 옮깁니다. 표가 곧 리뷰 자료가 됩니다.

```python
# 쿼터 (limit=3): 경계 3점을 정확히 짚는다
@pytest.mark.parametrize("pre_used, expected", [
    (2, 201),   # limit-1 : 마지막 한 자리 → 성공
    (3, 422),   # limit   : 꽉 참 → 거부
])
async def test_quota_boundary(as_stu, seeded, pre_used, expected): ...

# 예약 시간 경계
@pytest.mark.parametrize("start, end, expected", [
    (NOW + 1h, NOW + 2h, 201),   # 정상
    (NOW + 1h, NOW + 1h, 422),   # start == end (0분)
    (NOW - 1h, NOW + 1h, 422),   # 과거 시각
])
async def test_time_boundary(as_stu, start, end, expected): ...
```

로그인 잠금 경계(실패 4회 통과 / 5회째 429)는 기존 `test_auth.py`에 있으면 유지, 없으면 같은 방식으로 추가합니다.

### 3) 원인-결과 결정 테이블 — `test_approval.py`

`POST /approval-requests/{id}/decision`의 조건 조합을 표로 전부 나열합니다.

```python
# (요청 상태, 호출자 역할, 같은 팀?, 결정) → 기대 결과
DECISION_TABLE = [
    ("PENDING",  "MGR", True,  "approve", 200),  # 정상 승인 → 예약 생성 + RESERVED
    ("PENDING",  "MGR", True,  "reject",  200),  # 정상 거절
    ("PENDING",  "MGR", False, "approve", 403),  # 다른 팀
    ("PENDING",  "STU", True,  "approve", 403),  # 권한 없음
    ("APPROVED", "MGR", True,  "approve", 409),  # 비PENDING 재결정
    ("REJECTED", "MGR", True,  "approve", 409),
]

@pytest.mark.parametrize("state, role, same_team, decision, expected", DECISION_TABLE)
async def test_decision(...): ...

# 승인 성공 케이스는 상태코드만이 아니라 부수효과까지:
# 예약이 생성됐는가 / 서버가 RESERVED인가 / quota.used가 +1 됐는가
```

### 4) RBAC 권한 경계 — `test_rbac.py`

"역할 × 보호 엔드포인트" 행렬을 한 곳에 모읍니다.

```python
MATRIX = [
    # (역할 픽스처, 메서드, 경로, 기대)
    ("as_stu", "GET",  "/approval-requests",   403),
    ("as_stu", "GET",  "/teams/{other}/quotas", 403),
    ("as_mgr", "GET",  "/approval-requests",   200),
    ("as_other_mgr", "POST", "/approval-requests/{id}/decision", 403),  # 타팀
    (None,     "GET",  "/reservations",        401),  # 토큰 없음
]
```

설정 약점 2건(CORS `*`+credentials, 기본 `JWT_SECRET`)은 테스트보다 **수정**이 맞으므로, 여기서는 회귀 방지 테스트만 둡니다(예: 설정값이 기본 시크릿이면 실패하는 테스트).

### 5) 동시성 재현 — `test_concurrency.py` ★

스파이크 테스트(부하 도구)가 확률적으로 드러내는 버그를, 여기서는 **결정적으로 재현**합니다. 우선순위 1위 항목의 단위 재현 도구입니다.

```python
async def test_quota_race(client_factory, seeded):
    """남은 쿼터 1자리에 동시 예약 10건 → 성공은 정확히 1건이어야 한다.
    quota.used에 락이 없으므로 현재 코드는 이 테스트에 실패할 것으로 예상.
    (= 버그를 증명하는 테스트. 수정 후 통과로 바뀌는 것이 목표)"""
    await fill_quota_until_one_left(seeded)
    results = await asyncio.gather(
        *[post_reservation(c) for c in clients(10)]
    )
    assert sum(r.status_code == 201 for r in results) == 1

async def test_optimistic_lock(client_factory, seeded):
    """같은 서버에 동시 예약 10건 → 1건 성공, 9건은 409 (server.version 락 검증)."""
    results = await asyncio.gather(*[post_same_server(c) for c in clients(10)])
    assert sum(r.status_code == 201 for r in results) == 1
    assert sum(r.status_code == 409 for r in results) == 9
```

주의: ASGITransport(인프로세스)로는 단일 이벤트 루프라 진짜 동시성이 약합니다. 이 두 테스트는 **uvicorn을 실제 기동한 뒤 네트워크로 동시 요청**을 보내는 픽스처(`live_server`)를 사용합니다.

### 6) 커버리지 측정 (화이트박스 연결)

```bash
pytest backend/tests --cov=app/services --cov-branch --cov-report=html
```

목표: `reservation_service` · `auth_service` · `approval_service` 라인·분기 80% 이상.
특히 낙관적 락 분기(`rowcount==0 → 409` vs 성공)와 상태 가드(`if status != RESERVED`)의 **양쪽 분기**가 모두 실행되는지 HTML 리포트에서 확인합니다.

## 실행 방법

```bash
cd backend
pytest tests/integration -m integration            # 전체 통합
pytest tests/integration/test_concurrency.py -v    # 동시성만
pytest tests --cov=app/services --cov-branch --cov-report=html
```

## 합격 판정

| 파일 | 판정 |
| :--- | :--- |
| test_reservations / test_quota | 동등분할·경계값 표의 모든 행 통과 |
| test_approval | 결정 테이블 전 행 + 승인 부수효과 3종 통과 |
| test_rbac | 행렬 전 행이 기대 코드(401/403/200) 반환 |
| test_concurrency | 성공 건수가 정확히 기대값 (현재 코드는 실패 예상 → 버그 증명) |
| 커버리지 | 핵심 서비스 3종 라인·분기 ≥ 80% |

## 구현 순서

1. `conftest.py` 픽스처 확장 (seeded + 역할별 클라이언트)
2. `test_quota.py` + `test_reservations.py` (경계값 ★ — 우선순위 2위)
3. `test_concurrency.py` (우선순위 1위지만 live_server 픽스처가 필요해 2단계 뒤에)
4. `test_approval.py` 결정 테이블
5. `test_rbac.py` + 커버리지 리포트 확인
