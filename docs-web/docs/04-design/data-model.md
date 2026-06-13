# 데이터 모델 (ERD)

> 작성 2026-05-29 · 최신화 2026-06-12(AIOps 구현 반영: 수집·이상탐지·건강점수 + 제안 A·B·C·D)
> 기능·API 명세는 [`../02-requirements/features-and-apis.md`](../02-requirements/features-and-apis.md) 참조.

## ERD (논리)

```mermaid
erDiagram
    Team ||--o{ User : "소속"
    Team ||--o{ Quota : "팀 한도 배분"
    User ||--|| Quota : "개인 한도"
    User ||--o{ Reservation : "예약"
    Server ||--o{ Reservation : "대상"
    User ||--o{ ApprovalRequest : "요청(requester)"
    User ||--o{ ApprovalRequest : "결재(approver)"
    Server ||--o{ ApprovalRequest : "대상 서버"
    User ||--o{ Notification : "수신"
    Server ||--o{ ServerMetric : "시계열 수집"
    Server ||--o{ AnomalyRecord : "이상 이력"
    Server ||--o{ MaintenanceSchedule : "점검 일정"
    Server ||--o{ QueueEntry : "대기열"
    User ||--o{ QueueEntry : "대기"
    User ||--o{ AuditLog : "행위자"
    Incident ||--o{ AnomalyRecord : "이상 묶음"
    Incident ||--o| IncidentSummary : "LLM 요약"
    Server ||--o{ Forecast : "용량 예측"
    Server ||--o{ ServerHealthHistory : "건강점수 이력"
    User ||--o{ SecurityEvent : "보안 이벤트(actor, nullable)"
    User ||--o{ SecurityAlert : "경보 해결(resolved_by, nullable)"

    Team {
        bigint id PK
        string name
        string code "타팀 표시용 코드(UC01-E2)"
        int totalQuotaLimit "팀 전체 한도(일수)"
        datetime createdAt
    }
    User {
        bigint id PK
        string name
        string email UK
        enum role "STU|MGR|ADM"
        bigint teamId FK
        string hashedPassword "nullable, JWT 인증 컬럼(후속 구현)"
        datetime lockedUntil "UC20 일시 잠금, nullable"
        datetime createdAt
    }
    Quota {
        bigint id PK
        bigint userId FK "1:1"
        bigint teamId FK
        int limit "개인 한도(일수)"
        int used "현재 점유량"
        int version "낙관적 잠금(UC10-E3)"
    }
    Server {
        bigint id PK
        string name
        string ip
        int cpuCores
        int ramGb
        string gpuModel "nullable"
        string groupName "서버 그룹, nullable"
        enum status "AVAILABLE|RESERVED|IN_USE|MAINTENANCE"
        int version "낙관적 잠금"
        int healthScore "UC19, nullable"
        float riskScore "위험도 0~100, nullable (UC23)"
        datetime etaToRisk "위험 진입 예상 시각, nullable (UC23)"
        datetime deletedAt "soft delete(UC12), nullable"
        datetime createdAt
    }
    Reservation {
        bigint id PK
        bigint userId FK
        bigint serverId FK
        datetime startTime
        datetime endTime
        enum status "RESERVED|IN_USE|CANCELED|RETURNED|EXPIRED|RECLAIMED"
        datetime createdAt
    }
    ApprovalRequest {
        bigint id PK
        bigint requesterId FK
        bigint approverId FK "팀 MGR, nullable"
        bigint serverId FK "대상 서버"
        datetime requestedStart
        datetime requestedEnd
        string reason
        enum status "PENDING|APPROVED|REJECTED|AUTO_REJECTED"
        datetime requestedAt
        datetime decidedAt "nullable"
        string decidedBy "userId 또는 SYSTEM, nullable"
    }
    Notification {
        bigint id PK
        bigint userId FK
        string type "값 미확정이라 평문 문자열로 저장: APPROVAL_RESULT|CONFLICT|IDLE_WARNING|EXPIRY|RECLAIM|SECURITY|CAPACITY|INCIDENT|PREDICTIVE_FAILURE"
        string message
        json payload "링크·부가 데이터"
        datetime readAt "nullable"
        datetime createdAt
    }
    ServerMetric {
        bigint id PK
        bigint serverId FK
        float cpuUsage
        float memUsage
        float netUsage
        float gpuUsage "nullable, GPU 미탑재 시 null (서버풀 /metrics)"
        enum status "OK|MISSING|NA"
        datetime collectedAt "시계열 인덱스"
    }
    AnomalyRecord {
        bigint id PK
        bigint serverId FK
        enum metric "CPU|MEM|NET|GPU (이탈 메트릭 종류, UC18)"
        float currentValue
        float mean "7일 이동평균 μ"
        float stddev "표준편차 σ"
        datetime detectedAt
        bigint incidentId FK "묶인 인시던트, nullable, indexed (UC24)"
    }
    MaintenanceSchedule {
        bigint id PK
        bigint serverId FK
        datetime startAt
        datetime endAt
        string reason
        string recurringRule "반복 점검(UC13-A2), nullable"
        bigint createdBy FK
        datetime createdAt
    }
    QueueEntry {
        bigint id PK
        bigint serverId FK "nullable(사양 기반 대기)"
        bigint userId FK
        json requestedSpec "사양 조건"
        int position
        datetime createdAt
    }
    SchedulerLog {
        bigint id PK
        string ucId "UC14~UC20"
        datetime executedAt
        bool success
        int processedCount
    }
    AuditLog {
        bigint id PK
        bigint actorId FK
        string action "값 미확정이라 평문 문자열로 저장: VIEW|DELETE_SERVER|ACCOUNT_LOCK|MANUAL_UNLOCK|..."
        string targetType
        string targetId
        json detail
        datetime createdAt
    }
    Incident {
        bigint id PK
        enum severity "INFO|WARNING|CRITICAL"
        enum status "OPEN|RESOLVED"
        int anomalyCount "묶인 이상 수"
        json serverIds "연관 서버 목록"
        datetime startedAt
        datetime resolvedAt "nullable"
    }
    Forecast {
        bigint id PK
        bigint serverId FK "nullable, 풀 전체 예측(수요)은 null"
        enum metric "CPU|MEM|GPU|RESERVATION_DEMAND"
        json horizon "[{ts,yhat,lower,upper}]"
        datetime saturationAt "임계 초과 예상, nullable"
        float confidence "0~1"
        datetime generatedAt
    }
    IncidentSummary {
        bigint id PK
        bigint incidentId FK "indexed"
        string situation "상황 요약"
        json rootCauses "[{cause,evidence}]"
        json recommendations "[{action,rationale}]"
        string model "사용 LLM 모델명"
        datetime generatedAt
    }
    ServerHealthHistory {
        bigint id PK
        bigint serverId FK "indexed"
        int score "그 시점 건강점수"
        datetime recordedAt "시계열, 추세 기울기용"
    }
    SecurityEvent {
        bigint id PK
        string event_type "SecurityEventType: LOGIN_FAILURE|ACCOUNT_LOCKED|ACCESS_DENIED|ADMIN_ACTION|AGENT_UNREACHABLE"
        string severity "IncidentSeverity(재사용): INFO|WARNING|CRITICAL. 기본 INFO"
        bigint actor_id FK "nullable — 미가입 시도 허용"
        string source_ip "nullable, String(45)"
        string identifier "nullable, 시도된 이메일 등"
        string target_type "nullable, 대상 종류(server·user 등)"
        string target_id "nullable, 대상 식별자"
        json detail "nullable, 경로·사유 등 부가정보"
        datetime occurred_at "server_default now(). 인덱스: (event_type, occurred_at), (source_ip)"
    }
    SecurityAlert {
        bigint id PK
        string alert_type "SecurityAlertType: BRUTE_FORCE|ACCESS_ABUSE|AGENT_DOWN|ADMIN_ABUSE"
        string severity "IncidentSeverity(재사용)"
        string status "IncidentStatus(재사용): OPEN|RESOLVED. 기본 OPEN"
        string subject "경보 주체(IP·이메일·server:{id}·user:{id})"
        int event_count "묶인 이벤트 수"
        string message "사람이 읽는 요약, String(500)"
        datetime started_at "server_default now()"
        datetime resolved_at "nullable"
        bigint resolved_by FK "nullable — 해결한 ADM"
    }
```

