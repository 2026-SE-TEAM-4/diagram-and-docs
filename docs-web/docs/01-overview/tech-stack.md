# 기술 스택

**과목** 소프트웨어공학 (01) · **학기** 2026년 1학기 · **팀** 4조

---

## 개요

하나의 RDBMS, 두 개의 런타임.

Python 3.12 위의 FastAPI로 REST · WebSocket을, TypeScript 위의 React로 단일 SPA를.
모든 상태는 PostgreSQL 16에, 캐시·락·팬아웃·Rate Limit은 Redis 7에.
추측성 미래 요구로 스택을 늘리지 않는다.

---

## 00 — 시스템 토폴로지

### 구조

실선 = 단일 노드 데모 경계 / 점선 = 논리 그룹 / 굵은 검정 테두리 = 시스템의 핵심 컴포넌트.
학기 단일 노드 데모 구성을 기준으로 한다.

### 전체 흐름

좌→우 흐름: **Client**(브라우저) ↔ **Frontend SPA** ↔ **백엔드 서버**(API · Scheduler · DB · Cache) ↔ **서버 풀**(예약 가능한 서버들).

- ↔ 양방향(REST · WSS · 읽기/쓰기)
- ↓ 빌드 산출물 배포

### 로컬 개발 환경

위의 다이어그램은 **논리적 구조**를 보여준다. 실제 개발 단계에서는 위의 모든 컴포넌트가 **팀원 각자의 노트북 한 대** 안에서 함께 동작한다.
외부 클라우드 · 별도 서버 인프라 없이 로컬에서 끝까지 검증한다.

#### 실행 방법

| 구성 | 실행 명령 | 설명 |
|------|---------|------|
| **①Frontend SPA** | `npm run dev` | Vite 개발 서버가 `localhost:5173`에서 기동. 코드 수정 시 즉시 브라우저에 반영(HMR). |
| **②백엔드 서버** | `docker compose up -d` | FastAPI · Scheduler · PostgreSQL · Redis가 각각 Docker 컨테이너로 한 번에 기동. SPA에서는 `localhost:8000`으로 호출. |
| **③서버 풀** | 로컬 가상 서버 | 실제 외부 서버 대신 Docker 컨테이너(또는 가벼운 VM)로 노트북 안에서 모킹. 메트릭을 백엔드로 전송하는 더미 에이전트만 띄움. |

**요약** — 개발 / 데모는 노트북 한 대로 충분히 끝난다.
운영 배포가 필요해지면 같은 `docker compose` 파일을 클라우드 VM(예: AWS EC2 · Railway)에 그대로 올리는 방식으로 옮길 수 있다.

#### 노트북 런타임 상세

컨테이너 간 통신은 Docker 내부 네트워크로 격리된다.

- **Browser** — `localhost:5173`에서 Vite 개발 서버 + React SPA 실행
- **Docker 백엔드 컨테이너** — FastAPI (`:8000`), APScheduler, PostgreSQL (`:5432`), Redis (`:6379`)
- **Docker 가상 서버 풀** — 서버 1·2·3 및 metric agent (`:9101`, `:9102`, `:9103`)

개발자가 노트북에서 `npm run dev`로 프론트를, `docker compose up -d`로 백엔드 4개 컨테이너를, 그리고 가상 서버 풀 컨테이너를 함께 띄운다.
모든 통신은 `localhost` 안에서 일어나며, 외부 인프라가 필요 없다.

---

## 01 — 의사결정 원칙

스택을 추가할지 결정할 때 본 팀이 따른 우선순위. 새 라이브러리/인프라 도입 PR은 이 다섯 가지를 통과해야 한다.

### 원칙 1: 명세 요구사항을 정확히 충족하는가

추측성 미래 요구로 스택을 늘리지 않는다. 명세서 줄 번호로 정당화될 수 없는 도입은 보류.

### 원칙 2: 학기 단일 노드 데모 규모에서 운영 가능한가

운영급 분산 인프라(K8s, Kafka 등)는 학기 범위를 벗어남. Docker Compose 한 파일에 들어와야 한다.

### 원칙 3: 팀이 학습/리뷰 가능한가

1~2명만 이해하는 스택은 도입하지 않는다. 코드 리뷰가 형식적이 되는 영역을 만들지 않는다.

### 원칙 4: 명시성 > 마법

트랜잭션 · 이벤트 · 스케줄러는 코드에서 흐름이 드러나는 쪽을 선호. SE 과목 학습 취지에 부합.

