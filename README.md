<div align="center">

# 서버 예약 / 할당 관리 시스템

연구실·팀 단위 GPU/서버 공유 시 중복·유휴를 막는 예약·할당·모니터링 플랫폼

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React_18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis_7-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)

</div>

---

## 프로젝트 개요

연구실이나 팀에서 GPU·서버 같은 공용 장비를 여러 명이 나눠 쓸 때 자주 생기는 충돌·유휴·블랙박스 문제를 해소하기 위한 예약·할당·모니터링 시스템입니다. 호텔 예약과 유사한 흐름으로, 학생/연구원은 서버를 예약하고 사용 후 반납하며, 팀 관리자는 Quota 한도를 관리하고, 서버 관리자는 인프라 전반을 운영합니다.

자동화 주체(`SYS`)가 1분 주기로 사용률을 수집하고, 유휴 자원을 자동 회수하며, 이상 징후를 탐지해 AIOps 관점에서 가용성을 예측적으로 관리합니다.

---

## 팀

| 항목 | 내용 |
|------|------|
| 과목 | 한국공학대학교 컴퓨터공학부 · 소프트웨어공학 (01) · 3학년 1학기 |
| 학기 | 2026년 1학기 |
| 팀 | 4조 |
| 팀원 | 김강문 (팀장) · 최민호 · 조동화 |

---

## 기술 스택

