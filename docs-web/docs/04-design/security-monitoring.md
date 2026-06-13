# 보안 관제·경고 (Security Monitoring & Alerting)

> 작성 2026-06-13 · 신규 기능 설계
> 관련: [data-model.md](./data-model.md) · [ai-ops.md](./ai-ops.md) · [architecture.md](../03-architecture/architecture.md) · NFR-S4(감사성)

시스템 전반(인증·인가·관리자 작업·서버풀 수집)에서 발생하는 **보안 이벤트**를 기록하고,
주기 잡이 **위협 패턴을 탐지**해 **보안 경보**를 올리며, 시스템 관리자(ADM)에게 **알림 + 전용
대시보드**로 전달한다. 기존 AIOps(이상탐지 → 인시던트 → 알림) 구조를 그대로 본떠
용어·패턴을 일관되게 맞춘다.

용어: 보안 이벤트 = `SecurityEvent`, 보안 경보 = `SecurityAlert`, 위협 탐지 = detection.

---

## 1. 유스케이스 / 기능 / 화면 번호

| ID | 이름 | 행위자 | 설명 |
|----|------|--------|------|
| UC26 | 보안 이벤트 기록 | System | 인증 실패·권한 거부·관리자 민감 작업·에이전트 이상을 보안 이벤트로 적재 |
| UC27 | 보안 위협 탐지·경보 | System | 주기 탐지로 위협 패턴을 찾아 보안 경보 생성 + ADM 알림 |
| UC28 | 보안 경보 조회·해결 | Admin(ADM) | 보안 이벤트·경보 조회, 경보 수동 해결, 데모 시뮬레이션 |

| 기능 | 이름 |
|------|------|
| F36 | 보안 이벤트 기록 |
| F37 | 보안 위협 탐지·경보 |
| F38 | 보안 관제 화면(ADM 전용) |

화면: `A4 보안 관제`(서버 운영 그룹, ADM 전용, `/admin/security`).

> 실제 번호는 use-cases.md·features-and-apis.md의 마지막 번호를 확인해 빈 번호로 맞춘다(겹치면 +1).

---

## 2. 데이터 모델 (신규 테이블 2개)

기존 `IncidentSeverity`(INFO/WARNING/CRITICAL)·`IncidentStatus`(OPEN/RESOLVED)를 재사용한다.
신규 enum은 `app/models/enums.py`에 추가한다.

```
SecurityEventType: LOGIN_FAILURE | ACCOUNT_LOCKED | ACCESS_DENIED | ADMIN_ACTION | AGENT_UNREACHABLE
SecurityAlertType: BRUTE_FORCE | ACCESS_ABUSE | AGENT_DOWN | ADMIN_ABUSE
```

### SecurityEvent — 원시 보안 이벤트

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BigInteger PK | |
| `event_type` | String(30) | `SecurityEventType` 값 |
| `severity` | String(10) | `IncidentSeverity` 값(기본 INFO) |
| `actor_id` | BigInteger FK→user.id, **nullable** | 익명(미가입 이메일) 실패 허용 |
| `source_ip` | String(45), nullable | `request.client.host` |
| `identifier` | String(255), nullable | 시도된 이메일 등 |
| `target_type` | String(50), nullable | 대상 종류(server·user 등) |
| `target_id` | String(50), nullable | 대상 식별자 |
| `detail` | JSONB, nullable | 경로·사유 등 부가정보 |
| `occurred_at` | DateTime(tz) server_default now() | |

인덱스: `(event_type, occurred_at)`, `(source_ip)` — 탐지 잡의 윈도우 집계용.

### SecurityAlert — 탐지된 보안 경보(이벤트 묶음)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| `id` | BigInteger PK | |
| `alert_type` | String(20) | `SecurityAlertType` 값 |
| `severity` | String(10) | `IncidentSeverity` 값 |
| `status` | String(10) | `IncidentStatus` 값(기본 OPEN) |
| `subject` | String(255) | 경보 주체(IP·이메일·`server:{id}`·`user:{id}`) |
| `event_count` | Integer | 묶인 이벤트 수 |
| `message` | String(500) | 사람이 읽는 요약 |
| `started_at` | DateTime(tz) server_default now() | |
| `resolved_at` | DateTime(tz), nullable | |
| `resolved_by` | BigInteger FK→user.id, nullable | 해결한 ADM |

