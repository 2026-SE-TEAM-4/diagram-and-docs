# 동적 모델 (상태도·시퀀스)

> 작성 2026-05-29 · 검토용
> 비기능 요구사항은 [`../02-requirements/nfr.md`](../02-requirements/nfr.md) 참조.

---

## 1. 상태 다이어그램

### 1.1 Server 상태

```mermaid
stateDiagram-v2
    [*] --> AVAILABLE: 서버 등록(UC11)
    AVAILABLE --> RESERVED: 예약(UC04)
    AVAILABLE --> IN_USE: 즉시 할당(UC05)
    RESERVED --> IN_USE: 사용 시작(예약 기간 진입)
    RESERVED --> AVAILABLE: 예약 취소(UC06)
    IN_USE --> AVAILABLE: 반납(UC07)/만료(UC16)/회수(UC15)
    AVAILABLE --> MAINTENANCE: 점검 시작(UC13)
    IN_USE --> MAINTENANCE: 강제 점검 후 강제 반납(UC13-E2)
    MAINTENANCE --> AVAILABLE: 점검 종료(UC13)
    AVAILABLE --> [*]: soft delete(UC12)
    MAINTENANCE --> [*]: soft delete(UC12)
    note right of RESERVED: 모든 전이 시 version += 1 (낙관적 잠금)
```

### 1.2 Reservation 상태

```mermaid
stateDiagram-v2
    [*] --> RESERVED: 예약 생성(UC04)
    [*] --> IN_USE: 즉시 할당(UC05)
    RESERVED --> IN_USE: 사용 시작
    RESERVED --> CANCELED: 취소(UC06)
    IN_USE --> RETURNED: 직접 반납(UC07)
    IN_USE --> EXPIRED: 만료 자동 반납(UC16)
    IN_USE --> RECLAIMED: 유휴 자동 회수(UC15)
    CANCELED --> [*]
    RETURNED --> [*]
    EXPIRED --> [*]
    RECLAIMED --> [*]
```

### 1.3 ApprovalRequest 상태

```mermaid
stateDiagram-v2
    [*] --> PENDING: 초과 요청 생성(UC08)
    PENDING --> APPROVED: 승인(UC09)
    PENDING --> REJECTED: 거절(UC09)
    PENDING --> AUTO_REJECTED: 72h 무응답(UC17)
    APPROVED --> [*]
    REJECTED --> [*]
    AUTO_REJECTED --> [*]
    note right of PENDING: 승인 vs 타임아웃 경쟁은\nSELECT FOR UPDATE / status='PENDING' 가드로 1건만 성공
```

> 설계 발견 (확정 2026-05-29): RESERVED → IN_USE("사용 시작")는 **스케줄러 자동 전환**으로 결정. startTime 도달 시 주기 잡이 전환(UC16 만료 처리와 동일 1분 잡에 통합), 사용자 액션·엔드포인트 불필요. → 기능 카탈로그 F25에 책임 추가, ADR-05 참조.

---

## 2. 시퀀스 다이어그램

### 2.1 예약 낙관적 잠금 충돌 → 대안 서버 안내 (UC04 + UC03-d)

```mermaid
sequenceDiagram
    actor A as 학생 A
    actor B as 학생 B
    participant API as API(POST /reservations)
    participant DB as PostgreSQL
    participant WS as 알림 채널(WS)

    A->>API: 예약 {serverId:1, version:42}
    B->>API: 예약 {serverId:1, version:42}
    API->>DB: SELECT server#1 (status, version)
    DB-->>API: status=AVAILABLE, version=42
    Note over API,DB: 두 요청 모두 version=42를 읽음
    API->>DB: A) UPDATE server SET status=RESERVED, version=43 WHERE id=1 AND version=42
    DB-->>API: 1 row → 성공
    API->>DB: A) INSERT Reservation; Quota.used += ; COMMIT
    API-->>A: 201 예약 확정
    API->>DB: B) UPDATE ... WHERE id=1 AND version=42
    DB-->>API: 0 row → 충돌
    API->>DB: B) ROLLBACK
    API->>DB: B) 대안 서버 조회(AVAILABLE·유사 사양, ≤5)
    DB-->>API: [server#2, server#3]
    API-->>B: 409 + 대안 목록
    API->>WS: B에게 충돌 알림 푸시(UC03-d)
    WS-->>B: 모달: 대안 서버 선택 → UC04 재시도
```

