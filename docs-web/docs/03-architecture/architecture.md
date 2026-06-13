# 시스템 아키텍처

서버 예약·할당 관리 시스템의 전체 구성, 데이터 흐름, 그리고 아키텍처 스타일 선정 근거를 정리한다. 다이어그램 원본(drawio)은 [`diagrams/architecture.drawio`](../../diagrams/architecture.drawio)에 있다.

## 1. 전체 구성

![시스템 아키텍처](../../assets/architecture-diagram.png)

| 컴포넌트 | 기술 | 책임 |
|---|---|---|
| Frontend SPA | React 18 + TypeScript + Vite (`:5173`) | 역할별(STU·MGR·ADM) 화면, REST 호출, WebSocket 알림 수신 |
| API 서버 | FastAPI (`:8000`) | 인증(JWT)·예약·승인·알림·Quota REST API, WebSocket 엔드포인트 |
| 스케줄러 | APScheduler (별도 컨테이너) | 메트릭 수집(UC14)·유휴 회수(UC15)·만료/사용시작 전이(UC16)·승인 타임아웃(UC17)·이상 탐지(UC18)·헬스 점수(UC19)·점검 전환·이상 상관·LLM 요약·용량 예측·장애 예측 등 11개 주기 잡(잡 등록은 `app/jobs/scheduling.py` 한 곳). 설계 주기는 1~60분이며 로컬 데모용으로 초 단위로 가속 |
| 메인 저장소 | PostgreSQL 16 (`:5432`) | 사용자·예약·서버·승인·메트릭·AIOps(인시던트·예측·요약·건강이력)·감사 로그 (17개 엔티티) |
| 캐시·메시징 | Redis 7 (`:6379`) | 캐시, 분산 락, Pub/Sub(실시간 알림), 로그인 실패 카운터 |
| 서버 풀 | server-pool 에이전트 N대 (`:9101~`) | `/health`·`/metrics` 노출 — 모니터링 대상 (별도 레포) |
| CI/CD | GitHub → GitHub Actions → Docker | PR 검증·이미지 빌드·배포 |

핵심 흐름:

- Frontend → HTTPS REST · WebSocket → FastAPI (예약·승인·서버 API)
- APScheduler → 서버 풀 에이전트로 HTTP PULL(1분 주기) → ServerMetric 저장 → 이상 탐지·자동 회수
- 상태 변화(예약 승인, 회수 등) → Redis Pub/Sub 발행 → WebSocket으로 사용자에게 실시간 푸시

## 2. 로컬 런타임

`docker compose up` 한 번으로 노트북 안에서 전체 스택이 기동되며, 외부 서버 풀(메트릭 수집 대상)과 HTTP로 통신한다.

![로컬 런타임](../../assets/runtime-diagram.png)

- 컨테이너 간 통신은 Docker 내부 네트워크, 외부 서버 풀(`:9101..9106`, 6대)로는 `host.docker.internal` 경유 HTTP
- API와 스케줄러는 같은 코드베이스의 두 entrypoint로, 컨테이너를 분리해 장애 격리

## 3. 아키텍처 스타일 선정과 사유

### 3.1 시스템 구성 스타일 — 저장소 모델 (Repository Model)

모든 서브시스템(API, 스케줄러, WebSocket 알림)이 PostgreSQL이라는 **중앙 공유 저장소**를 통해 데이터를 주고받는다.

- 예약·Quota·서버 상태처럼 여러 주체(사용자 요청, 스케줄러 잡)가 같은 데이터를 읽고 쓰는 구조이므로, 데이터를 한곳에 모으고 트랜잭션·낙관적 잠금으로 일관성을 지키는 저장소 모델이 적합하다.
- 서브시스템 간 직접 호출 대신 DB 상태를 매개로 협력하므로 결합도가 낮다. 스케줄러가 죽어도 API는 동작한다.

### 3.2 모듈 분해 스타일 — 객체지향 분해 + 3계층 레이어드

백엔드 내부는 `api(라우터) → services(도메인 로직) → models(ORM)` 3계층으로 분해하고, 횡단 관심사는 `core(deps·security·redis)`로 분리했다.

- 의존 방향이 위에서 아래로만 흐르며, 서비스 계층은 FastAPI를 모르므로 단위 테스트가 쉽다.
- 도메인(인증·예약·승인·Quota·알림)별로 서비스를 나눠 한 파일이 한 책임만 가진다. 상세는 [백엔드 설계](../04-design/backend-design.md) 참조.

### 3.3 제어 스타일 — 이벤트 기반 + 중앙 주기 제어 혼합

- **요청 처리**: 클라이언트-서버 — 사용자의 REST 요청이 트리거.
- **실시간 알림**: 이벤트 기반(브로드캐스트) — 상태 변화 시 Redis Pub/Sub 채널에 발행하고, 구독 중인 WebSocket 핸들러가 수신해 푸시한다. 발행자는 수신자를 모른다(Observer).
- **자동화 작업**: 중앙 집중 주기 제어 — APScheduler가 1분 주기로 잡(메트릭 수집, 만료 처리, 자동 거절)을 호출하는 호출-복귀 방식. 자동화 주체(SYS)의 동작을 한곳에서 관제할 수 있다.

### 3.4 분산 처리에 대한 결정

메트릭 수집은 에이전트가 밀어 넣는(push) 방식 대신 **백엔드가 끌어오는(pull) 방식**을 채택했다. 에이전트를 상태 없는(stateless) 경량 HTTP 서버로 유지할 수 있고, 수집 주기·대상 관리가 백엔드 한곳에 모여 운영이 단순해지기 때문이다. 메시지 브로커(RabbitMQ·Kafka)는 이 규모(서버 ~100대, 1분 주기)에서 과한 운영 비용이라 제외했다 — 근거는 [기술 스택](../01-overview/tech-stack.md) 참조.