마이그레이션: `alembic/versions/0009_add_security_tables.py` (down_revision `0008`),
기존 마이그레이션과 같은 멱등 가드(`_has_table`/`_has_column`/`_has_index`) 패턴.

---

## 3. 이벤트 기록 지점

얇은 헬퍼 `services/security_event_service.py`의
`record_event(db, *, event_type, severity=INFO, actor_id=None, source_ip=None, identifier=None, target_type=None, target_id=None, detail=None)`
가 `SecurityEvent`를 `db.add` 한다(커밋은 호출부가 책임). 서비스는 FastAPI를 알지 않는다.

| 출처 | 위치 | 기록 |
|------|------|------|
| 로그인 실패 | `api/auth.py` 로그인 핸들러(`Request` 주입) | `InvalidCredentials`→`LOGIN_FAILURE`, `AccountLocked`→`ACCOUNT_LOCKED`. `source_ip`+`identifier`(이메일) 기록 후 커밋, 그다음 기존 HTTP 예외 변환 |
| 권한 거부(403) | `core/deps.py` `require_role` 체커(`Request`·`db` 주입) | `ACCESS_DENIED`(actor·경로). 기록·커밋 후 403 raise |
| 관리자 민감 작업 | `api/admin.py` reset 5종 + `api/users.py` 계정 잠금 해제 | `ADMIN_ACTION`(actor·작업명·대상) |
| 에이전트 이상 | `jobs/metric_collection_job.py` 수집 루프 | 서버 메트릭이 `MISSING`이면 해당 서버에 `AGENT_UNREACHABLE` 기록 |

> 인증 라우터의 IP는 라우터에서만 얻으므로 로그인 이벤트는 라우터에서 기록한다(서비스 계층은 무변경).

---

## 4. 탐지 잡 (F37 / UC27)

- 파일: `jobs/security_monitoring_job.py`. 등록 지점: `app/jobs/scheduling.py`(단일 출처), **5초** 주기(설계 5분).
- 순수 판정 로직은 `services/security_detection.py`에 분리(DB 없이 단위 테스트 가능).
- 윈도우·임계값은 모듈 상수(데모 가속·낮은 값):

| 경보 | 묶음 키 | 윈도우 | 임계 | 심각도 |
|------|---------|--------|------|--------|
| `BRUTE_FORCE` | source_ip 또는 identifier | 60초 | 실패+잠금 ≥ 5 | WARNING(잠금 포함 시 CRITICAL) |
| `ACCESS_ABUSE` | actor_id | 60초 | `ACCESS_DENIED` ≥ 5 | WARNING |
| `AGENT_DOWN` | `server:{id}` | 30초 | `AGENT_UNREACHABLE` ≥ 3 | CRITICAL |
| `ADMIN_ABUSE` | actor_id | 60초 | `ADMIN_ACTION` ≥ 5 | WARNING |

- 디바운스: 같은 `alert_type`+`subject`의 OPEN 경보가 이미 있으면 새로 만들지 않고 `event_count`만 갱신(알림 폭주 방지, anomaly 잡의 `_DEBOUNCE` 사상과 동일).
- 경보 생성 시: `SecurityAlert` 추가 → **전체 ADM**에게 `Notification(type="security_alert", message, payload={alertId, alertType, severity, subject})` 생성 → 각 ADM 채널로 `publish_notification(user_id, json)` 발행 → WebSocket 전달.
- 대시보드(F21) 실행 이력: `add_scheduler_log(db, "UC27", 이번_생성_경보수)`.

---

## 5. API (`api/security.py`, 전부 `require_role("ADM")`)

스키마는 `app/schemas/security.py`(기존 `schemas/ops.py`처럼 camelCase alias 노출). `main.py`에 라우터 등록.

