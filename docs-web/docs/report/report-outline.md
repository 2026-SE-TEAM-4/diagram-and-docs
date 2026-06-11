# 보고서 목차 추천

이전 학번 보고서 2종(Sommerville 교재 흐름의 9장 구조)과 2026 평가표(10항목×3점 + 리스크 + 느낀점)를 비교 분석해 도출한 목차다. 전통 흐름을 뼈대로 하되, 평가표에서 새로 비중이 커진 **상세설계·SOLID·디자인패턴을 독립 장으로 격상**한 것이 핵심이다 — 이전 보고서들에는 이 내용이 거의 없어, 그대로 벤치마킹하면 12점(4항목)을 놓친다.

각 장의 [E-xx]는 [평가 체크리스트](./evaluation-checklist.md)의 평가 항목 번호다.

## 목차와 장별 구성

| 장 | 제목 | 평가 매핑 | 핵심 재료 (본 저장소) |
|---|---|---|---|
| Ⅰ | 개발 목표, 배경 및 필요성 | E-01·02 | [프로젝트 개요](../01-overview/project-overview.md), [NFR](../02-requirements/nfr.md) 정량 목표 |
| Ⅱ | 유사 시스템 사례 수집·분석 | E-02 | 신규 작성 — Slurm·Run:ai·K8s 스케줄러 등 4건+, 문제점/해결/결과/향후과제 표 (이전 보고서 양식) |
| Ⅲ | 개발 프로세스·프로젝트 계획 | (기본) | [프로젝트 계획서](../01-overview/project-plan.md), Agile 스토리보드(team-4-agile.xlsx), 위험분석 |
| Ⅳ | 요구사항 분석 | E-03 | [UC 23 명세](../02-requirements/use-cases.md)·유스케이스 다이어그램, [기능·API 명세](../02-requirements/features-and-apis.md), [NFR](../02-requirements/nfr.md), UC→F→API 추적성 매트릭스 |
| Ⅴ | 아키텍처 분석·전략설계 | E-04·05 | [시스템 아키텍처](../03-architecture/architecture.md) — 구성 스타일(저장소 모델)/모듈 분해(객체지향+3계층)/제어 스타일(이벤트+주기) "선정+사유", architecture.drawio |
| Ⅵ | 상세설계 — 정적 모델 | E-06 | [ERD](../04-design/data-model.md)(erd.drawio), [백엔드 설계 §1~2](../04-design/backend-design.md)(class-diagram.drawio) |
| Ⅶ | 상세설계 — 자료구조·알고리즘 | E-07 | [동적 모델](../04-design/dynamic-models.md)(state-diagrams·sequence-reservation.drawio), [백엔드 설계 §5](../04-design/backend-design.md) 의사코드, [AIOps](../04-design/ai-ops.md), [서버 풀](../03-architecture/serverpool-spec.md) 수집 알고리즘 |
| Ⅷ | SOLID 원칙 적용 | E-08 | [백엔드 설계 §3](../04-design/backend-design.md) — 원칙별 실코드 발췌(파일:줄) |
| Ⅸ | 디자인 패턴 적용 | E-09 | [백엔드 설계 §4](../04-design/backend-design.md) — 패턴명/의도/위치/효과 표 + 설명 |
| Ⅹ | 테스트 | E-10 | [테스트 계획서](../05-testing/test-plan.md) + testkit(test-tool/) **실측 결과 그래프** — 부하·스파이크·중단점·장애 주입 |
| Ⅺ | 구현 결과 | E-10 | 레포 4개 구성, 백엔드 API 6도메인·스케줄러 잡, server-pool 에이전트, 프론트 시안(frontend-design/) 스크린샷, git 이력 |
| Ⅻ | 리스크 및 느낀점 | 필수 별도 | [체크리스트 §2~3](./evaluation-checklist.md) — 리스크 4건 후보, 팀원 전원 느낀점 |
| 부록 | 추적성 매트릭스·전체 UC/API 명세·ADR | E-10 | features-and-apis.md, dynamic-models.md ADR |

## 작성 순서 추천

1. **Ⅵ~Ⅸ 먼저** (배점 12점, 재료 완비) — backend-design.md와 다이어그램을 보고서 형식으로 옮기기
2. **Ⅹ** — testkit 실측 돌려서 그래프 확보 (다른 조와 차별화되는 "노력의 흔적")
3. **Ⅱ** — 유일한 신규 조사 작업
4. Ⅰ·Ⅲ~Ⅴ — 기존 문서 요약 정리
5. Ⅺ~Ⅻ·부록 — 마지막에 취합

## 플러스 포인트 전략 (E-10 "노력의 흔적")

상호평가에서 빠르게 훑어도 노력이 보이는 4가지를 전면 배치:

1. **실측 테스트 그래프** — 계획만 있는 조 vs 직접 CLI를 만들어 수치를 가진 조
2. **추적성 매트릭스 한 장** — UC → 기능 → API → 코드 → 테스트
3. **직접 만든 testkit CLI** — 사전 점검→계획→실행→리포트 4단계 출력 화면
4. **운영 증빙** — Agile 스토리보드, 노션 워크스페이스, git PR 흐름 캡처
