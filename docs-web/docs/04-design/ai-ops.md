# AIOps 기능 설계 초안 (제안 A·B·C·D)

> 이 문서는 본 시스템의 핵심 차별점인 **AIOps(AI 기반 운영)** 를 강화하기 위한 신규 기능 4종의
> 필요 기술·로직·논리를 정리한 초안입니다.
> 기존 설계와의 추적성을 위해 기존 ID(F23~F30, UC14~UC21)를 참조하고,
> 신규 기능은 **F31~F34 / UC22~UC25** 로 부여합니다.
> 상세 필드는 [`../02-requirements/features-and-apis.md`](../02-requirements/features-and-apis.md) 의 ERD를 따릅니다.

---

## 0. 배경 — 지금 있는 것 vs 더 필요한 것

현업 AIOps는 **탐지 → 예측 → 상관/노이즈 제거 → 설명 → 자동복구** 순으로 성숙합니다.
우리 설계에 이미 있는 것과 비어 있는 것을 정리하면:

| 단계 | 현업 패턴 | 우리 현황 |
|------|-----------|-----------|
| 탐지 | 동적 이상탐지 | 있음 — 단, 정적 통계(μ±2σ) 수준 (F27/UC18) |
| 건강 | 건강 점수 | 있음 — 순간값 가중평균 (F28/UC19) |
| 자동복구 | 폐루프 자가치유 | 일부 — 유휴 자동 회수 (F24/UC15) |
| **예측(용량)** | 수요·포화 예측 | **없음 → 제안 A** |
| **예측(장애)** | 장애·열화 예측(예지보전) | **없음 → 제안 B** |
| **상관** | 이상 묶기·노이즈 감소 | **없음 → 제안 C** |
| **설명** | LLM 자연어 원인 요약 | **없음 → 제안 D** |

핵심 아이디어: 데이터(`ServerMetric`, `AnomalyRecord`)가 **쌓일수록** 예측·상관·설명 품질이
좋아지는 구조를 만든다. 즉 "단순 모니터링"이 아니라 "데이터 기반으로 점점 똑똑해지는 운영".

### 공통 전제
- **데이터 소스:** 1분 주기로 수집되는 `ServerMetric`(cpuUsage·memUsage·netUsage·gpuUsage) 시계열,
  `AnomalyRecord`(이상 이력), `Server.healthScore`, `Reservation`(예약 수요).
- **연산 위치:** 모든 AI 로직은 **APScheduler 잡(별도 컨테이너)** 에서 주기적으로 돌고,
  결과를 PostgreSQL에 저장한다. API는 "저장된 결과 조회"만 한다(읽기 빠름, 화면 부담 없음).
- **공통 라이브러리:** pandas, numpy (A·B·C), Claude API (D).
- **신규 엔티티:** `Forecast`, `Incident`(+ `AnomalyRecord.incidentId` FK), `IncidentSummary`.

---

## 제안 A — 예측적 용량·수요 예측 (Predictive Capacity Forecasting)

> 신규: **F31 / UC22** · 주기: 스케줄러 1시간 · 난이도: 중

### A-1. 개요 (무엇을)
과거 사용률·예약 시계열을 학습해 **"이 서버/풀이 N일 후 포화된다"**, **"다음 주 예약 수요가 X% 증가한다"**
를 미리 알려준다. 관리자는 긴급 증설이 아니라 **계획적으로** 자원을 늘리거나 분산할 수 있다.

### A-2. 필요 기술
- **시계열 예측 모델:** Holt-Winters(지수평활) 또는 SARIMA — 요일·시간대 계절성 반영.
  (라이브러리: `statsmodels`. 더 강하게 가려면 `prophet`. MVP는 Holt-Winters로 충분.)
- **데이터 전처리:** pandas 리샘플링(1분 → 1시간 평균), 결측(status=MISSING) 보간.
- **저장:** 예측 결과를 `Forecast` 엔티티에 적재.