| 메서드·경로 | 설명 |
|------|------|
| `GET /security/events` | 보안 이벤트 목록. 쿼리: `eventType`·`severity`·`from`·`to`·`limit`(기본 100). occurred_at 내림차순 |
| `GET /security/alerts` | 보안 경보 목록. 쿼리: `status`(OPEN/RESOLVED). started_at 내림차순 |
| `GET /security/summary` | KPI 집계: `todayEvents`·`openAlerts`·`criticalAlerts`·`bruteForceSuspects` |
| `PATCH /security/alerts/{id}/resolve` | 경보 해결. status=RESOLVED·resolved_at·resolved_by 설정. 없으면 404, 이미 해결이면 멱등 |
| `POST /security/simulate` | **데모용**. body `{scenario: "brute_force"\|"access_abuse"\|"agent_down"\|"admin_abuse"}` → 해당 임계를 넘기는 가짜 `SecurityEvent` 일괄 삽입(다음 탐지 주기에 경보 발생). 삽입 건수 반환 |

`api/admin.py` reset 서비스(`services/admin.py`)의 `reset_all`·신규 `reset_security`에 `SecurityAlert`·`SecurityEvent` 정리를 추가(FK 순서: SecurityAlert는 user 참조만, 이벤트와 독립이므로 둘 다 삭제 가능).

---

## 6. 프론트엔드 (A4 보안 관제, ADM 전용)

- 라우트 `/admin/security` → `features/admin/SecurityPage.tsx`. `App.tsx`의 ADM 가드 블록에 추가, `routes/nav.ts` "서버 운영" 그룹에 `{ to:"/admin/security", label:"보안 관제", icon:"🛡" }`(이모지 대신 기존 기하 문자 톤에 맞춰 `⛨` 등) 추가.
- `OpsDashboardPage` 패턴(useApi 폴링 + viz/ui 컴포넌트)을 따른다. 한 화면, 섹션 구성:
  - `TraceBar`(UC26~UC28·엔드포인트·엔티티) + `PageHead` + 새로고침
  - **KPI 스트립**(`KpiTile`): 오늘 이벤트 / 미해결 경보 / Critical / 브루트포스 의심 — `GET /security/summary`
  - **보안 경보 패널**(`Panel`): `SecurityAlert` 목록 + `StatusChip`(severity) + [해결] 버튼 + [공격 시뮬레이션] 버튼(`POST /security/simulate`) — `GET /security/alerts`
  - **보안 이벤트 테이블**(`Table`): 필터(eventType·severity), 컬럼 시각·유형·actor/식별자·IP·심각도 — `GET /security/events`
- 타입: `src/types/api.ts`에 `SecurityEvent`·`SecurityAlert`·`SecuritySummary` 추가.
- 경보는 기존 알림 채널로도 도착하므로 별도 WS 처리 불필요(알림 화면·종 배지에 자동 노출).

---

## 7. 데모 시드

`scripts/seed.py`에 샘플 `SecurityEvent` 몇 건(과거 로그인 실패·권한 거부)과 `SecurityAlert` 1건(RESOLVED 예시)을 추가해, 시드 직후에도 화면이 비어 보이지 않게 한다. 라이브 시연은 `POST /security/simulate`로 경보 발생을 재현한다.

---

## 8. 테스트

- **단위**: `tests/unit/test_security_detection.py`(윈도우·임계값 경계), `tests/unit/test_scheduling.py` 기대 잡 목록에 `security_monitoring` 추가.
- **통합**: 로그인 실패/403 시 `SecurityEvent` 적재, 탐지 잡이 `SecurityAlert`+`Notification` 생성, `resolve`·`simulate` 엔드포인트, `GET` 목록·요약 권한(ADM 전용 403 확인).

---

## 9. 비범위 (YAGNI)

에이전트 인증/TLS, 외부 SIEM 연동, IP 차단·방화벽 자동 조치, 로그 보존정책(데모는 admin reset으로 정리),
지리적 위치·위협 인텔리전스는 이번 범위에서 제외한다.
