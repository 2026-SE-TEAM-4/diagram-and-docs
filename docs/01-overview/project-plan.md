# 프로젝트 계획서

| 항목 | 값 |
|------|-----|
| 과목 | 컴퓨터공학부 소프트웨어공학 (01) — 3학년 1학기 |
| 팀 | 4조 |
| 학기 | 2026년 1학기 |
| 작성일 | 2026-05-19 |

---

## 1. 왜 FastAPI인가

- Python 생태계의 데이터 처리 라이브러리(numpy, pandas)를 UC18(이상 징후 탐지) 같은 분석성 잡에 그대로 활용할 수 있다.
- Pydantic v2 기반의 입력 검증과 OpenAPI 3.1 자동 문서화로 발표용 Swagger UI 데모가 즉시 가능하다.
- async 네이티브 구조로 I/O 바운드 작업(DB·Redis·HTTP)에 강하고, 학부 단일 노드 배포 규모에서 가볍게 기동된다.
- SQLAlchemy 2.0의 명시적 트랜잭션 경계(`async with session.begin():`)는 SE 과목의 트랜잭션 학습 취지와 잘 맞는다.

---

## 2. 기술 스택

각 스택의 **선정 이유**와 **제외된 후보**(RabbitMQ, Kafka, GraphQL 등)의 상세 근거는 [`tech-stack.md`](./tech-stack.md) 참조.

| 계층 | 선정 기술 | 버전 (계획) |
|------|----------|-------------|
| 프론트엔드 | React 18 + TypeScript 5 + Vite | Vite 5+ |
| UI 라이브러리 | shadcn/ui + TailwindCSS + Recharts | — |
| 백엔드 | FastAPI + Python 3.12 + Uvicorn (gunicorn 워커) | FastAPI 0.115+ / Python 3.12 |
| ORM | SQLAlchemy 2.0 (`Mapped[]` 타입 매핑) + Alembic | SQLA 2.0+ |
| 검증 | Pydantic v2 | 2.x |
| 인증 | fastapi-users 또는 python-jose + passlib | — |
| 스케줄러 | APScheduler (단일 프로세스) 또는 Celery beat + Celery worker (멀티) | APScheduler 3.x / Celery 5.x |
| 실시간 푸시 | FastAPI WebSocket (UC03-d 충돌 모달 등) + 필요 시 Redis Pub/Sub로 인스턴스 간 팬아웃 | — |
| RDBMS | PostgreSQL 16 | 16.x |
| 캐시 / Pub-Sub | Redis 7 + `redis.asyncio` | 7.x |
| 빌드/패키지 | uv (또는 Poetry) | uv 0.5+ |
| 컨테이너 | Docker Compose | — |
| CI/CD 파이프라인 (빌드·배포) | GitHub Actions | — |
| 테스트 | pytest + pytest-asyncio + Testcontainers-python | — |

메시지 큐(RabbitMQ/aio-pika)는 **도입하지 않는다**. 본 시스템의 "알림"은 외부 채널 전송이 아니라 앱 내부 `notifications` 테이블에 적재되는 인-앱 알림이고, 동일 트랜잭션 안에서 `INSERT`로 처리하면 일관성·재시도·DLQ가 모두 자연스럽게 해결된다. 실시간 푸시는 WebSocket/SSE, 인스턴스 간 팬아웃은 Redis Pub/Sub로 대체한다 (5.3절 참고).

### 2.1 스택 선정 근거

- **FastAPI**: async 네이티브 + Pydantic으로 입력 검증·OpenAPI 자동 문서화가 강점. 학부 데모에서 Swagger UI를 바로 보여줄 수 있어 발표에 유리.
- **SQLAlchemy 2.0**: 트랜잭션 경계가 코드에 그대로 드러나 트랜잭션 흐름을 가르치는 SE 과목 취지와 잘 맞는다.
- **APScheduler vs Celery**: 단일 프로세스 학기 데모는 APScheduler로 충분. 운영급 멀티 워커 필요 시 Celery로 교체.
- **메시지 큐 미도입**: 인-앱 알림은 DB INSERT로 충분하고, 실시간 푸시는 WebSocket이 더 직접적이다. 외부 채널(이메일/SMS/푸시)이 추가될 때 재검토.

### 2.2 인지하고 가야 할 트레이드오프