### A-3. 로직·논리 (단계)
1. 스케줄러가 서버별 최근 **14~30일** `ServerMetric` 를 조회한다.
2. pandas 로 1시간 단위 평균으로 리샘플링하고 결측을 선형 보간한다.
3. Holt-Winters 로 **향후 7일(168시간)** cpu/mem/gpu 사용률을 예측한다(점추정 + 신뢰구간).
4. 예측선이 **임계치(예: 90%)** 를 처음 넘는 시점을 "포화 예상 시각(saturationAt)"으로 계산한다.
5. 예약 수요는 같은 방식으로 `Reservation` 생성 추이를 예측한다.
6. 결과를 `Forecast` 에 저장하고, 포화가 임박(예: 72시간 이내)하면 `Notification(type=CAPACITY)` 발송.

### A-4. 모델 수식 (요지)
- 수준·추세·계절 3성분 지수평활:
  `ŷ(t+h) = (Lₜ + h·Tₜ) · Sₜ₊ₕ₋ₘ`
  (L=수준, T=추세, S=주기 m의 계절지수). 잔차 표준편차로 ±신뢰밴드 산출.
- 재학습: 매 실행마다 최신 윈도우로 다시 적합 → "데이터 쌓이며 정확해짐"을 자연히 충족.

### A-5. 신규 엔티티
```
Forecast {
  bigint id PK
  bigint serverId FK   "nullable(풀 전체 예측 시 null)"
  enum metric          "CPU|MEM|GPU|RESERVATION_DEMAND"
  json   horizon       "예측 구간 [{ts, yhat, lower, upper}]"
  datetime saturationAt "임계 초과 예상 시각, nullable"
  float  confidence    "0~1"
  datetime generatedAt
}
```

### A-6. API
**GET /ops/forecast** · REST · 권한 MGR/ADM · 기능 F31
```jsonc
// Request (query)
{ "serverId": 1, "metric": "CPU", "days": 7 }
// Response 200
{
  "serverId": 1,
  "metric": "CPU",
  "generatedAt": "2026-06-04T10:00:00",
  "saturationAt": "2026-06-06T14:00:00",   // null이면 기간 내 포화 없음
  "confidence": 0.82,
  "horizon": [
    { "ts": "2026-06-04T11:00", "yhat": 71.2, "lower": 64.0, "upper": 78.4 },
    { "ts": "2026-06-04T12:00", "yhat": 73.5, "lower": 65.9, "upper": 81.1 }
    // ... 168 포인트
  ]
}
```
에러: 401, 403, 404(데이터 부족 시 예측 불가), 500

### A-7. 프론트 표출
- 사용률 Recharts 라인 차트에 **실측선(실선) + 예측선(점선) + 신뢰구간 밴드(반투명 영역)**.
- 서버 카드/대시보드에 **"포화 예상: 2일 14시간 후"** 경고 배지.

---

## 제안 B — 예측적 장애·건강 열화 예측 (Predictive Failure / Health Degradation)

> 신규: **F32 / UC23** · 주기: 스케줄러 10분(F28 직후) · 난이도: 중

### B-1. 개요 (무엇을)
기존 건강 점수(F28)는 **"지금"** 의 점수만 본다. 여기에 **추세**와 **이상 누적**을 더해
**"이 서버가 며칠 내 위험(고장/회수) 상태에 진입할 가능성"** 을 예측한다. 고장 전에 점검을 유도한다(예지보전).

### B-2. 필요 기술
- **추세 분석:** healthScore 시계열의 EWMA(지수가중이동평균) 기울기.
- **이상 빈도 집계:** 최근 24h `AnomalyRecord` 발생 빈도·가속도.
- **(선택) 분류 모델:** 과거 "회수/장애가 실제로 일어난" 라벨로 로지스틱 회귀
  (피처: 점수 기울기, 이상 빈도, gpu/cpu 변동성). MVP는 규칙 기반 점수화로 시작.