### 원칙 5: 추가했을 때 빠질 수 있는가

한 번 도입하면 운영 부담이 학기 내내 누적되므로 "지금 필요해진 시점에" 추가한다.

---

## 02 — 프론트엔드

학생 · 팀 관리자 · 서버 관리자를 모두 받는 단일 SPA. 모바일 앱 없이 반응형 웹으로만 제공.

| ID | 기술 | 설명 | 태그 |
|---|---|---|---|
| F · 01 | **React** (v18) | 컴포넌트 단위로 UC별 화면(예약 폼, 알림함, 운영 대시보드)을 분리. 팀원 다수가 가장 익숙한 프론트 스택. | UI, SPA |
| F · 02 | **TypeScript** (v5) | 정적 타입 검사로 API 응답·도메인 모델을 코드 안에 명시. 팀 리뷰 시 의도 파악이 빠르고, 리팩터링 안전성이 올라간다. | Types, review |
| F · 03 | **Vite** (v5) | 개발 서버 + 번들러. HMR이 매우 빨라 데모 중 코드 수정 → 즉시 반영 흐름이 자연스럽다. | dev server |
| F · 04 | **TailwindCSS** | UC별 화면이 많은 본 시스템에서 공통 spacing · typography를 강제하기 좋다. 디자인 시스템 없이도 일관된 UI 유지. | utility CSS |
| F · 05 | **Recharts** | UC18(이상 징후) · UC19(헬스 점수) · UC21(운영 대시보드) 차트 렌더링. 학습 곡선이 완만하고 학부 데모에 충분. | 시각화 |

---

## 03 — 백엔드 코어

REST API + WebSocket을 한 프로세스에서 호스트. UC04~UC07의 동시성·트랜잭션 본체.

| ID | 기술 | 설명 | 태그 |
|---|---|---|---|
| B · 01 | **FastAPI** (0.115+) | async 네이티브 · Pydantic 통합 · OpenAPI 3.1 자동 생성 · WebSocket 기본 지원. 발표 데모에서 `/docs` 그대로 시연 가능. | core, async |
| B · 02 | **Python** (3.12) | 백엔드 단일 언어. 타입 힌트 · async/await native. | runtime |
| B · 03 | **Uvicorn + gunicorn** | ASGI 서버. 단일 노드에서 워커 수만 조정해 멀티프로세스 확장. | ASGI |
| B · 04 | **Pydantic** (v2) | Rust 기반 코어로 v1 대비 5~20배 검증 성능. "기간 ≤ 14일 / 사유 ≥ 20자" 같은 규칙을 선언적으로 표현. | validation |
| B · 05 | **SQLAlchemy** (2.0) | 명시적 트랜잭션 경계 · 낙관적 잠금(`version_id_col`) · `Mapped[T]` 타입 힌트. SE 학습 취지에 부합. | ORM, async |
| B · 06 | **asyncpg** (0.29+) | PostgreSQL async 드라이버. SQLAlchemy 2.0 async 엔진의 권장 드라이버. | db driver |
| B · 07 | **Alembic** | SQLA 팀이 직접 만든 마이그레이션 도구. 모델 변경 → 자동 후보 마이그레이션 생성. | migrations |
| B · 08 | **fastapi-users** (JWT) | 회원가입/로그인/리셋 라우터 일괄 제공. RBAC(STU/MGR/ADM) 분기는 직접 구현. | auth |
| B · 09 | **passlib + bcrypt** | 비밀번호 해싱. 직접 구현 경로 선택 시 python-jose + passlib 조합도 가능. | hashing |

---

## 04 — 데이터 계층

사용자 · 예약 · 서버 · 승인 · 할당 · 알림 · 메트릭 · 감사로그 전부 단일 RDBMS에 수용. Redis는 캐시·락·팬아웃·카운터 한 종으로.

| ID | 기술 | 설명 | 태그 |
|---|---|---|---|
| D · 01 | **PostgreSQL** (16) | 트랜잭션 · MVCC 안정성으로 UC04~UC07의 낙관적 잠금과 다중 행 일관성을 표준 SQL로 보장. `metrics_raw`는 `ts` 기준 월 단위 RANGE 파티셔닝. JSONB로 알림 payload · 감사 로그 등 가변 스키마를 별도 저장소 없이 흡수. | primary store, 파티셔닝, JSONB, 윈도우 함수 |
| D · 02 | **Redis** (7) | `redis.asyncio`로 접근. UC01·UC02 hot path 캐시(`fastapi-cache2`), 스케줄러 단일 실행 보장 분산 락(`SET NX PX`), UC03-d 실시간 팬아웃 Pub/Sub, UC20 슬라이딩 카운터(`INCR + PEXPIRE`). | cache, 분산 락, Pub/Sub, rate limit |