| 관점 | 영향 | 대응 |
|------|------|------|
| 트랜잭션 표현 | `@Transactional` 같은 선언적 단축 없음 | `async with session.begin():`를 코드 리뷰 체크리스트로 강제 |
| 의존성 주입 | FastAPI `Depends()`는 가벼우나 표현력은 Spring DI보다 제한적 | 서비스 계층을 명시적 함수/클래스로 분리해 보완 |
| 배치/스케줄러 | 프레임워크 내장 X (별도 프로세스로 기동) | `python -m app.scheduler.runner` 컨테이너 분리 |
| 타입 안정성 | 런타임 검증(Pydantic) 위주, 컴파일 타임 보장은 약함 | `mypy --strict`, CI에서 실패 처리 |
| CPU 바운드 부하 | GIL로 인해 멀티스레드 활용 제한 | UC18·UC19는 numpy/pandas의 C 구현으로 우회, 더 무거워지면 Celery로 분산 |
| 학습 자료 | FastAPI 한국어 자료는 Spring 대비 적음 | 공식 영문 문서 + Pydantic v2 마이그레이션 가이드를 표준 레퍼런스로 사용 |

---

## 3. 모듈 분리 (모노레포)

```
server-reservation/
├── app/
│   ├── api/                # FastAPI 라우터 (사용자 API)
│   │   ├── reservations.py
│   │   ├── approvals.py
│   │   ├── servers.py
│   │   └── ops_dashboard.py
│   ├── core/               # 도메인 모델, 정책
│   │   ├── models.py       # SQLAlchemy ORM 모델
│   │   ├── schemas.py      # Pydantic 스키마
│   │   └── services/       # 비즈니스 로직
│   ├── infra/              # DB·Redis 어댑터, WebSocket 매니저
│   ├── scheduler/          # APScheduler 잡 (UC14~UC20)
│   ├── deps.py             # FastAPI Depends
│   └── main.py             # 앱 진입점
├── alembic/                # 마이그레이션
└── tests/
```

`scheduler/`는 동일 코드베이스이지만 별도 프로세스로 기동 (`python -m app.scheduler.runner`).

---

## 4. UC ↔ 컴포넌트 매핑

| UC | 담당 컴포넌트 | 비고 |
|----|---------------|------|
| UC01, UC02 | `api.servers / api.reservations` 라우터 + Redis 캐시 | `fastapi-cache2` 이용 |
| UC03-a | `services.notification.create()` — 같은 트랜잭션에서 `Notification` 행 INSERT | 알림함 폴링/SSE로 클라이언트 표시 |
| UC03-d | `services.notification.create()` + WebSocket(`/ws/notifications`) 푸시 | 다중 인스턴스 시 Redis Pub/Sub 팬아웃 |
| UC04 ~ UC07 | `services.reservation` (SQLAlchemy `async session`) | 낙관적 잠금: `version_id_col` |
| UC09, UC10 | `services.approval`, `services.quota` | — |
| UC11 ~ UC13 | `services.server_admin` | — |
| UC14 | `scheduler.jobs.collect_metrics` (`@scheduler.scheduled_job('interval', minutes=1)`) | aiohttp으로 에이전트 폴링 |
| UC15 | `scheduler.jobs.idle_reclaim` | — |
| UC16 | `scheduler.jobs.expire_reservation` | — |
| UC17 | `scheduler.jobs.approval_timeout` | — |
| UC18 | `scheduler.jobs.anomaly_detect` | **numpy + pandas로 7일 이동 평균·표준편차 계산** |
| UC19 | `scheduler.jobs.health_scorer` | — |
| UC20 | `middleware.rate_limit` (Starlette Middleware) + Redis `INCR`/`PEXPIRE` | — |
| UC21 | `api.ops_dashboard` 라우터 + 집계 쿼리 | — |

---

## 5. 핵심 설계 결정

### 5.1 동시성 제어 (낙관적 잠금)

```python
class Server(Base):
    __tablename__ = "servers"
    __mapper_args__ = {"version_id_col": "version"}

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[ServerStatus] = mapped_column(Enum(ServerStatus))
    version: Mapped[int] = mapped_column(default=0)
    # ...
```

SQLAlchemy가 UPDATE 시 `WHERE id=? AND version=?` 절을 자동 추가. 영향 행이 0이면 `StaleDataError` 발생 → 컨트롤러에서 UC03-d 분기.