### B-3. 로직·논리 (단계)
1. F28 이 healthScore 를 갱신한 직후 실행.
2. 서버별 최근 **7일** healthScore 추세 기울기와 최근 24h 이상 빈도를 계산.
3. 위험도 = `w1·(점수 하락 기울기) + w2·(이상 빈도) + w3·(현재 점수의 낮음)` 로 0~100 산출.
4. 위험도와 추세로 **"위험 진입 예상까지 남은 시간(etaToRisk)"** 추정(현 기울기 외삽).
5. 임계 초과 시 `Notification(type=PREDICTIVE_FAILURE)` + 권장 점검창(`MaintenanceSchedule`) 제안.

### B-4. 논리적 근거
- 현업 예지보전은 6~12개월 데이터로 baseline·열화패턴을 학습해 **고장 전 경고**한다.
  우리는 동일 발상을 학기 단위 데이터로 축소 적용 — "추세가 나빠지는 서버를 미리 격리".
- 라벨이 쌓이면(실제 회수/장애 발생) 규칙 기반 → 학습 기반으로 자연스럽게 승급 가능.

### B-5. 신규 필드(기존 Server 확장)
```
Server {
  ... 기존 ...
  int   healthScore        "UC19, nullable"
  float riskScore          "UC23, 0~100, nullable"        // 신규
  datetime etaToRisk       "위험 진입 예상 시각, nullable"   // 신규
}
```

### B-6. API
**GET /servers/{id}/health-trend** · REST · MGR/ADM · F32
```jsonc
// Response 200
{
  "serverId": 1,
  "healthScore": 71,
  "riskScore": 64,                  // 높을수록 위험
  "trend": "DEGRADING",            // IMPROVING|STABLE|DEGRADING
  "etaToRisk": "2026-06-07T00:00:00", // null이면 임박 위험 없음
  "history": [
    { "ts": "2026-05-28", "healthScore": 88 },
    { "ts": "2026-05-29", "healthScore": 85 }
    // ... 7일
  ],
  "drivers": ["health 기울기 -4.1/일", "최근 24h 이상 9건"]
}
```
에러: 401, 403, 404, 500

### B-7. 프론트 표출
- 서버 카드에 **위험 예측 배지**(예: "주의 → 위험 전이 예상 3일") + 건강점수 **스파크라인**.
- 위험도 높은 서버를 대시보드 상단에 정렬해 "먼저 봐야 할 서버" 강조.

---

## 제안 C — 이상 상관·노이즈 감소 (Anomaly Correlation → Incident)

> 신규: **F33 / UC24** · 주기: 스케줄러 5분(F27 직후) · 난이도: 중하

### C-1. 개요 (무엇을)
이상이 터지면 `AnomalyRecord` 가 수십 건씩 쏟아진다. 이를 **시간·서버·유형**으로 묶어
**하나의 "인시던트(Incident)"** 로 만든다. 운영자는 알림 폭주 대신 **의미 있는 소수의 사건**만 본다.

### C-2. 필요 기술
- **클러스터링 로직:** 시간 윈도우(예: 10분) + 서버 그룹 + 메트릭 유형 기준 그룹핑.
  (복잡한 ML 불필요 — 규칙/거리 기반으로 충분. 고도화 시 DBSCAN 시간-토폴로지 거리.)
- **디바운스/상태관리:** Redis 로 진행 중 인시던트 키 관리(중복 생성 방지, 자동 종료).

### C-3. 로직·논리 (단계)
1. F27 이 새 `AnomalyRecord` 를 만들면 트리거.
2. 같은 서버 그룹 + 10분 윈도우 안의 미할당 이상들을 모은다.
3. 진행 중 인시던트가 있으면 거기 붙이고(`AnomalyRecord.incidentId`), 없으면 새 `Incident` 생성.
4. 인시던트의 심각도 = 묶인 이상 수·서버 수·최고 편차로 산정.
5. 일정 시간(예: 15분) 새 이상이 안 붙으면 인시던트를 `RESOLVED` 로 자동 종료.
6. 알림은 **인시던트 단위로 1건만** 발송(`Notification(type=INCIDENT)`) → 노이즈 감소.