---

## 05 — 배치·스케줄러 / 실시간 푸시

주기 잡은 별도 컨테이너에서, 실시간 알림은 WebSocket + Redis Pub/Sub로.

| ID | 기술 | 설명 | 태그 |
|---|---|---|---|
| S · 01 | **APScheduler** (3.x) | in-process 스케줄러로 단일 노드 데모에 충분. `python -m app.scheduler.runner`로 별도 프로세스 기동 → API 요청 처리에 영향 없음. UC14~UC20의 메트릭 수집·유휴 회수·만료·승인 타임아웃·이상 탐지·헬스 점수·rate limit 정리를 담당. | cron · interval, → Celery 5.x 확장 경로 |
| S · 02 | **FastAPI WebSocket + Redis Pub/Sub** | UC03-d 충돌 모달 즉시 표시, UC03-a 결과 알림 푸시. FastAPI 네이티브 지원으로 추가 라이브러리 없이 `@app.websocket("/ws/notifications")` 한 줄로 시작. Pub/Sub로 다중 API 인스턴스 사이 팬아웃. | WebSocket, fan-out |

---

## 06 — 빌드 · 테스트 · 품질

| ID | 기술 | 설명 |
|---|---|---|
| Q · 01 | **uv** (0.5+) | 의존성 잠금 · 가상환경 · 스크립트 실행. Poetry 대비 수십 배 빠른 락 해결, Python 인터프리터 관리까지 일원화. |
| Q · 02 | **Docker Compose** | PostgreSQL · Redis · API · Scheduler · Frontend를 일괄 기동. 단일 노드 가정과 일치. |
| Q · 03 | **pytest + pytest-asyncio** | 단위 · 통합 테스트 러너. Python 표준 사실상 단일 후보. async 테스트 지원. |
| Q · 04 | **Testcontainers-python** | 테스트에서 실제 PostgreSQL · Redis 컨테이너 기동. UC04~UC07 트랜잭션 경계 테스트에 실 DB 필수. |
| Q · 05 | **httpx** | FastAPI 테스트 클라이언트, 외부 HTTP 호출. requests의 async 대응. |
| Q · 06 | **ruff · mypy** | **ruff** — flake8/black/isort/pyupgrade를 하나로. CI 시간 단축. **mypy** `--strict` — Pydantic이 런타임 검증, mypy가 흐름 타입 안정성. |

---

## 07 — CI/CD 파이프라인

PR/머지 시 자동 테스트 · 린트 · 타입체크 + main 머지 시 빌드 · 배포까지 한 파이프라인.

| ID | 단계 | 설명 |
|---|---|---|
| C · 01 | **CI 단계 — PR / push** | `uv run pytest` (Testcontainers-python) · `ruff check` · `mypy app/` · 프론트 `tsc --noEmit` · `vitest`. |
| C · 02 | **빌드 단계** | 프론트 `vite build` 결과물 + 백엔드 Docker 이미지(`backend` · `scheduler`)를 워크플로우에서 동시 빌드, GHCR(GitHub Container Registry)로 푸시. |
| C · 03 | **배포 단계** | main 머지 시 단일 노드 데모 서버에서 `docker compose pull && docker compose up -d`로 무중단 갱신. |

---

## 08 — 제외 · 도입 보류 스택

도입을 검토했지만 **명세 요구사항을 초과**하거나 **학기 범위에서 비용이 가치 초과**로 판단한 스택.
"지금 안 쓴다"는 결정이지 "영원히 안 쓴다"는 아니므로 재검토 트리거를 함께 기록한다.

### RabbitMQ + aio-pika

**제외 사유:**
- 본 시스템의 "알림"은 외부 채널이 아니라 **앱 내부 `notifications` 테이블에 적재되는 인-앱 알림**.
- 같은 트랜잭션 안에서 `session.add(Notification(...))` 한 줄이면 일관성 자연 성립 → Outbox 패턴조차 불필요.
- UC03-d 실시간 푸시는 메시지 큐가 아니라 **WebSocket**이 더 직접적이다.
- RabbitMQ 한 종 = 컨테이너 + 관리 UI + 큐 토폴로지 + 컨슈머 헬스. 단일 노드 데모에서 회수 가치 없음.

