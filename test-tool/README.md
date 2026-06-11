# testkit — 팀 공용 테스트 CLI

부하·중단점·장애 테스트를 명령 한 줄로 돌리는 도구입니다.
모든 명령이 **사전 점검 → 테스트 계획 → 실행 → 다듬어진 결과** 4단계를 같은 모양으로 출력합니다.

설계 문서: [`docs/`](./docs/README.md) (00이 전체 구조, 01~03이 각 명령). 테스트 계획서는 [`../docs-web/docs/05-testing/test-plan.md`](../docs-web/docs/05-testing/test-plan.md).

## 준비

```bash
# 1) 백엔드 + server-pool 컨테이너 기동
cd ../backend     && docker compose up -d
cd ../server-pool && docker compose up -d

# 2) testkit 의존성 설치
uv sync
```

> 부하 측정 전, 백엔드 `docker-compose.yml`의 `uvicorn ... --reload` 에서 `--reload`를 제거하세요(측정 왜곡 방지).

## 사용

```bash
uv run testkit check                  # 사전 점검만 (백엔드·에이전트·docker·k6)
uv run testkit seed                   # 시드 투입 (팀·서버 3대·계정 50개·쿼터)

uv run testkit load                   # 부하
uv run testkit stress                 # 과부하
uv run testkit spike                  # 스파이크 + 자동 DB 정합성 검사 ★
uv run testkit endurance --duration 6h

uv run testkit scenario               # 보안·성능·안정성 시나리오 점검 (단일 요청 단언)
uv run testkit scenario --category security   # 카테고리만 (security|performance|stability|all)

uv run testkit breakpoint login       # 중단점 (login|reserve|read|serverpool)
uv run testkit fault s1               # 장애 주입 (s1~s5|all)
uv run testkit verify                 # DB 정합성 검사만 단독 실행

uv run testkit chart                  # 최신 실행을 인터랙티브 HTML로 (--open 으로 브라우저 열기)
uv run testkit chart --compare 3      # 최근 3개 실행 겹쳐 비교
uv run testkit chart --list           # 시각화 가능한 실행 목록
```

부하 4종(load/stress/spike/endurance)은 실행 중 단계 진행 바와 실시간 지표
(RPS·p95·요청·실패·사용자 + 추세 스파크라인)를 보여 줍니다.

### 부하 강도 (--intensity / -i, 1~4)

load·stress·spike·endurance·breakpoint은 `--intensity N` 으로 부하 강도를 조절합니다.
레벨이 곧 배율(레벨 N = ×N)이며 사용자 수·spawn_rate에 적용됩니다(단계 시간은 불변).
레벨 1이 기본값이자 기존 동작입니다.

```bash
uv run testkit load -i 3              # load 단계별 사용자 ×3 (10/50/100/200 → 30/150/300/600)
uv run testkit spike -i 4            # 스파이크 피크 ×4 (200 → 800명)
uv run testkit breakpoint login -i 2 # 중단점 램프 피크 ×2 (500 → 1000 VU)
```

### 시나리오 점검 (testkit scenario)

권한 없는 접근·잘못된 입력·경쟁 조건 등 약 20여 종을 단일 요청으로 단언 검증합니다.
보안(인증/권한)·성능(응답시간)·안정성(5xx 금지/경쟁) 3개 카테고리로 묶여 있고,
critical 시나리오가 모두 통과하면 종합 PASS(종료 코드 0)입니다.

## 결과

`results/<날짜시각>-<명령>/` 에 저장됩니다:

- `summary.json` — 계획·지표·판정 (추이 비교용)
- `report.txt` — 화면 출력 그대로
- `report.html` — 인터랙티브 시계열 리포트 (부하 4종, 브라우저로 열기)
- `locust.log` — locust 원본 로그 (디버깅용)
- 엔진 원본 — Locust CSV, k6 JSON, 장애 구간 백엔드 로그 등

종료 코드: 종합 PASS=0, FAIL=1, 사전 점검 실패=2 (CI에서도 사용 가능).

## 필요한 외부 도구

- `docker` / `docker compose` — 컨테이너 점검·장애 주입
- `k6` — `testkit breakpoint` (백엔드 경로). 없으면 점검 단계에서 설치 링크 안내
- `hey` — `testkit breakpoint serverpool`. server-pool 이미지에 이미 포함