### 5.2 트랜잭션 경계 (명시적)

```python
async def reserve(session: AsyncSession, user_id: int, server_id: int, period: Period):
    async with session.begin():  # ← 트랜잭션 명시
        server = await session.get(Server, server_id, with_for_update=False)
        quota = (await session.execute(
            select(Quota).where(Quota.team_id == server.team_id)
        )).scalar_one()

        if not quota.has_room(period.days):
            req = ApprovalRequest(requester_id=user_id, ...)
            session.add(req)
            return ReservationResult.quota_exceeded(req)

        server.reserve()                  # status, version UPDATE 자동 발행
        reservation = Reservation(...)
        session.add(reservation)
        quota.used_days += period.days
        return ReservationResult.confirmed(reservation)
```

트랜잭션 경계가 코드에 그대로 드러나 트랜잭션 흐름을 학습용으로 보여주기 좋다.

### 5.3 알림 (UC03-a / UC03-d) — DB 기반 인-앱 알림

본 시스템의 알림은 외부 채널(이메일/SMS/푸시)이 아니라 **앱 내부 알림함에 적재되는 `notifications` 테이블의 행**이다. 따라서 별도 메시지 브로커 없이 동일 트랜잭션에서 INSERT 하나로 일관성을 보장한다.

```python
# 트랜잭션 내에서 Notification 행을 직접 INSERT
async with session.begin():
    reservation = Reservation(...)
    session.add(reservation)
    session.add(Notification(
        user_id=requester_id,
        kind="approval.approved",
        payload={"reservation_id": reservation.id, ...},
    ))
# 커밋되면 알림도 보이고, 롤백되면 알림도 함께 사라진다 → outbox 불필요
```

**실시간 푸시 (UC03-d 충돌 모달)**: FastAPI 네이티브 WebSocket으로 처리한다.

```python
@app.websocket("/ws/notifications")
async def notif_ws(ws: WebSocket, user: User = Depends(current_user_ws)):
    await ws.accept()
    async for msg in pubsub.listen(f"notif:{user.id}"):  # 단일 인스턴스면 in-memory 큐로 대체 가능
        await ws.send_json(msg)
```

**다중 인스턴스 팬아웃**: Redis Pub/Sub로 인스턴스 간 알림을 브로드캐스트. RabbitMQ 도입 없이 이미 스택에 있는 Redis로 해결한다.

### 5.4 Redis 활용

- 캐시: `cache:server:{id}`, `cache:reservation:list:{...}` 등 키 패턴으로 hot path 응답 캐싱 (`fastapi-cache2`).
- 분산 락: UC15 유휴 회수, UC16 만료 같은 스케줄러 잡의 단일 실행 보장(`SET key val NX PX ttl`).
- Pub/Sub: WebSocket 푸시(UC03-d)와 인스턴스 간 알림 팬아웃 채널.
- Rate Limit(UC20): `INCR` + `PEXPIRE`로 슬라이딩 카운터.

클라이언트는 `redis.asyncio`로 일원화.

### 5.5 PostgreSQL 단일 — 메트릭/시계열

`metrics_raw`는 `(server_id, ts)` PK + `ts` 기준 월 단위 파티셔닝, `metrics_5m` 사전 집계 테이블을 함께 둔다. **이상 징후 탐지는 Python의 강점을 활용**:

```python
# UC18 — pandas 윈도우 함수로 μ ± 2σ 계산
df = pd.read_sql(metrics_query, conn)
df["ma_7d"]  = df.groupby("server_id")["cpu"].transform(lambda s: s.rolling("7D").mean())
df["std_7d"] = df.groupby("server_id")["cpu"].transform(lambda s: s.rolling("7D").std())
df["is_anomaly"] = (df["cpu"] - df["ma_7d"]).abs() > 2 * df["std_7d"]
```

순수 SQL 윈도우 함수로도 가능하지만, pandas는 슬라이딩 윈도우·결측 보간·다중 지표 결합을 코드 몇 줄로 표현할 수 있어 학습 데모로도 적합하다.

### 5.6 인증 (JWT)

- `fastapi-users` 라이브러리로 회원/JWT 발급/로그아웃 일괄 처리.
- 또는 직접 구현: `python-jose` + `passlib[bcrypt]` 조합.

### 5.7 API 문서