| Field | Technology of Use |
|-------|-------------------|
| Frontend | ![React](https://img.shields.io/badge/React_18-61DAFB?style=for-the-badge&logo=react&logoColor=black) ![TypeScript](https://img.shields.io/badge/TypeScript_5-3178C6?style=for-the-badge&logo=typescript&logoColor=white) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=white) ![TailwindCSS](https://img.shields.io/badge/TailwindCSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white) ![shadcn/ui](https://img.shields.io/badge/shadcn%2Fui-000000?style=for-the-badge&logo=shadcnui&logoColor=white) ![Recharts](https://img.shields.io/badge/Recharts-FF6B6B?style=for-the-badge) |
| Backend | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white) ![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=for-the-badge&logo=python&logoColor=white) ![Uvicorn](https://img.shields.io/badge/Uvicorn-499848?style=for-the-badge&logo=gunicorn&logoColor=white) ![Pydantic](https://img.shields.io/badge/Pydantic_v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white) ![Alembic](https://img.shields.io/badge/Alembic-6BA539?style=for-the-badge&logo=alembic&logoColor=white) |
| Database | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL_16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white) ![Redis](https://img.shields.io/badge/Redis_7-DC382D?style=for-the-badge&logo=redis&logoColor=white) ![asyncpg](https://img.shields.io/badge/asyncpg-336791?style=for-the-badge&logo=postgresql&logoColor=white) |
| Scheduler | ![APScheduler](https://img.shields.io/badge/APScheduler-3776AB?style=for-the-badge&logo=python&logoColor=white) ![pandas](https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white) ![numpy](https://img.shields.io/badge/numpy-013243?style=for-the-badge&logo=numpy&logoColor=white) |
| DevOps | ![Docker Compose](https://img.shields.io/badge/Docker_Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white) ![uv](https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=astral&logoColor=white) |
| Test | ![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white) ![Testcontainers](https://img.shields.io/badge/Testcontainers-1A7DBC?style=for-the-badge) ![ruff](https://img.shields.io/badge/ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=black) ![mypy](https://img.shields.io/badge/mypy-1F5082?style=for-the-badge) |
| ETC | ![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white) ![Notion](https://img.shields.io/badge/Notion-000000?style=for-the-badge&logo=notion&logoColor=white) ![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white) ![drawio](https://img.shields.io/badge/drawio-F08705?style=for-the-badge&logo=diagramsdotnet&logoColor=white) |

각 스택의 선정 이유와 제외된 후보(RabbitMQ, Kafka, GraphQL 등)는 [`docs/01-overview/tech-stack.md`](./docs/01-overview/tech-stack.md) 참조.

---

## 시스템 아키텍처

전체 컴포넌트 구성과 데이터 흐름. CI/CD 파이프라인(GitHub → GitHub Actions → Docker), Frontend SPA, Backend Server (API · Scheduler · DB · Cache), 공유 서버 풀로 구성됩니다.

![Architecture Diagram](./assets/architecture-diagram.png)

핵심 흐름:
- Frontend (React SPA) → HTTPS REST · WebSocket → FastAPI (예약·승인·서버 API)
- APScheduler (별도 컨테이너) → 메트릭 수집(UC14) · 유휴 회수(UC15) · 만료 반납(UC16) · 이상 탐지(UC18) · 헬스 점수(UC19)
- PostgreSQL = 메인 데이터 저장소 (사용자·예약·서버·승인·메트릭·감사 로그)
- Redis = 캐시 · 분산 락 · Pub/Sub · Rate limit 카운터

---

## 로컬 런타임 (개발자 노트북)

`docker compose up` 한 번으로 노트북 안에서 전체 스택이 기동되며, 외부 서버 풀(메트릭 수집 대상)과 HTTP로 통신합니다.

![Runtime Diagram](./assets/runtime-diagram.png)

- Vite Dev Server (`:5173`) — React SPA + HMR (`npm run dev`)
- FastAPI (`:8000`) — REST + WebSocket API
- APScheduler (별도 컨테이너) — 주기 잡 · 이상 탐지
- PostgreSQL (`:5432`) — 메인 데이터 저장소
- Redis (`:6379`) — 캐시 · 실시간 메시지
- 컨테이너 간 통신은 Docker 내부 네트워크로, 외부 서버 풀(`:9101`)로는 HTTP 메트릭 수집

---

## 저장소 구성

본 레포(docs-web)는 설계 산출물·명세서·다이어그램과 이를 보여주는 웹 뷰어를 담습니다. 시스템 구현은 `backend`·`frontend`·`server-pool`, 테스트 도구는 `test-tool`, 화면 시안은 `frontend-design` 레포에서 진행됩니다.

**문서의 단일 원본은 `docs/` 아래 마크다운 파일**이며, `index.html` 뷰어가 같은 md 파일을 fetch해 렌더링하므로 두 형태가 항상 동기화됩니다. 다이어그램 원본(drawio)은 `diagrams/`에 모입니다.

```
docs-web/
├── README.md                      # 본 파일
├── index.html                     # 문서 뷰어 (md를 불러와 렌더링 — 메인 진입점)
├── docs/
│   ├── 01-overview/               # 프로젝트 개요 · 계획서 · 기술 스택
│   ├── 02-requirements/           # 유스케이스(23) · 기능(30)·API(22) · NFR
│   ├── 03-architecture/           # 시스템 아키텍처 · 서버 풀 명세
│   ├── 04-design/                 # 데이터 모델(ERD) · 동적 모델 · 백엔드 설계(SOLID·패턴) · AIOps
│   └── 05-testing/                # 테스트 계획서
├── diagrams/                      # drawio 원본 — 아키텍처·ERD·클래스·상태·시퀀스·유스케이스
│   └── README.md                  # 다이어그램 안내 (파일별 내용·관련 문서)
├── assets/                        # 뷰어(style.css·app.js·manifest.js) + 내보낸 PNG
└── team-4-agile.xlsx              # Agile 스토리보드 (스프린트·백로그)
```

### 문서 보는 법

뷰어는 fetch로 md를 읽으므로 정적 서버가 필요합니다:

```bash
cd diagram-and-docs
python3 -m http.server 8080
# http://localhost:8080 접속
```

md 파일을 직접 읽어도 무방합니다(GitHub에서도 그대로 렌더링됨). 새 문서를 추가할 때는 `docs/<카테고리>/`에 md를 만들고 `assets/manifest.js`에 한 줄 등록하면 뷰어에 나타납니다.

관련 레포:
- `backend` — FastAPI 서버 + APScheduler (Python)
- `frontend` — React SPA (TypeScript)
- `server-pool` — 모니터링 대상 서버 풀 시뮬레이터 (경량 에이전트 · /health·/metrics)
- `test-tool` — testkit CLI(부하·중단점·장애 주입) 구현 + 툴 설계 문서
- `frontend-design` — 역할별 화면 시안(KKM) + 정보구조(IA) 다이어그램

---

## 주요 문서

| 문서 | 내용 |
|------|------|
| [`index.html`](./index.html) | 문서 뷰어 — 사이드바 색인 + md 렌더링 (메인 진입점) |
| [`docs/01-overview/project-overview.md`](./docs/01-overview/project-overview.md) | 프로젝트 개요 — 문제 정의, 역할 3종+SYS, 관련 레포 |
| [`docs/01-overview/project-plan.md`](./docs/01-overview/project-plan.md) | 프로젝트 계획서 — 모듈 분리·UC↔컴포넌트 매핑·설계 결정·일정 |
| [`docs/01-overview/tech-stack.md`](./docs/01-overview/tech-stack.md) | 기술 스택 — 채택 이유 + 제외 후보(RabbitMQ·Kafka·GraphQL 등) 검토 |
| [`docs/02-requirements/use-cases.md`](./docs/02-requirements/use-cases.md) | UC 23개 풀 명세 + 부록 — 인증·계정(UC22·UC23) 포함 |
| [`docs/02-requirements/features-and-apis.md`](./docs/02-requirements/features-and-apis.md) | 기능(30)·API(22) 명세 + 추적 매핑 |
| [`docs/02-requirements/nfr.md`](./docs/02-requirements/nfr.md) | 비기능 요구사항 — 측정 가능 수치 + 검증 방법 |
| [`docs/03-architecture/architecture.md`](./docs/03-architecture/architecture.md) | 시스템 아키텍처 — 구성·데이터 흐름·아키텍처 스타일 선정 사유 |
| [`docs/03-architecture/serverpool-spec.md`](./docs/03-architecture/serverpool-spec.md) | 서버 풀 기능·API 명세 (/health·/metrics 계약) |
| [`docs/04-design/data-model.md`](./docs/04-design/data-model.md) | 데이터 모델 — ERD 13개 엔티티 |
| [`docs/04-design/dynamic-models.md`](./docs/04-design/dynamic-models.md) | 동적 모델 — 상태도·시퀀스·ADR |
| [`docs/04-design/backend-design.md`](./docs/04-design/backend-design.md) | 백엔드 상세설계 — 레이어·클래스 관계·SOLID·디자인 패턴·핵심 알고리즘 |
| [`docs/04-design/ai-ops.md`](./docs/04-design/ai-ops.md) | AIOps 기능 설계 — 용량 예측·장애 예측·이상 상관·LLM 설명 (F31~F34) |
| [`docs/05-testing/test-plan.md`](./docs/05-testing/test-plan.md) | 테스트 계획서 — 성능 5종, 보안·복원·회귀, 정적/동적, V 모델·커버리지 (도구는 `test-tool` 레포) |
| [`diagrams/`](./diagrams/README.md) | drawio 원본 — 아키텍처·ERD·클래스·상태·시퀀스·유스케이스 |
| [`team-4-agile.xlsx`](./team-4-agile.xlsx) | Agile 스토리보드 (스프린트·백로그) |

---

## 빠른 시작 (예정)

```bash
# backend (FastAPI + APScheduler)
cd backend
uv sync
docker compose up -d
docker compose exec api alembic upgrade head

# frontend (React SPA, HMR)
cd frontend
npm install
npm run dev
```

---

<div align="center">

한국공학대학교 컴퓨터공학부 · 소프트웨어공학 (01) · 4조 · 2026 1학기

</div>
