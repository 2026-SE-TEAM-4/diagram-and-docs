# 02. 중단점 탐색 — `testkit breakpoint <경로>` (k6/hey 엔진)

> testkit 공통 구조는 [00-testkit-cli.md](./00-testkit-cli.md) 참조. 이 문서는 중단점 명령의 엔진 설계만 다룹니다.

## 목적

동시 사용자를 **계속 늘려가며** 성능이 무너지기 시작하는 임계점(breakpoint)을 찾습니다.
산출물은 합격/불합격이 아니라 **"동시 N명까지는 p95 < 300ms 유지, 이후 급격히 악화"라는 수치**입니다.

- 담당 테스트: 계획서 2.5 중단점 ★
- 엔진: 백엔드 경로는 k6(`ramping-vus`), server-pool은 이미지에 들어있는 `hey`. 둘 다 subprocess로 실행하고 testkit이 결과를 파싱해 임계점을 계산합니다.

## 명령

```text
testkit breakpoint login        # 로그인 경로 (bcrypt 병목 — 가장 먼저 무너질 것으로 예상)
testkit breakpoint reserve      # 예약 경로 (낙관적 락 409 비율 관찰)
testkit breakpoint read         # 조회 경로 (DB 풀 병목)
testkit breakpoint serverpool   # server-pool /metrics (hey, 스레드풀 포화)
```

## 관련 파일

```text
testing/testkit/
├── commands/breakpoint.py    # 계획 출력 → k6/hey 실행 → 임계점 계산
└── engines/k6/breakpoint.js  # ramping-vus 시나리오 (TARGET_PATH로 경로 선택)
```

## 핵심 설계

### 1) k6 시나리오 — `breakpoint.js`

```javascript
export const options = {
  scenarios: { breakpoint: {
    executor: 'ramping-vus', startVUs: 0,
    stages: [{ duration: '10m', target: 500 }],   // 끝없이 증가
  }},
  // 임계점 탐색이 목적이므로 thresholds로 중단하지 않고 끝까지 기록
};

export default function () {
  const path = __ENV.TARGET_PATH;     // login | reserve | read
  // login: POST /auth/login  (계정 이메일을 __VU로 분산)
  // reserve: 로그인 → POST /reservations (409는 conflict_409 카운터로 별도 집계)
  // read: 로그인 → GET /reservations
}
```

예약 경로는 409 비율이 50%를 넘는 VU 수준이 실질 임계점입니다(낙관적 락이 대부분을 막기 시작하는 지점).

### 2) 임계점 계산 — `commands/breakpoint.py`

```text
k6 run --out json=raw.json  → testkit이 raw.json(시계열) 파싱:
1. 10초 단위 구간(bucket)으로 묶어 구간별 p95·오류율 계산
   (VU 수는 경과 시간으로 선형 근사: 600초에 0→500)
2. 판정 규칙: p95 > 300ms 또는 오류율 > 5% 가 "2구간 연속" 처음 발생
   → 그 시점의 VU 수 = 임계점 (1구간 튐은 노이즈로 무시)
3. 출력: breakpoint.csv(시간·VU·p95·오류율) + "임계점: 동시 N명" 강조 한 줄
```

### 3) server-pool 측정 — hey

`/metrics`는 동기 핸들러라 스레드풀(기본 CPU수+4)이 한계를 결정합니다. `hey`를 동시성 단계별로 반복 실행해 같은 형태의 표를 만듭니다.

```text
for C in 10 20 30 40 50 75 100 150 200:
    hey -z 30s -c <C>  http://localhost:9101/metrics
→ 각 결과에서 p95·오류 수를 뽑아 serverpool-breakpoint.csv로 합침
```

## 실행 방법

```bash
cd testing
uv run testkit seed
uv run testkit breakpoint login        # 로그인 경로 임계점
uv run testkit breakpoint reserve
uv run testkit breakpoint serverpool
```

## 산출물

| 산출물 | 내용 |
| :--- | :--- |
| `breakpoint.csv` | 시간·VU·p95·오류율 시계열 (그래프용) |
| 임계점 요약 | "동시 N명, 그때의 p95/오류율" |
| 비교 관찰 | 예상 검증: 로그인(bcrypt) < 예약(락·풀) < 조회 순으로 임계점이 낮은지 |

이 수치는 운영 용량 산정 근거이자, 개선(bcrypt를 스레드풀로 이전, `pool_size` 확대) 전후 비교의 기준선이 됩니다.

## 구현 순서

1. `breakpoint.js` + `commands/breakpoint.py`의 login 경로 (임계점이 낮아 결과가 빨리 나옴)
2. reserve 경로 (409 카운터 포함)
3. serverpool(hey) 경로