FastAPI 기본 제공 `/docs` (Swagger UI) + `/redoc`. 별도 설정 없이 OpenAPI 3.1 스키마 자동 생성 → 발표 데모에 그대로 활용 가능.

---

## 6. 데이터 모델 / REST API

- REST API 경로·메서드·응답 스키마는 명세서(UC 표)에 정의된 그대로 유지하고, Pydantic v2 `BaseModel`로 요청/응답 스키마를 선언한다.
- ORM 모델은 SQLAlchemy 2.0 `Mapped[]` 타입 매핑으로 기술하며, 동시성이 걸리는 엔티티(Server, Reservation, Quota 등)는 `version_id_col`로 낙관적 잠금을 적용한다.
- 마이그레이션은 Alembic으로 관리하고, 모든 스키마 변경은 PR에 마이그레이션 파일이 함께 포함된다.
- OpenAPI 3.1 스키마는 `/openapi.json`에서 자동 생성되며, 프론트엔드 타입은 `openapi-typescript`로 빌드 시점에 동기화한다.

---

## 7. 개발/배포 환경

### 7.1 로컬

```yaml
services:
  postgres:   image: postgres:16
  redis:      image: redis:7
  api:        build: ./backend
              command: uvicorn app.main:app --host 0.0.0.0 --reload
  scheduler:  build: ./backend
              command: python -m app.scheduler.runner
  frontend:   build: ./frontend
```

### 7.2 패키지 관리

```bash
# uv 사용 (빠른 Python 패키지 매니저)
uv init
uv add fastapi uvicorn sqlalchemy alembic pydantic asyncpg redis apscheduler pandas numpy
uv add --dev pytest pytest-asyncio testcontainers httpx ruff mypy
```

### 7.3 CI/CD 파이프라인 (GitHub Actions — 빌드·배포)

- **CI (PR / push)**: `uv run pytest` (Testcontainers-python으로 실 PostgreSQL·Redis 기동) + `ruff check` + `mypy app/`.
- **빌드**: 프론트엔드(`vite build`)·백엔드(Docker 이미지 `backend`, `scheduler`)를 워크플로우에서 동시 빌드.
- **배포**: main 머지 시 GHCR로 이미지 푸시, 단일 노드 데모 서버에 `docker compose pull && up -d`.

---

## 8. 일정

학기 일정(약 14주)에 맞춘 마일스톤:

| 주차 | 마일스톤 |
|------|---------|
| 1~2 | 요구사항/UC 확정, 스택 셋업, Docker Compose 골격 |
| 3~5 | 인증·서버/예약 CRUD(UC01·UC02·UC04~UC07), 낙관적 잠금 |
| 6~7 | 승인/Quota(UC09·UC10), 알림(UC03-a/d) + WebSocket |
| 8~9 | 서버 관리(UC11~UC13), 운영 대시보드(UC21) |
| 10~11 | 스케줄러 잡(UC14~UC17) |
| 12 | 분석성 잡(UC18·UC19), Rate Limit(UC20) |
| 13 | 통합 테스트, 부하 테스트, 보안 점검 |
| 14 | 발표 데모 리허설, 문서화 마감 |

---

## 9. 한계 및 후속 결정 사항

- **CPU 바운드 작업의 GIL 영향**: UC18·UC19 같은 분석 작업이 무거워지면 Celery worker 다중 프로세스로 분산.
- **다중 인스턴스 분산 락**: APScheduler는 단일 노드 가정. 다중화 시 Celery beat + Redis lock 또는 별도 분산 스케줄러로 교체.
- **타입 안정성**: 런타임 타입 검증은 Pydantic이 해주지만 컴파일 타임 안정성은 약하므로 `mypy --strict`로 보완.
- **트랜잭션 경계 누락 방지**: 데코레이터 한 줄로 끝나는 모델이 아니므로 코드 리뷰 시 "트랜잭션 경계 명시" 체크리스트를 운영한다.
- **외부 채널 알림 추가 시**: 이메일/SMS/푸시가 요구되면 그때 RabbitMQ(또는 SQS/Kafka) + Outbox 패턴을 도입해 재시도·DLQ를 확보한다. 현 단계에선 도입하지 않는다.

---

## 10. 참고 자료

- 명세서: [`use-cases.md`](../02-requirements/use-cases.md)
- 기술 스택 상세(채택/제외 근거): [`tech-stack.md`](./tech-stack.md)
