// 문서 목록 단일 원본 — 상단 탭·사이드바·홈 카드가 이 객체에서 생성된다.
// path는 index.html 기준 상대 경로. md 파일을 추가하면 해당 탭에 한 줄만 더하면 된다.
window.DOCS_MANIFEST = {
  site: {
    title: "서버 예약·할당 관리 시스템",
    subtitle: "소프트웨어공학 (01) · 4조 · 2026-1",
  },
  tabs: [
    {
      id: "design",
      title: "설계 문서",
      categories: [
        {
          no: "01",
          title: "개요 · 계획",
          items: [
            { title: "프로젝트 개요", path: "docs/01-overview/project-overview.md" },
            { title: "프로젝트 계획서", path: "docs/01-overview/project-plan.md" },
            { title: "기술 스택", path: "docs/01-overview/tech-stack.md" },
          ],
        },
        {
          no: "02",
          title: "요구사항",
          items: [
            { title: "유스케이스 명세서", path: "docs/02-requirements/use-cases.md" },
            { title: "기능 · API 명세", path: "docs/02-requirements/features-and-apis.md" },
            { title: "비기능 요구사항 (NFR)", path: "docs/02-requirements/nfr.md" },
          ],
        },
        {
          no: "03",
          title: "아키텍처",
          items: [
            { title: "시스템 아키텍처", path: "docs/03-architecture/architecture.md" },
            { title: "서버 풀 명세서", path: "docs/03-architecture/serverpool-spec.md" },
          ],
        },
        {
          no: "04",
          title: "상세설계",
          items: [
            { title: "데이터 모델 (ERD)", path: "docs/04-design/data-model.md" },
            { title: "동적 모델 (상태도·시퀀스)", path: "docs/04-design/dynamic-models.md" },
            { title: "백엔드 설계 — 클래스·SOLID·패턴", path: "docs/04-design/backend-design.md" },
            { title: "AIOps 기능 설계", path: "docs/04-design/ai-ops.md" },
            { title: "보안 관제·경고 설계", path: "docs/04-design/security-monitoring.md" },
          ],
        },
        {
          no: "05",
          title: "테스트",
          items: [
            { title: "테스트 계획서", path: "docs/05-testing/test-plan.md" },
          ],
        },
        {
          no: "06",
          title: "다이어그램",
          items: [
            { title: "다이어그램 안내 (drawio)", path: "diagrams/README.md" },
          ],
        },
      ],
    },
    {
      id: "screens",
      title: "화면 설계",
      categories: [
        {
          no: "UI",
          title: "프론트엔드",
          items: [
            { title: "화면 설계 (역할별 시안)", path: "docs/06-screens/screen-design.md" },
          ],
        },
      ],
    },
    {
      id: "checklist",
      title: "평가 체크리스트",
      categories: [
        {
          no: "EV",
          title: "평가 대비",
          items: [
            { title: "평가 체크리스트", path: "docs/report/evaluation-checklist.md" },
          ],
        },
      ],
    },
    {
      id: "outline",
      title: "보고서 목차 추천",
      categories: [
        {
          no: "RP",
          title: "보고서",
          items: [
            { title: "보고서 목차 추천", path: "docs/report/report-outline.md" },
          ],
        },
      ],
    },
  ],
};