### 2.2 승인 vs 타임아웃 경쟁 (UC09 / UC17)

```mermaid
sequenceDiagram
    actor M as 팀관리자(MGR)
    participant API as API(decision)
    participant SCH as Scheduler(UC17)
    participant DB as PostgreSQL

    Note over DB: ApprovalRequest#5 status=PENDING (72h 임박)
    par 동시 발생
        M->>API: 승인 {decision: APPROVE}
    and
        SCH->>SCH: 주기 도래, 72h 초과 탐지
    end
    API->>DB: BEGIN; SELECT req#5 FOR UPDATE
    SCH->>DB: UPDATE req#5 SET AUTO_REJECTED WHERE status='PENDING'
    Note over DB: 행 잠금 — 한쪽만 진행
    DB-->>API: 잠금 획득
    API->>DB: UPDATE status=APPROVED, decidedBy=MGR; COMMIT
    DB-->>SCH: 0 row (이미 PENDING 아님)
    SCH->>SCH: 처리 없이 종료(UC17-A1/E1)
    API-->>M: 200 승인 완료 → 예약 확정 재개
```

### 2.3 유휴 서버 감지·자동 회수 (UC15)

```mermaid
sequenceDiagram
    participant SCH as Scheduler(1분 주기)
    participant DB as PostgreSQL
    participant WS as 알림 채널
    actor S as 학생(점유자)

    SCH->>DB: IN_USE 서버 최근 30분 평균 CPU 조회
    DB-->>SCH: server#7 avg=3% (<5%)
    SCH->>WS: 유휴 회수 경고(15분 후 회수)
    WS-->>S: 경고 수신
    SCH->>DB: 회수 예정 시각 기록(now+15m)
    alt 사용 중 표시 또는 직접 반납(UC07)
        S->>DB: 타이머 초기화 / 반납
        Note over SCH: 다음 주기 회수 대상 제외(UC15-A1/A2)
    else 15분 경과·여전히 유휴
        SCH->>DB: 사용률 재확인(<5%)
        SCH->>DB: TX) Reservation=RECLAIMED, Server=AVAILABLE, version+1, Quota.used-=
        SCH->>WS: 회수 완료 알림
        WS-->>S: 회수됨
    end
```

---

## 3. 설계 결정 기록 (ADR-lite)

| ID | 결정 | 대안 | 이유 |
|---|---|---|---|
| ADR-01 | 낙관적 잠금(version 컬럼) | 비관적 잠금(SELECT FOR UPDATE 전역) | 예약 충돌은 드묾 → 락 경합·데드락 위험 줄이고 처리량 확보. 승인 경쟁 등 좁은 구간만 비관적 락 병행 |
| ADR-02 | 서버 soft delete(deletedAt) | 물리 삭제 | 과거 메트릭·감사 로그 보존(UC12 E3, 부록) |
| ADR-03 | 상태 이력 테이블 미도입, SchedulerLog+status 근사 | ServerStatusHistory 도입 | 학기 범위 YAGNI. MTBF/MTTR 정확도 이슈 발생 시 도입 |
| ADR-04 | API/Scheduler 동일 코드베이스·별 프로세스 | 별도 서비스 분리 | core/infra 공유로 중복 제거, 단일 노드 단순성 |
| ADR-05 | RESERVED→IN_USE 전이는 **스케줄러 자동 전환**(확정) | 사용자 명시 액션 / 첫 접속 감지 | UC 미명시 공백을 상태도에서 발견·결정. startTime 잡에서 전환, UI 불필요 |
