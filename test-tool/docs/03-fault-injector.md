# 03. 장애 주입·복원 검증 — `testkit fault s1~s5`

> testkit 공통 구조는 [00-testkit-cli.md](./00-testkit-cli.md) 참조. 이 문서는 장애 주입 명령의 설계만 다룹니다.

## 목적

일부러 장애를 일으킨 뒤 ① 백엔드가 장애를 **감지**하는지, ② 복구 후 **데이터 무손실**인지를 자동 검증합니다.
server-pool은 처음부터 "장애는 외부 docker 명령으로 주입한다"는 설계라 이 도구의 최적 대상입니다.

- 담당 테스트: 계획서 3.2 복원
- 구현: 별도 bash 스크립트가 아니라 **testkit의 서브커맨드**로 통합(다듬어진 출력이 요구사항이므로). docker 호출은 파이썬 subprocess 한 줄이라 손해가 없습니다.

## 명령

```text
testkit fault s1      # 에이전트 정지 (연결 거부 경로)
testkit fault s2      # 에이전트 멈춤 (pause — 타임아웃 경로)
testkit fault s3      # PostgreSQL 재시작
testkit fault s4      # Redis 재시작
testkit fault s5      # 에이전트 과부하 (stress-ng, 부분 장애)
testkit fault all     # s1~s5 순차 + 종합 요약
```

## 관련 파일

```text
testing/testkit/commands/fault.py   # 시나리오 5종 + 공통 5단계 헬퍼
```

## 동작 흐름 (모든 시나리오 공통 5단계)

```text
1. snapshot_before : 예약 목록·쿼터 값을 API로 떠서 저장
2. inject          : docker stop/pause/restart 로 장애 주입
3. expect_detect   : 백엔드 API를 N초간 폴링하며 기대 상태 확인 (poll_until)
4. recover         : docker start/unpause 로 복구 → 정상 복귀 폴링
5. verify_data     : snapshot_after 를 떠서 before와 비교 → 무손실 검증
```

## 핵심 설계

### 컨테이너 이름 해석

컨테이너 이름은 compose 프로젝트 접두사가 붙습니다(`server-pool-agent-3-1`, `backend-api-1`). 그래서 모든 시나리오는 **`docker ps`에서 부분 일치로 실제 이름을 찾아** 사용합니다.

### 공통 헬퍼 (`fault.py` 안에)

```text
poll_until(timeout, 설명, 조건함수)  : 조건이 참이 될 때까지 2초 간격 폴링,
                                       제한시간 초과 시 ✖ + 소요시간 기록
snapshot()                          : 예약·쿼터를 ADM/시드 토큰으로 떠서 dict 반환
docker_stop/start/pause/unpause/restart/exec_stress
```

### 대표 시나리오 — s1 (에이전트 정지)

```text
snapshot_before
docker stop <agent-3 실제이름>
poll_until(90초, "agent-3가 MISSING으로 표시됨", 서버상태==MISSING)
docker start <agent-3>
poll_until(90초, "정상 상태로 복귀", 서버상태 in AVAILABLE/RESERVED/IN_USE)
snapshot_after → 예약·쿼터 불변 검증
```

> **중요(설계상 발견 예정)**: 백엔드의 "서버를 MISSING으로 바꾸는 로직"은 설계만 되어 있고 **아직 미구현**입니다.
> 그래서 s1/s2의 감지 폴링이 끝까지 MISSING으로 안 바뀔 수 있는데, 이건 도구의 오류가 아니라 **"감지 로직 미구현"이라는 발견(FINDING)**으로 보고합니다. 복원 테스트의 가치가 바로 이런 공백을 드러내는 것입니다.

s2(pause)는 stop을 pause/unpause로 바꾼 것. **연결 거부(즉시 에러)와 타임아웃(응답 없음)은 백엔드에서 다른 코드 경로**이고, 백엔드에 명시적 타임아웃이 없어 수집기가 무한 대기할 가능성이 있습니다(이 약점이 드러나면 그 자체가 수확).

### DB/Redis 시나리오 — s3·s4

```text
docker restart <postgres 또는 redis>
다운 중: /reservations 호출 → 5xx 허용, 프로세스 다운은 불허
복구 후: poll_until(60초, "API 정상 응답 복귀", /health==200)
핵심 질문: 백엔드가 재연결하는가, 죽은 커넥션을 물고 계속 실패하는가
```

### 부분 장애 — s5 (stress-ng)

```text
docker exec <agent-3> stress-ng --cpu 4 --timeout 120s
→ /metrics(9103)가 계속 응답하는지, cpuUsage가 실제로 높게 보고되는지 확인
```

### 조용히 삼켜지는 예외 대비

백엔드 스케줄러는 예외를 조용히 삼키는 구조라, 장애가 API에 안 나타나고 로그에만 남을 수 있습니다. 그래서 주입~복구 구간의 백엔드 로그를 함께 수집합니다: `docker logs <api> --since <시각> → backend-during-fault.log`.

## 실행 방법

```bash
cd testing
uv run testkit seed
uv run testkit fault s1      # 개별
uv run testkit fault all     # 전체 (약 15분)
```

## 산출물과 합격 판정

| 시나리오 | 판정 |
| :--- | :--- |
| s1 agent stop | 90초 내 MISSING 표시(현재는 미구현 → FINDING) + 복구 후 데이터 무손실 |
| s2 agent pause | 타임아웃 경로에서도 멈추지 않고 감지 / 무한 대기 여부 관찰 |
| s3·s4 DB·Redis 재시작 | 프로세스 다운 없음 + 60초 내 API 정상 + 데이터 무손실 |
| s5 부분 장애 | 메트릭 수집 지속 + 높은 CPU가 정확히 보고됨 |

판정은 PASS / FAIL / **FINDING**(미구현·약점 발견) 3종으로 출력하고, `all`은 종합 요약표를 만듭니다.

## 구현 순서

1. 공통 헬퍼(poll_until / snapshot / docker_*)
2. s1 (가장 단순하고 설계 의도가 명확)
3. s2 (타임아웃 경로 — 약점 발견 가능성 최고)
4. s3/s4 DB·Redis
5. s5 stress-ng + `all` 묶기