## 설계 메모

- 신규 보안 관제 엔티티(SecurityEvent·SecurityAlert)는 F36 인라인 기록과 F37 탐지 잡이 각각 적재하고, F38 API는 조회·해결만 한다. 기존 `IncidentSeverity`·`IncidentStatus` enum을 재사용하며, 신규 enum `SecurityEventType`·`SecurityAlertType`은 `app/models/enums.py`에 추가됨.
- 신규 AIOps 엔티티(Incident·Forecast·IncidentSummary·ServerHealthHistory)는 모두 스케줄러 잡이 적재하고 API는 조회만 한다.
- `Server.healthScore`·`riskScore`·`etaToRisk` 갱신은 낙관적 락(version)을 건드리지 않는 직접 UPDATE로 한다.
- `AnomalyRecord.incidentId`는 상관 잡(F33)이 채운다.
- **낙관적 잠금**은 `Server.version`이 단일 진실. 예약/취소/반납/회수/만료는 모두 `WHERE id=? AND version=?` 조건으로 갱신, 영향 행 0이면 409 충돌(UC04-A.1).
- `Quota`는 `User`와 1:1이나 별도 엔티티로 둠(한도·사용량·version 독립 관리, UC10).
- `SchedulerLog`·`AuditLog`는 다른 엔티티와 FK 관계가 느슨(행위자/대상은 id 참조). UC21 대시보드와 가용성 지표(MTBF·MTTR)의 데이터 소스.
- 가용성 지표는 별도 테이블 없이 `SchedulerLog` + `Server.status` 이력에서 산출(부록 B.5). 상태 이력 추적이 필요하면 `ServerStatusHistory`를 추가 고려(미정).

## 설계 결정 (확정 2026-05-29)

- (Q1) `Reservation.version` **두지 않음** — 충돌 제어는 `Server.version` 단일 진실로 충분. 예약 행 자체의 동시 수정 경로 없음.
- (Q2) 대기열은 `QueueEntry` **엔티티로 유지** — UC05 "대기 N번째"(position)·반납 시 자동 할당 트리거에 필요.
- (Q3) `ServerStatusHistory` **생략** — UC21 MTBF/MTTR은 `SchedulerLog` + `Server.status`로 근사. 대시보드 정확도 이슈 발생 시 추가(설계 결정 ADR-03 참조).
