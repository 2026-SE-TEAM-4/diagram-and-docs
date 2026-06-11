# 00. testkit — 팀 공용 테스트 CLI

## 목적

부하·중단점·장애 테스트를 팀원 누구나 **명령 한 줄**로 돌릴 수 있게 하는 CLI 도구입니다.
부하 엔진(Locust/k6)을 새로 만드는 게 아니라, 그 앞뒤를 감싸는 오케스트레이터입니다:

```text
사전 점검(컨테이너 살아있나) → 계획 출력(뭘 어떻게 테스트하나) → 실행(실시간 지표) → 결과(다듬어진 표 + 판정)
```

모든 명령이 이 4단계를 같은 모양으로 출력하므로, 어떤 테스트든 사용법이 동일합니다.

## 기술 선택

| 역할 | 선택 | 이유 |
| :--- | :--- | :--- |
| CLI 프레임워크 | **Typer** | 서브커맨드 구조·`--help`·인자 검증 자동. FastAPI와 같은 제작자라 팀에 익숙한 사용감 |
| 터미널 출력 | **Rich** | 점검 체크표(✔/✖), 실행 중 실시간 지표(Live), 결과 표, PASS/FAIL 판정 출력 전부 담당 |
| 사전 점검 | **httpx** + `docker ps` (subprocess) | 컨테이너 존재는 docker ps로, 실제 응답하는지는 `/health`·`/metrics` HTTP 호출로 이중 확인 |
| 부하 엔진 | **Locust / k6 subprocess 래핑** | `locust --headless --csv`, `k6 --summary-export`로 돌리고 산출 파일을 파싱해 Rich로 렌더링. 엔진을 임베드하지 않아 단순함 |
| DB 검증 | **asyncpg** | 스파이크 후 정합성 검사를 CLI 안에서 바로 실행 |
| 실행/패키징 | **uv** | 레포 표준. `uv run testkit ...` 으로 설치 절차 없이 실행 |

외부 바이너리 의존: `k6` (중단점 테스트에만 필요. 사전 점검에서 없으면 설치 안내를 출력하고 중단).

## 명령 체계

```text
testkit check                      # 사전 점검만 단독 실행
testkit seed                       # 시드 데이터 투입 (계정·팀·쿼터)
testkit load | stress | spike | endurance     # 성능 4종 (Locust 엔진) → 01 문서
testkit breakpoint login|reserve|read|serverpool   # 중단점 (k6/hey)   → 02 문서
testkit fault s1|s2|s3|s4|s5|all   # 장애 주입·복원                     → 03 문서
testkit verify                     # DB 정합성 검사만 단독 실행
```

공통 옵션: `--host`(기본 http://localhost:8000), `--no-preflight`(점검 생략), `--duration`/`--users`(시나리오 기본값 덮어쓰기).

## 파일 구조

```text
testing/
├── pyproject.toml            # uv 프로젝트: typer, rich, httpx, asyncpg, locust
├── README.md                 # 사용법 요약
├── results/                  # 실행 결과 저장 (gitignore)
└── testkit/
    ├── cli.py                # Typer 앱 — 서브커맨드 등록만
    ├── ui.py                 # Rich 출력 헬퍼 (4단계 출력 규약은 전부 여기)
    ├── preflight.py          # 컨테이너·HTTP·바이너리 점검
    ├── results.py            # 결과 폴더 생성·요약 저장
    ├── seed.py               # 시드 투입 (API 호출 방식)
    ├── verify.py             # DB 정합성 검사 3종 (asyncpg)
    ├── commands/
    │   ├── loadtest.py       # load/stress/spike/endurance
    │   ├── breakpoint.py     # breakpoint 4종
    │   └── fault.py          # fault s1~s5
    └── engines/
        ├── locust/           # users.py, shapes.py, locustfile.py
        └── k6/               # breakpoint.js
```

설계 원칙: **commands/ 의 각 파일은 서로 import하지 않습니다.** 공유 코드는 ui/preflight/results/verify에만 둡니다 (병렬 개발·리뷰가 쉬워짐).

## 출력 규약 (모든 명령 공통)

```text
$ uv run testkit spike

[1/4] 사전 점검
  ✔ backend          running   /health 200 (12ms)
  ✔ agent-1 (9101)   running   /metrics 200
  ✖ agent-3 (9103)   exited    → docker compose up -d agent-3
  → 하나라도 ✖면 여기서 중단 (잘못된 측정 방지). --no-preflight로 강행 가능

[2/4] 테스트 계획
  시나리오   스파이크 (test-plan 2.3 ★)
  요청       POST /reservations/instant — 200 VU를 1초 내 투입 → 4분 관찰
  측정       p95 / RPS / 오류율 + 종료 후 DB 정합성 3종
  합격 기준  서버 생존 · 초과 배정 0건 · 쿼터 초과 0건

[3/4] 실행 중   ⠼ 02:31/05:00  VU 200  p95 412ms  RPS 183  err 2.1%

[4/4] 결과
  지표 표 + 합격 기준별 PASS/FAIL + 종합 판정
  결과 저장: testing/results/2026-06-15-1432-spike/
```

- 1단계 점검 항목: backend `/health` → 에이전트 3대 `/metrics` → (필요 시) k6 바이너리 → docker 데몬
- 2단계는 "무엇을, 어떤 요청으로, 무엇을 측정하고, 무엇이면 합격인지"를 실행 전에 반드시 보여줌 — 팀원이 명령만 보고도 테스트 내용을 학습하는 게 목적
- 4단계 판정: 합격 기준 각각에 PASS/FAIL을 따로 찍고, 종합은 전부 PASS일 때만 PASS
- 종료 코드: 종합 PASS=0, FAIL=1, 사전 점검 실패=2 (CI에서도 쓸 수 있게)

## 결과 저장 규약

`testing/results/<YYYY-MM-DD-HHMM>-<명령>/` 에 저장:

- `summary.json` — 계획·지표·판정(기계가 읽는 용도, 추이 비교)
- `report.txt` — 4단계 출력 그대로(사람이 읽는 용도)
- 엔진 원본 산출물 — Locust CSV, k6 JSON, 장애 구간 로그 등

## 구현 원칙

1. 코드는 학부생 수준 가독성(backend `rule.md`와 같은 기조). 주석은 한국어, 이모지 금지.
2. 파일당 200줄 이내 목표. 출력 꾸미기는 전부 `ui.py`로 모아서 commands/는 흐름만 남김.
3. 엔진 호출은 subprocess + 산출 파일 파싱. 엔진 내부 API에 의존하지 않음.
4. 실패는 명확하게: 점검 실패 시 "무엇이 죽었고 어떤 명령으로 살리는지"를 그대로 출력.
