# 기능·API 명세

> 작성 2026-05-29 · 최신화 2026-06-12(백엔드 전 기능 F01~F34 구현 완료 반영)
> 도출 근거: `use-case-spec.html`(UC01~UC21, 부록 A·B), `시스템 설계` 페이지(배치·아키텍처).
> 데이터 모델은 [`../04-design/data-model.md`](../04-design/data-model.md) 참조.

## 설계 결정 요약 (합의됨)

- 기능 명세 / API 명세는 **별도 DB 2개 + relation 유지** (다대다·추적성).
- 기능 = **구현 단위(백엔드 서비스 메서드)**, **연산 단위 입도** (예: `예약 생성`·`예약 취소` 각각 하나).
- 도출 순서 **UC → ERD → 기능 → API**. API의 Request/Response는 ERD 엔티티를 참조한다.
- ERD는 **논리 수준**(엔티티 + 속성·타입 + 관계), SSOT는 **노션 "데이터 모델" 페이지**(mermaid erDiagram).
- 스케줄러 기능(UC14~UC19)·미들웨어 기능(UC20)은 **클라이언트 REST 엔드포인트가 없음** → "API 없는 기능"으로 기능 ≠ API 가 증명됨.

상태 의미: 기능 `미정의→정의완료(역할·입출력 합의+관련 API 연결)→구현완료(머지+테스트)` / API `미정의→정의완료(메서드·경로·Req/Res·에러 확정)→구현완료(라우터 구현+동작)`.

---

## 1. 기능 카탈로그 (연산 단위, 34개)

> 담당자는 팀 배정 전이라 (미정). 우선순위는 UC 명세 그대로.