### C-4. 논리적 근거
- 현업 사례: 토폴로지·시간·인과 기반 상관으로 **알림 70~91% 감소, MTTR 약 40% 단축**.
- 측정 지표(`noiseReductionRate = 1 - 인시던트수/이상수`)를 대시보드에 노출하면
  "AIOps 효과"를 **수치로** 보여줄 수 있다(발표/평가에 유리).

### C-5. 신규 엔티티
```
Incident {
  bigint id PK
  enum   severity     "INFO|WARNING|CRITICAL"
  enum   status       "OPEN|RESOLVED"
  int    anomalyCount "묶인 이상 수"
  json   serverIds    "연관 서버 목록"
  datetime startedAt
  datetime resolvedAt "nullable"
}
// AnomalyRecord 에 incidentId FK(nullable) 추가
```

### C-6. API
**GET /ops/incidents** · REST · MGR/ADM · F33
```jsonc
// Request (query): { "status": "OPEN", "severity": "CRITICAL" }
// Response 200
{
  "noiseReductionRate": 0.86,       // 이상 86%를 인시던트로 압축
  "incidents": [
    {
      "id": 51,
      "severity": "CRITICAL",
      "status": "OPEN",
      "anomalyCount": 12,
      "serverIds": [1, 2, 5],
      "startedAt": "2026-06-04T09:40:00",
      "resolvedAt": null
    }
  ]
}
```
**GET /ops/incidents/{id}** — 인시던트에 묶인 개별 `AnomalyRecord` 목록 반환. 에러: 401,403,404,500

### C-7. 프론트 표출
- 알림함을 개별 이상이 아니라 **인시던트 타임라인(접힌 그룹)** 으로. "관련 이상 12건" 펼치기.
- 대시보드에 **"노이즈 감소율 86%"** KPI 카드.

---

## 제안 D — LLM 기반 이상 설명·인시던트 요약 (Explainable RCA)

> 신규: **F34 / UC25** · 트리거: 인시던트 생성/조회 시 · 난이도: 중(외부 API 연동)

### D-1. 개요 (무엇을)
인시던트(제안 C)가 생기면 **LLM이 "무슨 일이 / 왜 / 어떻게 대응"** 을 자연어로 요약한다.
근거가 된 메트릭·이상 이력을 **인용**해 신뢰도를 높인다(환각 억제). 2025년 'AI SRE'의 핵심 차별점.

### D-2. 필요 기술
- **LLM:** Claude API (이미 개발 환경에 존재).
- **컨텍스트 구성(RAG식):** 인시던트에 묶인 `AnomalyRecord` + 해당 시점 `ServerMetric` 발췌 +
  서버 메타를 구조화해 프롬프트에 주입. LLM은 **주어진 데이터 안에서만** 추론하도록 지시.
- **캐싱/비용:** 인시던트당 1회 생성 후 `IncidentSummary` 에 저장(재조회는 DB에서). Redis 단기 캐시.

### D-3. 로직·논리 (단계)
1. 인시던트가 `OPEN` 으로 생성되면(또는 운영자가 상세를 열면) 요약 잡 트리거.
2. 묶인 이상·메트릭·서버 정보를 JSON 컨텍스트로 정리한다.
3. 프롬프트: "다음 운영 데이터만 근거로, ①상황 ②원인 후보 ③권장 조치를 한국어로 요약하라.
   각 주장 뒤에 근거 데이터(서버/시각/값)를 괄호로 인용하라. 데이터에 없으면 추측 금지."
