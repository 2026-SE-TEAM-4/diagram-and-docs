# 테스트 툴 설계 모음

[`테스트 계획서`](../../docs-web/docs/05-testing/test-plan.md)에서 정의한 테스트들을 **실제로 어떤 도구로, 어떤 구조로 구현할지** 설계한 문서 모음입니다.

핵심 결정: 부하·중단점·장애 테스트는 **`testkit` 이라는 하나의 CLI**(Typer + Rich)로 묶습니다.
모든 명령이 "사전 점검 → 계획 출력 → 실행 → 다듬어진 결과" 4단계를 같은 모양으로 출력하므로, 팀원 누구나 명령 한 줄로 돌릴 수 있습니다. 전체 구조는 [00-testkit-cli.md](./00-testkit-cli.md)부터 읽으세요.

## 문서 목록

| 문서 | 형태 | 담당하는 테스트 (계획서 절) |
| :--- | :--- | :--- |
| [00-testkit-cli.md](./00-testkit-cli.md) | **testkit CLI 공통 설계** — 기술 선택·명령 체계·출력 규약 | (공통 기반) |
| [01-load-suite-locust.md](./01-load-suite-locust.md) | `testkit load/stress/spike/endurance` — Locust 엔진 | 부하(2.1) · 과부하(2.2) · 스파이크(2.3★) · 내구력(2.4) |
| [02-breakpoint-k6.md](./02-breakpoint-k6.md) | `testkit breakpoint <경로>` — k6/hey 엔진 | 중단점(2.5★) |
| [03-fault-injector.md](./03-fault-injector.md) | `testkit fault s1~s5` — docker 장애 주입 | 복원(3.2) |
| [04-blackbox-pytest.md](./04-blackbox-pytest.md) | pytest 스위트 (`backend/tests/` 확장, testkit과 별개) | 보안(3.1) · 동등분할(5.1) · 경계값(5.2★) · 원인-결과(5.3) · 커버리지(5.4) |
| [05-static-analysis-ci.md](./05-static-analysis-ci.md) | CI 파이프라인 (testkit과 별개) | 정적 분석(4.2) · 회귀(3.3) 자동화 |

> 04·05는 pytest/CI 생태계가 이미 그 자체로 좋은 CLI·리포트를 제공하므로 testkit에 넣지 않습니다.
> testkit은 "엔진 여러 개를 오케스트레이션해야 하고 결과를 직접 다듬어야 하는" 1~3만 담당합니다.

## 코드 위치

```text
2026-se-team-4/
├── test-tool/                # testkit CLI 구현 + 본 설계 문서 — uv run testkit ...
└── backend/tests/            # pytest 스위트 (04) — CI 설정은 05
```

## 모든 테스트 공통 준비 사항

1. **`--reload` 제거** — Uvicorn 자동 리로드는 성능 측정을 왜곡함.
2. **DB 커넥션 풀 명시** — `create_async_engine(..., pool_size=N)` 설정 후 테스트. 기본값(~10)과 비교 측정하면 좋은 리포트가 됨.
3. **시드 데이터 통일** — `uv run testkit seed` 하나로 통일 (계정 N개·팀·서버 3대·쿼터).
4. **측정 지표 통일** — 응답시간 p50/p95/p99, 처리량(RPS), 오류율(4xx/5xx), 자원(CPU/메모리/DB·Redis 연결 수).
5. **결과 저장 규약** — `results/<날짜시각>-<명령>/` 에 summary.json + report.txt + 엔진 원본. testkit이 자동으로 처리.