| # | 기능 이름 | 도메인 | 관련 UC | 우선순위 | 관련 API | 비고 |
|---|---|---|---|---|---|---|
| F01 | 서버 현황 조회 | 조회 | UC01 | 중간 | GET /servers | 권한별 범위·필터·정렬·1분 새로고침 |
| F02 | 서버 상세 조회 | 조회 | UC01 | 낮음 | GET /servers/{id} | 단건 상세 |
| F03 | 예약 현황 조회 | 조회 | UC02 | 중간 | GET /reservations | 권한별 범위·상태/기간 필터 |
| F04 | 서버 예약 요청(예약형) | 예약·할당 | UC04 | 높음 | POST /reservations | 낙관적 잠금, Quota 검사 |
| F05 | 즉시 서버 요청 | 예약·할당 | UC05 | 중간 | POST /reservations/instant | 조건 매칭 1대 즉시 IN_USE, 없으면 대기열 |
| F06 | 예약 취소 | 예약·할당 | UC06 | 중간 | POST /reservations/{id}/cancel | RESERVED 한정, Quota 회복 |
| F07 | 서버 반납 | 예약·할당 | UC07 | 중간 | POST /reservations/{id}/return | IN_USE 한정, 조기 반납 |
| F08 | 대안 서버 조회 | 예약·할당 | UC03-d | 높음 | GET /servers/alternatives | 충돌 시 유사 사양 최대 5건 |
| F09 | Quota 초과 승인 요청 생성 | 승인·Quota | UC08(UC04/05 확장) | 높음 | POST /approval-requests | PENDING 생성 |
| F10 | 허가함 목록 조회 | 승인·Quota | UC09 | 높음 | GET /approval-requests | MGR 결재 대기 목록 |
| F11 | 초과 요청 승인/거절 | 승인·Quota | UC09 | 높음 | POST /approval-requests/{id}/decision | 부분 승인·대리 허가 |
| F12 | 팀원별 Quota 조회 | 승인·Quota | UC10 | 중간 | GET /teams/{id}/quotas | 한도·사용량 |
| F13 | 팀원별 Quota 설정 | 승인·Quota | UC10 | 중간 | PATCH /quotas/{id} | 합계 검증, 낙관적 잠금 |
| F14 | 서버 등록 | 서버관리 | UC11 | 중간 | POST /servers | 검증, version=1 |
| F15 | 서버 삭제 | 서버관리 | UC12 | 낮음 | DELETE /servers/{id} | soft delete, 활성예약 차단 |
| F16 | 점검 스케줄 등록 | 서버관리 | UC13 | 중간 | POST /servers/{id}/maintenances | 충돌 검사·반복·강제 |
| F17 | 알림 목록 조회 | 알림 | UC03-a | 높음 | GET /notifications | 알림함 |
| F18 | 알림 읽음 처리 | 알림 | UC03-a | 중간 | PATCH /notifications/{id}/read | readAt 기록 |
| F19 | 실시간 알림 채널 | 알림 | UC03-a, UC03-d | 높음 | WS /ws/notifications | 배지·충돌 모달 푸시 |
| F20 | 계정 잠금 해제(수동) | 보안·운영 | UC20 | 중간 | POST /admin/users/{id}/unlock | ADM 오탐 해제 |
| F21 | 운영 대시보드 조회 | 보안·운영 | UC21 | 중간 | GET /ops/dashboard | 5개 섹션 집계 |
| F22 | 가용성 현황 조회 | 보안·운영 | UC21 | 중간 | GET /ops/availability | 업타임·MTBF·MTTR·A% |
| F23 | 실시간 사용률 수집 | 모니터링·자동화 | UC14 | 중간 | — (스케줄러 1분) | 서버풀 /metrics PULL |
| F24 | 유휴 서버 감지·자동 회수 | 모니터링·자동화 | UC15 | 높음 | — (스케줄러 1분) | 경고 후 15분 회수 |
| F25 | 예약 만료 자동 반납·사용 시작 전환 | 모니터링·자동화 | UC16 | 높음 | — (스케줄러 1분) | 만료 예약 EXPIRED + startTime 도달 시 RESERVED→IN_USE(ADR-05) |
| F26 | 승인 타임아웃 자동 거절 | 모니터링·자동화 | UC17 | 중간 | — (스케줄러) | 72h PENDING→AUTO_REJECTED |
| F27 | 서버 이상 징후 탐지 | 모니터링·자동화 | UC18 | 높음 | — (스케줄러 5분) | μ±2σ, AnomalyRecord |
| F28 | 서버 건강 점수 산출 | 모니터링·자동화 | UC19 | 중간 | — (스케줄러 10분) | 가중 평균 healthScore |
| F29 | 비정상 접근 감지·일시 잠금 | 보안·운영 | UC20 | 높음 | — (미들웨어) | Rate limit, 15분 잠금 |
| F30 | 점검 스케줄 자동 상태 전환 | 모니터링·자동화 | UC13 | 중간 | — (스케줄러) | 시작/종료 시 MAINTENANCE↔AVAILABLE |
| F31 | 용량·수요 예측 | 모니터링·자동화 | UC22 | 중간 | GET /ops/forecast | Holt-Winters(statsmodels), Forecast 적재, 포화 임박 시 CAPACITY 알림 |
| F32 | 장애·건강 열화 예측 | 모니터링·자동화 | UC23 | 중간 | GET /servers/{id}/health-trend | EWMA 추세+위험도(riskScore/etaToRisk), 임계 초과 시 PREDICTIVE_FAILURE 알림 |
| F33 | 이상 상관·노이즈 감소 | 모니터링·자동화 | UC24 | 높음 | GET /ops/incidents, GET /ops/incidents/{id} | 시간·서버그룹 클러스터링→Incident, 노이즈 감소율, INCIDENT 알림 |
| F34 | LLM 원인 설명·요약 | 모니터링·자동화 | UC25 | 중간 | GET /ops/incidents/{id}/summary | Gemini API, 인시던트당 1회 IncidentSummary 캐시 |
| F35 | 운영 데이터 초기화(고급) | 보안·운영 | — | 낮음 | POST /admin/reset/* | ADM 전용, 데모·테스트용 5종 초기화 엔드포인트 |

스케줄러/미들웨어 기능(F23~F30): 클라이언트 호출 API 없음. 단, 동작 결과는 `SchedulerLog`에 기록되어 F21 대시보드(GET /ops/dashboard)에서 노출됨. AIOps 기능(F31~F34)은 스케줄러 잡이며 조회 API가 별도로 있다(GET /ops/forecast, GET /servers/{id}/health-trend, GET /ops/incidents, GET /ops/incidents/{id}, GET /ops/incidents/{id}/summary).

---

## 1.1 구현 현황 (2026-06-12 기준)

**구현완료: F01~F35 — 미구현 없음.**
- 인증(회원가입·로그인·내 정보)을 포함해 기능 카탈로그 35건 전부 머지+테스트 완료.
- F35(운영 데이터 초기화): 2026-06-13 추가. ADM 전용 고급 화면(`/admin/advanced`)과 5종 초기화 REST 엔드포인트(`POST /admin/reset/*`).
- 조회·예약·승인·서버관리·알림·보안운영 REST 기능과 스케줄러/미들웨어 잡(F23~F30), AIOps 기능(F31~F34)이 모두 동작한다.

**구현 시 명세와 달라진 점(정확히 반영)**:
- F20(계정 잠금 해제)은 명세의 `POST /admin/users/{id}/unlock`가 아니라 **`POST /users/{id}/unlock`**로 구현됨.
- 신규 **`GET /teams`**(비인증, 회원가입 시 팀 선택용) 추가됨 — 기존 카탈로그에 없던 항목. 아울러 Quota 목록 응답에 `userName`·`version` 필드가 추가됨.
- F21·F22 가용성(MTBF/MTTR/업타임)은 서버 상태 표본을 기반으로 산출되며, 대시보드 스케줄러 섹션은 이제 `SchedulerLog` 실데이터로 채워진다(모든 스케줄러 잡이 실행 시 `SchedulerLog`에 기록).

모든 AIOps 잡은 스케줄러 컨테이너(app/scheduler.py)가 단독 등록·실행하며(app/jobs/scheduling.py), API 프로세스는 잡을 돌리지 않는다(이중 실행 방지).

---

## 2. API 카탈로그 (32개 엔드포인트)

> 모든 엔드포인트는 인증 필요(미인증 401). 권한 불일치 403. 잠금 상태 사용자 429(UC20).
> Request/Response는 핵심 필드만. path/query 파라미터는 Request에 표기.

### 조회

**GET /servers** · 통신 REST · 권한 STU/MGR/ADM · 기능 F01
```jsonc
// Request (query)
{ "status": "AVAILABLE", "group": "Lab-A GPU", "sort": "name", "order": "asc" }
// Response 200
{ "servers": [ { "id": 1, "name": "gpu-01", "status": "AVAILABLE",
  "spec": {"cpuCores":16,"ramGb":64,"gpuModel":"RTX4090"},
  "healthScore": 82, "occupant": "팀코드 또는 실명(권한별)" } ] }
```
에러: 401, 403, 404(표시할 서버 없음 UC01-E1), 500

**GET /servers/{id}** · REST · STU/MGR/ADM · F02 — 단건 상세. 에러 401,403,404,500

**GET /reservations** · REST · STU(본인)/MGR(팀)/ADM(전체) · F03
```jsonc
// Request (query): { "scope":"mine", "status":"active", "from":"...", "to":"..." }
// Response 200: { "reservations":[ {"id":10,"serverId":1,"serverName":"gpu-01",
//   "startTime":"...","endTime":"...","status":"RESERVED"} ] }
```
에러: 401, 403(타인 예약 조회 UC02-E1), 500

**GET /servers/alternatives** · REST · STU · F08
```jsonc
// Request (query): { "serverId": 1 }
// Response 200: { "alternatives": [ {"id":2,"name":"gpu-02","spec":{...}} ] }  // 최대 5
```
에러: 401, 500

### 예약·할당

**POST /reservations** · REST · STU · F04
```jsonc
// Request: { "serverId": 1, "startTime": "2026-06-01T09:00", "endTime": "2026-06-03T09:00", "version": 42 }
// Response 201: { "reservationId": 10, "status": "RESERVED", "server": {...} }
```
에러: 400, 401, 403, 409(낙관적 잠금 충돌 UC04-E1 → UC03-d), 422(Quota 초과 → 승인 분기 UC04-A1), 500

**POST /reservations/instant** · REST · STU · F05
```jsonc
// Request: { "spec": {"minRamGb":32,"gpuRequired":true} }
// Response 201: { "reservationId": 11, "status": "IN_USE", "server": {"ip":"10.0.0.5",...} }
// Response 202(대기열): { "queued": true, "position": 3 }
```
에러: 400, 401, 409, 422(Quota 초과), 500

**POST /reservations/{id}/cancel** · REST · STU(소유자) · F06 — 에러 401,403(타인 UC06-E2),404,409(상태/충돌 UC06-E1·E3),500

**POST /reservations/{id}/return** · REST · STU(소유자) · F07 — 에러 401,403(타인 UC07-E2),404,409(이미 종료/회수 경합 UC07-E1·E3),500

### 승인·Quota

**POST /approval-requests** · REST · STU · F09
```jsonc
// Request: { "serverId":1, "startTime":"...", "endTime":"...", "reason":"논문 실험" }
// Response 201: { "approvalRequestId": 5, "status": "PENDING" }
```
에러: 400, 401, 409, 500

**GET /approval-requests** · REST · MGR/ADM · F10
```jsonc
// Request (query): { "status": "PENDING" }
// Response 200: { "requests":[ {"id":5,"requester":"홍길동","serverName":"gpu-01",
//   "period":"...","reason":"...","teamUsage":"7/10","requestedAt":"..."} ] }
```
에러: 401, 403, 500

**POST /approval-requests/{id}/decision** · REST · MGR/ADM(대리) · F11
```jsonc
// Request: { "decision": "APPROVE", "shortenedEnd": "2026-06-02T09:00" }   // 부분 승인 옵션
//      또는 { "decision": "REJECT", "reason": "한도 초과" }                  // 거절 사유 필수
// Response 200: { "id":5, "status":"APPROVED", "reservationId": 12, "decidedAt":"...", "decidedBy": 3 }
```
에러: 400, 401, 403(타팀 UC09-E3), 404, 409(타임아웃 경합 UC09-E2 / 서버 점유 UC09-E1), 500

**GET /teams/{id}/quotas** · REST · MGR/ADM · F12
```jsonc
// Response 200: { "members":[ {"userId":4,"name":"홍길동","limit":3,"used":1} ], "teamLimit":10 }
```
에러: 401, 403, 404, 500

**PATCH /quotas/{id}** · REST · MGR/ADM · F13
```jsonc
// Request: { "limit": 5, "version": 7 }
// Response 200: { "id":2, "limit":5, "used":1, "version":8 }
```
에러: 400(합계 초과 UC10-E1 / 사용량 미만 UC10-E2), 401, 403, 409(동시 수정 UC10-E3), 500

### 서버관리

**POST /servers** · REST · ADM · F14
```jsonc
// Request: { "name":"gpu-03", "ip":"10.0.0.7", "cpuCores":16, "ramGb":64,
//   "gpuModel":"RTX4090", "group":"Lab-A GPU", "startInMaintenance": false }
// Response 201: { "id":3, "status":"AVAILABLE", "version":1 }
```
에러: 400, 401, 403, 409(IP 중복), 422(필수 누락 UC11-E1), 500

**DELETE /servers/{id}** · REST · ADM · F15 — soft delete(deletedAt). 에러 401,403,404,409(활성 예약 UC12-E1),500

**POST /servers/{id}/maintenances** · REST · ADM · F16
```jsonc
// Request: { "startAt":"...", "endAt":"...", "reason":"디스크 교체",
//   "recurringRule": null, "force": false }
// Response 201: { "maintenanceId": 8 }
```
에러: 400(잘못된 기간 UC13-E3), 401, 403, 404, 409(예약 충돌 UC13-E1·E2 / 중복 UC13-E4), 500

### 알림

**GET /notifications** · REST · 인증 사용자 · F17 — 에러 401,500
**PATCH /notifications/{id}/read** · REST · 소유자 · F18 — 에러 401,403,404,500
**WS /ws/notifications** · WebSocket · 인증 사용자 · F19, F08 — 알림 배지·예약 충돌 모달(UC03-d) 실시간 푸시. 에러 401

### 보안·운영

**PATCH /users/{id}/unlock** · REST · ADM · F20 — 잠금 해제(오탐). 에러 401,403,404,500

> 구현은 `/users/{id}/unlock` (명세의 `/admin/users/{id}/unlock`와 경로 다름 — 1.1 구현 현황 참조)

**GET /ops/dashboard** · REST · ADM · F21
```jsonc
// Response 200: { "scheduler":[{"ucId":"UC15","lastRun":"...","success":true,"processed":3}],
//   "metrics":{"successRate":0.98,"missing":["gpu-09"]},
//   "autoActions":{"reclaimed":2,"expired":5,"autoRejected":1},
//   "health":{"정상":12,"주의":3,"위험":1} }
```
에러: 401, 403(STU/MGR UC21-E2), 500

**GET /ops/availability** · REST · ADM · F22
```jsonc
// Response 200: { "servers":[{"id":1,"uptime":99.2,"mtbf":120.5,"mttr":0.8,"riskBadge":false}],
//   "systemAvailability": 99.1 }
```
에러: 401, 403, 500 (데이터 부족 시 N/A UC21-E3)

### AIOps(모니터링·예측)

**GET /ops/incidents** · REST · MGR/ADM · F33
```jsonc
// Request (query): { "status": "OPEN", "severity": "HIGH" }
// Response 200:
{ "noiseReductionRate": 0.63,
  "incidents": [
    { "id": 7, "severity": "HIGH", "status": "OPEN",
      "anomalyCount": 5, "serverIds": [1, 3],
      "startedAt": "2026-06-12T10:00:00Z", "resolvedAt": null }
  ] }
```
에러: 401, 403, 500

**GET /ops/incidents/{id}** · REST · MGR/ADM · F33
```jsonc
// Response 200:
{ "id": 7, "severity": "HIGH", "status": "OPEN",
  "serverIds": [1, 3], "startedAt": "2026-06-12T10:00:00Z", "resolvedAt": null,
  "anomalies": [
    { "id": 42, "serverId": 1, "metric": "cpu", "detectedAt": "2026-06-12T10:00:00Z",
      "zScore": 3.1, "value": 97.2 }
  ] }
```
에러: 401, 403, 404, 500

**GET /ops/incidents/{id}/summary** · REST · MGR/ADM · F34
```jsonc
// Response 200:
{ "incidentId": 7, "generatedAt": "2026-06-12T10:05:00Z", "model": "gemini-3.1-flash-lite",
  "situation": "gpu-01·gpu-03 CPU 동시 급등, 10분간 지속",
  "rootCauses": [
    { "cause": "분산 학습 작업 자원 경쟁", "evidence": "두 서버 동일 시각 cpu>95%" }
  ],
  "recommendations": [
    { "action": "작업 스케줄 분산", "rationale": "동일 시간대 GPU 작업 집중 완화" }
  ] }
```
에러: 401, 403, 404(요약 미생성), 500

**GET /ops/forecast** · REST · MGR/ADM · F31
```jsonc
// Request (query): { "serverId": 1, "metric": "cpu", "days": 7 }   // metric 필수
// Response 200:
{ "serverId": 1, "metric": "cpu", "generatedAt": "2026-06-12T06:00:00Z",
  "saturationAt": "2026-06-19T14:00:00Z", "confidence": 0.82,
  "horizon": [
    { "ts": "2026-06-13T00:00:00Z", "yhat": 72.5, "lower": 65.0, "upper": 80.0 }
  ] }
```
에러: 401, 403, 404(데이터 부족), 500

**GET /servers/{id}/health-trend** · REST · MGR/ADM · F32
```jsonc
// Response 200:
{ "serverId": 1, "healthScore": 68, "riskScore": 0.74,
  "trend": "DEGRADING",
  "etaToRisk": "2026-06-15T08:00:00Z",
  "history": [
    { "ts": "2026-06-12T00:00:00Z", "healthScore": 75 },
    { "ts": "2026-06-12T10:00:00Z", "healthScore": 68 }
  ],
  "drivers": ["cpu 지속 상승", "메모리 사용률 증가"] }
```
에러: 401, 403, 404, 500

### 고급 관리 (ADM 전용)

**POST /admin/reset/availability** · REST · ADM · F35
```jsonc
// Response 200: { "deleted": 1240, "message": "가용성 히스토리 1240건 삭제됨" }
```
ServerMetric·ServerHealthHistory 전체 삭제. 에러 401, 403, 500

**POST /admin/reset/aiops** · REST · ADM · F35
```jsonc
// Response 200: { "deleted": 87, "message": "AIOps 데이터 87건 삭제됨" }
```
IncidentSummary·AnomalyRecord·Incident·Forecast·SchedulerLog 전체 삭제. 에러 401, 403, 500

**POST /admin/reset/notifications** · REST · ADM · F35
```jsonc
// Response 200: { "deleted": 45, "message": "알림·감사 로그 45건 삭제됨" }
```
Notification·AuditLog 전체 삭제. 에러 401, 403, 500

**POST /admin/reset/reservations** · REST · ADM · F35
```jsonc
// Response 200: { "deleted": 33, "message": "예약·승인·대기열 33건 삭제됨" }
```
Reservation·ApprovalRequest·QueueEntry·MaintenanceSchedule 전체 삭제. 에러 401, 403, 500

**POST /admin/reset/all** · REST · ADM · F35
```jsonc
// Response 200: { "deleted": 1405, "message": "전체 운영 데이터 1405건 삭제됨" }
```
마스터 데이터(User·Team·Quota·Server) 제외 모든 운영 데이터 삭제. 에러 401, 403, 500

---

## 3. 추적 매핑 (UC → 기능 → API)

| UC | 기능 | API |
|---|---|---|
| UC01 | F01, F02 | GET /servers, GET /servers/{id} |
| UC02 | F03 | GET /reservations |
| UC03-a | F17, F18, F19 | GET /notifications, PATCH /notifications/{id}/read, WS |
| UC03-d | F08, F19 | GET /servers/alternatives, WS |
| UC04 | F04 | POST /reservations |
| UC05 | F05 | POST /reservations/instant |
| UC06 | F06 | POST /reservations/{id}/cancel |
| UC07 | F07 | POST /reservations/{id}/return |
| UC08 | F09 | POST /approval-requests |
| UC09 | F10, F11 | GET /approval-requests, POST /approval-requests/{id}/decision |
| UC10 | F12, F13 | GET /teams/{id}/quotas, PATCH /quotas/{id} |
| UC11 | F14 | POST /servers |
| UC12 | F15 | DELETE /servers/{id} |
| UC13 | F16, F30 | POST /servers/{id}/maintenances |
| UC14 | F23 | — |
| UC15 | F24 | — |
| UC16 | F25 | — |
| UC17 | F26 | — |
| UC18 | F27 | — |
| UC19 | F28 | — |
| UC20 | F29, F20 | POST /admin/users/{id}/unlock |
| UC21 | F21, F22 | GET /ops/dashboard, GET /ops/availability |
| UC22 | F31 | GET /ops/forecast |
| UC23 | F32 | GET /servers/{id}/health-trend |
| UC24 | F33 | GET /ops/incidents, GET /ops/incidents/{id} |
| UC25 | F34 | GET /ops/incidents/{id}/summary |

---

## 4. 노션 반영 계획 (승인 후 실행)

1. **기능 명세 진척도 DB** 컬럼 추가: `도메인`(select), `우선순위`(select).
2. **API 명세 진척도 DB** 컬럼 추가: `메서드`(select), `경로`(text), `통신 유형`(select), `권한`(multi-select). 제목은 `METHOD /path` 규칙.
3. **데이터 모델 페이지** 신규 생성(서버 예약/할당 관리 시스템 하위): 위 mermaid erDiagram + 엔티티별 속성표.
4. 기능 30건 · API 22건 행 생성, `관련 API`↔`관련 기능` relation 연결, `관련 UC`·`우선순위`·`도메인` 채움. 담당자는 미배정.