**재검토 트리거** — 외부 채널(이메일/SMS/푸시) 알림 요구 추가, 무거운 알림 작업(PDF 등) 분리 필요, 다수 외부 소비자 구독 요구 발생 시.

### Apache Kafka

**제외 사유:**
- RabbitMQ와 동일 사유 + 클러스터(ZooKeeper/KRaft) 운영 비용이 학기 범위를 크게 초과.

**재검토 트리거** — 이벤트 처리량이 초당 수만 건 규모거나 이벤트 소싱 전환 시. 현 명세는 분당 수회~수십회 수준이라 해당 없음.

### TimescaleDB / InfluxDB

**제외 사유:**
- PostgreSQL의 **파티셔닝 + BRIN 인덱스 + 사전 집계 테이블**(`metrics_5m`)로 학기 데모 데이터량(서버 ≤ 수십 대 × 분 단위)은 충분.
- 저장소 한 종 추가 = 백업/마이그레이션/접근 권한 라이프사이클 복제. 단일 RDBMS의 단순성이 학기 마지막 발표·인수인계에 유리.

**재검토 트리거** — 메트릭 보존 기간이 1년 이상으로 늘거나 다운샘플링 정책이 복잡해질 때.

### NoSQL (MongoDB · DynamoDB)

**제외 사유:**
- 핵심 데이터(예약 · 승인 · 할당)는 **강한 관계 · 트랜잭션 · 낙관적 잠금**이 필요. 가변 스키마 영역은 PostgreSQL JSONB로 충분.

**재검토 트리거** — 스키마가 자주 바뀌는 비정형 콘텐츠가 중심이 될 때.

### GraphQL

**제외 사유:**
- 클라이언트 단일(웹 SPA) → 멀티 클라이언트 호환 이점이 약함. REST + OpenAPI 자동 문서화로 발표 데모 가치가 더 크다. Pydantic ↔ GraphQL 스키마 이중 정의 부담.

**재검토 트리거** — 모바일 앱이 추가되어 화면별 over-fetching이 문제가 될 때.

### Spring Boot / JPA

**제외 사유:**
- 팀 내 Python 경험자 비율이 더 높고, JVM 기동 비용·메모리 부담이 단일 노드 데모에 무겁다.
- `@Transactional`의 간결함보다 SE 학습 취지에는 **명시적 트랜잭션 경계**의 가시성이 더 낫다고 판단.

**재검토 트리거** — 멀티 서비스/멀티 팀으로 확장, JVM 관측성 도구(Actuator 등)가 필요할 때.

### Kubernetes / Helm

**제외 사유:**
- 단일 노드 가정과 부합하지 않음. Docker Compose로 충분.

**재검토 트리거** — 무중단 배포 · 자동 스케일링이 요구사항으로 추가될 때.

### Sentry / Datadog 등 외부 SaaS 관측성

**제외 사유 (학기 중 보류):**
- 비용 · 계정 · 데이터 외부 전송 이슈. 학기 중에는 컨테이너 로그 + Prometheus(선택) + PostgreSQL 감사 로그 테이블로 충분.

**재검토 트리거** — 운영 환경 이관 시.

### ElasticSearch

**제외 사유:**
- 본 시스템에 전문 검색(서버 설명 검색 등) 요구가 약함. PostgreSQL `tsvector`로 필요 시 대응 가능.

**재검토 트리거** — UC21 운영 대시보드에서 로그/감사 검색 요구가 본격화될 때.

---

## 09 — 향후 도입 결정 시 체크리스트

새 라이브러리/인프라 추가 PR이 올라오면 리뷰어는 다음을 확인한다.

- 어떤 UC/명세 요구사항을 충족하기 위함인가? (명세 줄 번호 인용)
- 같은 기능을 **이미 채택된 스택**으로 구현할 수 있는가? (Redis / PostgreSQL / FastAPI로 대체 가능 여부)
- 추가 시 **운영 부담**(컨테이너 · 백업 · 모니터링 · 시크릿)이 무엇이며, 학기 범위에서 회수되는가?
- **제거 경로**가 있는가? (락인되는 의존성인지, 교체 가능한 어댑터로 격리 가능한지)
- 이 문서의 **제외 목록**에 이미 검토된 후보인가? 그렇다면 **재검토 트리거**가 충족되었는가?
