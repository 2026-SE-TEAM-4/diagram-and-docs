# testkit — 팀 공용 테스트 CLI

부하·중단점·장애 테스트를 명령 한 줄로 돌리는 도구입니다.
모든 명령이 **사전 점검 → 테스트 계획 → 실행 → 다듬어진 결과** 4단계를 같은 모양으로 출력합니다.

설계 문서: `../diagram-and-docs/test-tool/` (00이 전체 구조, 01~03이 각 명령).

## 준비

```bash
# 1) 백엔드 + server-pool 컨테이너 기동
cd ../backend     && docker compose up -d
cd ../server-pool && docker compose up -d

# 2) testkit 의존성 설치
cd ../testing && uv sync
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

uv run testkit breakpoint login       # 중단점 (login|reserve|read|serverpool)
uv run testkit fault s1               # 장애 주입 (s1~s5|all)
uv run testkit verify                 # DB 정합성 검사만 단독 실행
```

## 결과

`testing/results/<날짜시각>-<명령>/` 에 저장됩니다:

- `summary.json` — 계획·지표·판정 (추이 비교용)
- `report.txt` — 화면 출력 그대로
- 엔진 원본 — Locust CSV, k6 JSON, 장애 구간 백엔드 로그 등

종료 코드: 종합 PASS=0, FAIL=1, 사전 점검 실패=2 (CI에서도 사용 가능).

## 필요한 외부 도구

- `docker` / `docker compose` — 컨테이너 점검·장애 주입
- `k6` — `testkit breakpoint` (백엔드 경로). 없으면 점검 단계에서 설치 링크 안내
- `hey` — `testkit breakpoint serverpool`. server-pool 이미지에 이미 포함
