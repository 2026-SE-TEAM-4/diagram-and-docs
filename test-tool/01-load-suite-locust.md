# 01. 성능 4종 — `testkit load / stress / spike / endurance` (Locust 엔진)

> testkit 공통 구조(기술 선택·출력 규약·결과 저장)는 [00-testkit-cli.md](./00-testkit-cli.md) 참조. 이 문서는 성능 4종 명령의 엔진 설계만 다룹니다.

## 목적

성능 테스트 4종(부하·과부하·스파이크·내구력)을 testkit 서브커맨드 4개로 제공합니다.
4종의 차이는 "부하를 주는 모양"뿐이므로, **사용자 행동(태스크)은 공유하고 부하 프로파일(LoadTestShape)만 교체**합니다.

- 담당 테스트: 계획서 2.1 부하 / 2.2 과부하 / 2.3 스파이크 ★ / 2.4 내구력
- 엔진: Locust를 subprocess로 실행(`--headless --csv`)하고, testkit이 CSV를 파싱해 결과를 렌더링

## 관련 파일

```text
testing/testkit/
├── commands/loadtest.py      # 4개 서브커맨드: 계획 출력 → locust 실행 → 결과 렌더링
├── engines/locust/
│   ├── locustfile.py         # 진입점: SHAPE 환경변수로 유저·프로파일 선택
│   ├── users.py              # 사용자 행동 3종
│   └── shapes.py             # 부하 프로파일 4종
├── verify.py                 # 스파이크 종료 후 DB 정합성 검사 (공유 모듈)
└── seed.py                   # 시드 (공유 모듈)
```

## 핵심 설계

### 1) 사용자 행동 — `users.py`

실제 사용 패턴을 흉내 내는 3종. 읽기:쓰기 비율은 태스크 가중치로 표현합니다.

```python
class BrowsingUser(HttpUser):
    """일반 사용자: 조회 위주. load/endurance의 주력."""
    wait_time = between(1, 3)

    def on_start(self):
        self.token = login(self)   # 시드 계정 풀에서 하나 골라 로그인

    @task(5)
    def list_reservations(self): ...   # GET /reservations
    @task(2)
    def my_quota(self): ...            # GET /teams/{id}/quotas
    @task(1)
    def create_reservation(self): ...  # POST /reservations

class LoginUser(HttpUser):
    """로그인만 반복: bcrypt 병목 전용. stress에서 혼합."""

class InstantUser(HttpUser):
    """즉시 배정만 반복: 자원 쟁탈. spike 전용.
    409(자원 없음/충돌)는 정상 동작이므로 실패로 집계하지 않음."""
    wait_time = constant(0)
```

### 2) 부하 프로파일 — `shapes.py`

`LoadTestShape` 4종. 어떤 프로파일을 쓸지는 testkit이 `SHAPE` 환경변수로 넘깁니다.

```python
class LoadShape(LoadTestShape):
    """2.1 부하: 10 → 50 → 100 → 200명, 각 단계 5분 유지."""

class StressShape(LoadTestShape):
    """2.2 과부하: 정점 2~3배(300명) 5분 → 정상(50명) 복귀 5분.
    복귀 구간의 회복 여부가 핵심이므로 복귀 후에도 측정 지속."""

class SpikeShape(LoadTestShape):
    """2.3 스파이크: 평상 5명 → 1~2초 안에 200명 → 다시 5명."""

class EnduranceShape(LoadTestShape):
    """2.4 내구력: 동시 20명을 기본 6시간 유지 (--duration으로 조정)."""
```

### 3) testkit 쪽 흐름 — `commands/loadtest.py`

```text
[1/4] 사전 점검 (공통 preflight)
[2/4] 계획 출력: 시나리오·요청·부하 모양·측정 지표·합격 기준
[3/4] locust subprocess 실행 + stdout 파싱으로 Live 지표 갱신
      (locust --headless --csv <결과경로> --csv-full-history)
[4/4] CSV 파싱 → 지표 표 + 합격 기준별 PASS/FAIL
```

명령별 추가 동작:

- **spike**: 종료 후 `verify.py` 자동 실행 → 정합성 3종을 결과 표에 합산. 합격 기준이 응답 속도가 아니라 정합성이기 때문.
- **stress**: CSV 전체 이력에서 "복귀 구간"만 잘라 회복 시간(정상 응답률 복귀까지 걸린 초)을 따로 계산해 출력.
- **endurance**: 실행 중 30초 간격으로 `docker stats`·DB/Redis 연결 수를 CSV로 같이 수집(백그라운드 스레드). 결과에서 추이의 기울기(우상향 여부)를 판정.

### 4) DB 정합성 검사 — `verify.py` (★ 스파이크의 핵심)

asyncpg로 DB에 직접 접속해 3종 검사. `testkit verify`로 단독 실행도 가능.

```text
1. 활성 예약 수 <= 가용 서버 수        (낙관적 락 검증)
2. 팀별 quota.used <= quota.limit     (경쟁 상태 검증 — 계획서 최우선 확인 항목)
3. quota.used == 실제 활성 예약 수     (카운터와 실제값 일치)
어긋나면 어긋난 행을 표로 출력 + FAIL
```

## 실행 방법

```bash
cd testing
uv run testkit seed
uv run testkit load                      # 부하 (약 20분)
uv run testkit stress                    # 과부하 (약 12분)
uv run testkit spike                     # 스파이크 + 자동 정합성 검사 (약 5분)
uv run testkit endurance --duration 6h   # 내구력
```

## 합격 판정 (4단계 결과 출력에 그대로 반영)

| 명령 | 판정 |
| :--- | :--- |
| load | 동시 50명 구간에서 p95 < 300ms, 오류율 < 1% |
| stress | 부하 해제 후 2분 내 정상 응답률 복귀, 프로세스 다운 없음 |
| spike | 서버 생존 + **정합성 검사 3종 전부 통과** |
| endurance | 메모리·연결 수가 우상향하지 않음 |

## 구현 순서

1. `users.py` + `shapes.py` + `locustfile.py` (locust 단독으로 동작 확인)
2. `commands/loadtest.py` — load부터, CSV 파싱·판정까지
3. `verify.py` + spike 연동 (★ 우선순위 1위 — 여기까지가 1차 목표)
4. stress 회복 시간 계산, endurance 자원 추이 수집 (장시간 실행이라 마지막)