4. 응답을 파싱해 `IncidentSummary` 에 저장(원인 후보, 권장 조치, 인용 목록).
5. 운영자 확인용으로만 사용(자동 실행 X) — **사람이 최종 판단**.

### D-4. 논리적 근거 / 안전장치
- 현업 트렌드: "탐지에서 **설명**으로". LLM이 로그라인·커밋 등을 **인용**하면 환각이 줄고 신뢰가 오른다.
- 안전: LLM은 **읽기 전용 분석**만. 자동 조치는 절대 LLM에 위임하지 않는다(권장만).
- 비용: 인시던트당 1회 생성·저장으로 호출 최소화.

### D-5. 신규 엔티티
```
IncidentSummary {
  bigint id PK
  bigint incidentId FK
  string situation        "상황 요약"
  json   rootCauses       "[{cause, evidence}]"
  json   recommendations  "[{action, rationale}]"
  string model            "사용 모델명"
  datetime generatedAt
}
```

### D-6. API
**GET /ops/incidents/{id}/summary** · REST · MGR/ADM · F34
```jsonc
// Response 200
{
  "incidentId": 51,
  "generatedAt": "2026-06-04T09:42:00",
  "model": "claude-...",
  "situation": "09:40부터 GPU 서버 3대(gpu-01,02,05)에서 CPU·GPU 사용률이 동시 급증했습니다.",
  "rootCauses": [
    { "cause": "동일 팀의 대규모 학습 작업 동시 시작으로 추정",
      "evidence": "gpu-01 09:41 cpu 97% (평소 μ=42%, σ=8%), gpu-02 동일 패턴" }
  ],
  "recommendations": [
    { "action": "해당 팀 Quota 일시 점검 및 작업 분산 권고",
      "rationale": "3대 동시 포화로 타 사용자 영향 가능" },
    { "action": "gpu-05 우선 모니터링", "rationale": "상승 기울기가 가장 가파름" }
  ]
}
```
에러: 401, 403, 404(요약 미생성), 500

### D-7. 프론트 표출
- 인시던트 상세에 **"AI 분석 요약"** 카드: 상황 / 원인 후보 / 권장 조치 + 근거 인용 토글.
- "AI가 작성, 사람이 검토 필요" 라벨로 책임 소재를 명확히.

---

## 부록 — 신규 항목 요약 (추적용)

| 신규 ID | 기능 | UC | 주기/트리거 | 핵심 기술 | 신규 엔티티 | API |
|---------|------|----|-------------|-----------|-------------|-----|
| F31 | 용량·수요 예측 | UC22 | 스케줄러 1h | Holt-Winters/SARIMA, pandas | `Forecast` | GET /ops/forecast |
| F32 | 장애·건강 열화 예측 | UC23 | 스케줄러 10m | EWMA 추세, (로지스틱) | Server 확장 | GET /servers/{id}/health-trend |
| F33 | 이상 상관·노이즈 감소 | UC24 | 스케줄러 5m | 시간/토폴로지 클러스터링, Redis | `Incident` | GET /ops/incidents |
| F34 | LLM 원인 설명·요약 | UC25 | 인시던트 생성/조회 | Claude API, RAG식 컨텍스트 | `IncidentSummary` | GET /ops/incidents/{id}/summary |

### 의존 관계
- C(F33) 는 기존 이상탐지 F27 위에서 동작 → **C 먼저**.
- D(F34) 는 C의 인시던트가 있어야 함 → **C 다음 D**.
- A(F31)·B(F32) 는 독립적으로 병행 가능(둘 다 `ServerMetric` 시계열만 사용).

### 권장 구현 순서
1. **C (노이즈 감소)** — 즉시 효과·수치 어필, 난이도 낮음.
2. **A (용량 예측)** — "데이터로 똑똑해짐" 스토리의 핵심.
3. **D (LLM 설명)** — 데모 임팩트 최상, C 위에 얹음.
4. **B (장애 예측)** — 라벨 데이터가 쌓이면 학습형으로 고도화.
