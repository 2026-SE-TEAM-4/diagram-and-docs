# 다이어그램 안내

시스템의 모든 다이어그램 원본(drawio)을 이 디렉토리에 모은다. [draw.io](https://app.diagrams.net/)에서 열어 편집하고, 보고서·문서에 넣을 때는 PNG/SVG로 내보낸다(File → Export as).

| 파일 | 내용 | 관련 문서 |
|---|---|---|
| `architecture.drawio` | 시스템 아키텍처 — Frontend·FastAPI·APScheduler·PostgreSQL·Redis·서버 풀·CI/CD 구성과 데이터 흐름 | [시스템 아키텍처](../docs/03-architecture/architecture.md) |
| `erd.drawio` | ERD — 13개 엔티티와 관계(카디널리티 포함) | [데이터 모델](../docs/04-design/data-model.md) |
| `class-diagram.drawio` | 백엔드 클래스/모듈 다이어그램 — api·core·services·models·jobs 레이어와 의존 관계 | [백엔드 설계](../docs/04-design/backend-design.md) |
| `state-diagrams.drawio` | 상태 다이어그램 2탭 — Server 상태머신 · Reservation 생애주기 | [동적 모델](../docs/04-design/dynamic-models.md) |
| `sequence-reservation.drawio` | 예약 생성(UC04) 시퀀스 — 낙관적 잠금 성공/충돌 분기 포함 | [동적 모델](../docs/04-design/dynamic-models.md) |
| `use-case-diagram.drawio` | 유스케이스 다이어그램 — 액터 5 · UC 23 | [유스케이스 명세서](../docs/02-requirements/use-cases.md) |

프론트엔드 정보구조(IA) 다이어그램은 시안과 함께 별도 레포 `frontend-design`(`frontend-ia.drawio`)에 있다.

내보낸 이미지(PNG)는 `assets/`에 두고 문서에서 상대 경로로 참조한다. 현재 `assets/architecture-diagram.png`, `assets/runtime-diagram.png`가 이 방식으로 쓰인다.
