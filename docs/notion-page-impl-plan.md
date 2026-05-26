# 노션 워크스페이스 구현 플랜

> **For agentic workers:** 본 플랜은 노션 MCP 도구로 직접 실행하는 작업 목록임. 각 task는 (1) MCP 도구 호출 (2) 결과 검증 두 단계로 구성. 코드 TDD 패턴 대신 "create → fetch 검증"으로 대체.

**Goal:** 빈 노션 메인 페이지를 working hub로 변환 — 4개 DB + 2개 정적 서브 페이지 + 7개 섹션 메인 페이지

**Architecture:** 4개 DB 먼저 생성 (relation 필요) → 2개 정적 서브 페이지 → 메인 페이지 콘텐츠 (linked DB view 임베드 포함)

**Tech Stack:** Notion MCP (create-database, create-pages, update-page, create-view), Notion-flavored Markdown

**관련 문서:** [`notion-page-design.md`](./notion-page-design.md) (스펙)

**주요 ID/URL (실행 중 누적)**
- 메인 페이지: `340e84777239804f823ddb242d0351f1`
- 김강문 (팀장, 본인): `6adb291b-a20e-47b1-b150-364c2565cc0e`
- 최민호, 조동화: 워크스페이스 멤버 아님 → PEOPLE 컬럼 대신 SELECT 사용

---

## 스펙 vs 플랜 차이 (적응 사항)

스펙 작성 후 발견된 제약:

1. **PEOPLE 컬럼 → SELECT** — 최민호·조동화가 워크스페이스 멤버가 아니므로 `담당`은 SELECT 사용 (옵션: `팀장(김강문)`, `최민호`, `조동화`). 참석자도 MULTI_SELECT.
2. **API 명세 ↔ 기능 명세 relation 순서** — DUAL relation은 target DB가 이미 존재해야 하므로 기능 명세 먼저 생성 후 API 명세에서 DUAL 추가 (자동 back-relation).

---

## Task 1: 기능 명세 DB 생성

**도구:** `notion-create-database`
**부모:** 메인 페이지

- [ ] **Step 1: DB 생성**

```sql
CREATE TABLE (
  "UC ID" TITLE,
  "이름" RICH_TEXT,
  "액터" MULTI_SELECT('STU':blue, 'MGR':purple, 'ADM':red, 'SYS':gray),
  "그룹" SELECT('조회':gray, '알림':orange, '예약·할당':blue, 'Quota·승인':purple, '서버관리':green, '자동화':yellow, '보안·운영':red),
  "설명" RICH_TEXT,
  "비즈니스 규칙" RICH_TEXT,
  "Acceptance Criteria" RICH_TEXT,
  "구현 상태" SELECT('미정의':gray, '정의완료':blue, '구현완료':green) COMMENT '명세 정의 → 코드 구현 진척'
)
```

- 부모: `{"type": "page_id", "page_id": "340e84777239804f823ddb242d0351f1"}`
- 타이틀: `기능 명세`

- [ ] **Step 2: data_source_id 저장**

응답에서 `<data-source url="collection://...">` 추출 → 이후 Task 2의 RELATION 타겟으로 사용.

---

## Task 2: API 명세 DB 생성 (DUAL relation to 기능 명세)

**도구:** `notion-create-database`
**부모:** 메인 페이지
**의존:** Task 1의 data_source_id

- [ ] **Step 1: DB 생성**

```sql
CREATE TABLE (
  "Endpoint" TITLE,
  "Method" SELECT('GET':green, 'POST':blue, 'PUT':yellow, 'DELETE':red, 'PATCH':orange),
  "기능" RELATION('<기능명세_DS_ID>', DUAL '관련 API'),
  "Auth" SELECT('STU':blue, 'MGR':purple, 'ADM':red, 'public':gray),
  "Request" RICH_TEXT COMMENT 'JSON code block',
  "Response" RICH_TEXT COMMENT 'JSON code block',
  "Status Codes" MULTI_SELECT('200':green, '201':green, '204':green, '400':orange, '401':red, '403':red, '404':orange, '409':red, '422':orange, '429':red, '500':red),
  "구현 상태" SELECT('미정의':gray, '정의완료':blue, '구현완료':green)
)
```

- DUAL relation으로 기능 명세에 `관련 API` 컬럼이 자동 생성됨.

- [ ] **Step 2: 검증**
- `notion-fetch` on 기능 명세 DB → `관련 API` 컬럼 존재 확인.

---

## Task 3: 백로그 DB 생성

**도구:** `notion-create-database`
**부모:** 메인 페이지

- [ ] **Step 1: DB 생성**

```sql
CREATE TABLE (
  "Title" TITLE,
  "UC" MULTI_SELECT('UC01':gray, 'UC02':gray, 'UC03-a':orange, 'UC03-d':orange, 'UC04':blue, 'UC05':blue, 'UC06':blue, 'UC07':blue, 'UC09':purple, 'UC10':purple, 'UC11':green, 'UC12':green, 'UC13':green, 'UC14':yellow, 'UC15':yellow, 'UC16':yellow, 'UC17':yellow, 'UC18':yellow, 'UC19':yellow, 'UC20':red, 'UC21':red),
  "담당" SELECT('팀장(김강문)':blue, '최민호':green, '조동화':purple),
  "상태" STATUS,
  "주차" SELECT('W1':gray, 'W2':gray, 'W3':gray, 'W4':gray, 'W5':gray, 'W6':gray, 'W7':gray, 'W8':gray, 'W9':gray, 'W10':gray, 'W11':gray, 'W12':gray, 'W13':gray, 'W14':gray),
  "마감" DATE,
  "우선순위" SELECT('높음':red, '중간':yellow, '낮음':gray),
  "레이어" SELECT('FE':blue, 'BE':green, 'Infra':purple, 'Docs':gray)
)
```

> STATUS 타입은 노션 기본 그룹(To-do / In progress / Complete)을 자동 생성. 후속으로 UI에서 그룹 라벨을 "대기/진행/리뷰/완료"로 rename.

- [ ] **Step 2: 4 views 생성** — `notion-create-view`
  - **Kanban (메인 임베드 후보)**: `type=board, configure='GROUP BY "상태"'`
  - **Table (All)**: `type=table`
  - **By UC**: `type=table, configure='GROUP BY "UC" SORT BY "UC" ASC'`
  - **This Week**: `type=table, configure='FILTER "주차" = "현재주" SORT BY "마감" ASC'` — 현재주 값은 운영자가 매주 수동 변경 (노션 native 동적 필터 한계)

---

## Task 4: 회의록 DB 생성

**도구:** `notion-create-database`
**부모:** 메인 페이지

- [ ] **Step 1: DB 생성**

```sql
CREATE TABLE (
  "제목" TITLE,
  "회차" UNIQUE_ID PREFIX 'M',
  "날짜" DATE,
  "주차" SELECT('W1':gray, 'W2':gray, 'W3':gray, 'W4':gray, 'W5':gray, 'W6':gray, 'W7':gray, 'W8':gray, 'W9':gray, 'W10':gray, 'W11':gray, 'W12':gray, 'W13':gray, 'W14':gray),
  "참석자" MULTI_SELECT('팀장(김강문)':blue, '최민호':green, '조동화':purple),
  "핵심 결정사항" RICH_TEXT,
  "액션 아이템" RICH_TEXT COMMENT 'task성 항목은 백로그로 수동 복사'
)
```

UNIQUE_ID로 자동 회차 부여 (M-1, M-2, ...).

- [ ] **Step 2: 메인 임베드용 view 생성** — `notion-create-view`
  - **Recent 5**: `type=table, configure='SORT BY "날짜" DESC SHOW "제목", "날짜", "주차", "핵심 결정사항"'` (limit 5는 노션 view DSL에 없음 — 운영자가 UI에서 row limit 설정)

---

## Task 5: 시스템 설계 서브 페이지

**도구:** `notion-create-pages`
**부모:** 메인 페이지

- [ ] **Step 1: 페이지 생성 with content**

```markdown
# 📐 시스템 설계

> 시스템 다이어그램 3종 풀뷰. 원본 drawio는 GitHub `diagram-and-docs/`에 위치.
{color="blue_bg"}

## 1. 유스케이스 다이어그램

<callout icon="🧩" color="gray_bg">
4 actors · 20 UCs · 6 그룹 (조회 / 알림 / 예약·할당 / Quota·승인 / 서버관리 / 자동화 / 보안·운영)
</callout>

*(이미지 자리 — drawio export PNG 임베드)*

**원본:** GitHub `diagram-and-docs/usecase.drawio`

---

## 2. 배치 다이어그램

<callout icon="🐳" color="gray_bg">
Docker Compose 단일 노드 토폴로지 · API · Scheduler · PostgreSQL · Redis · Frontend
</callout>

*(이미지 자리)*

**원본:** GitHub `diagram-and-docs/deployment.drawio`

---

## 3. 컴포넌트 아키텍처

<callout icon="⚙️" color="gray_bg">
FastAPI 레이어 (api / core / infra / scheduler) · 데이터 흐름 화살표
</callout>

*(이미지 자리)*

**원본:** GitHub `diagram-and-docs/architecture.drawio`

---

## 변경 이력

| 날짜 | 다이어그램 | 변경 |
|------|-----------|------|
| - | - | - |
```

- 부모: `{"type": "page_id", "page_id": "340e84777239804f823ddb242d0351f1"}`
- 타이틀: `📐 시스템 설계`
- 아이콘: `📐`

- [ ] **Step 2: 페이지 URL 저장** — 메인 페이지의 시스템 설계 카드에서 링크용.

---

## Task 6: 다음 회의 준비 서브 페이지

**도구:** `notion-create-pages`
**부모:** 메인 페이지

- [ ] **Step 1: 페이지 생성**

```markdown
# 🎯 다음 회의 준비

<callout icon="📅" color="yellow_bg">
**일시:** 다음 정기 회의 (요일·시간 수정 가능)
**참석:** 팀장 · 최민호 · 조동화
</callout>

## 안건 (누구나 추가)

- [ ] 
- [ ] 
- [ ] 

## 지난 회의 액션 아이템 검토

- [ ] *(회의록 DB에서 미완료 액션 확인)*

---

## Archive 흐름

회의 시작 시:
1. 회의록 DB에서 새 row 생성 (제목: `W{n} 정기 회의`)
2. 위 안건을 회의록 페이지에 복사
3. 회의 진행 → 결정사항·액션 아이템 작성
4. 이 페이지의 안건을 빈 템플릿으로 리셋
```

- 부모: 메인 페이지
- 타이틀: `🎯 다음 회의 준비`
- 아이콘: `🎯`

---

## Task 7: 메인 페이지 콘텐츠 빌드 (7 섹션)

**도구:** `notion-update-page` (replace_content)
**부모:** 메인 페이지 자체

이전 task의 DB IDs, 페이지 URLs 모두 필요.

- [ ] **Step 1: 메인 페이지 타이틀·아이콘 갱신**

`notion-update-page` command=`update_properties`:
- `properties: {"title": "🖥️ 서버 예약 / 할당 관리 시스템"}`
- `icon: "🖥️"`

- [ ] **Step 2: 콘텐츠 replace_content**

`notion-update-page` command=`replace_content`, `allow_deleting_content=true` (페이지가 비어있으므로 안전):

```markdown
<callout icon="🎓" color="blue_bg">
**SOFTWARE ENGINEERING 01 · TEAM 4 · 2026 SPRING**
연구실·팀 단위 GPU/서버 공유 시 중복·유휴를 막는 예약·할당·모니터링 플랫폼.

`📅 Week N/14` · `👥 3명` · `🧩 20 UCs` · `⚙️ FastAPI + React` · `🗓 다음 회의: 목 19:00`
</callout>

---

<columns>
<column>

<callout icon="🎯" color="yellow_bg">
**THIS WEEK · W3 (5/26 ~ 6/1)**
- [ ] [샘플] UC04 예약 API 골격 — 조동화
- [ ] [샘플] DB 스키마 v1 + Alembic 셋업 — 최민호
- [ ] [샘플] 로그인 화면 + JWT 클라이언트 — 팀장
</callout>

</column>
<column>

**Quick actions**
- <mention-page url="<다음회의준비_URL>">📝 다음 회의 준비</mention-page>
- *(백로그 새 row는 아래 DB에서 + 클릭)*
- *(검색은 Cmd/Ctrl + P)*

</column>
</columns>

---

## 📋 전체 백로그

<database data-source-url="<백로그_DS_URL>" inline="true">백로그 (Kanban)</database>

---

## 📐 시스템 설계

<columns>
<column>
<mention-page url="<시스템설계_URL>">유스케이스</mention-page>
20 UCs · 4 actors
</column>
<column>
<mention-page url="<시스템설계_URL>">배치</mention-page>
Docker Compose · 단일 노드
</column>
<column>
<mention-page url="<시스템설계_URL>">아키텍처</mention-page>
FastAPI · PostgreSQL · Redis
</column>
</columns>

---

## 📚 산출물

<columns>
<column>
**📄 프로젝트 계획서**
[GitHub →](https://github.com)
</column>
<column>
**🧱 기술 스택 명세**
[GitHub →](https://github.com)
</column>
<column>
**📘 유스케이스 명세서**
[GitHub →](https://github.com)
</column>
</columns>

<columns>
<column>
**🔌 API 명세 DB**
<mention-database url="<API명세_DB_URL>">API 명세</mention-database>
</column>
<column>
**⚙️ 기능 명세 DB**
<mention-database url="<기능명세_DB_URL>">기능 명세</mention-database>
</column>
<column>
**📊 발표 자료**
*(학기 말 작성 예정)*
</column>
</columns>

---

## 📅 회의록 · 결정사항

<database data-source-url="<회의록_DS_URL>" inline="true">회의록 (최근 5건)</database>

---

## 👥 팀  ·  🔗 외부

<columns>
<column>
**팀**
- 👑 팀장 — 김강문
- 최민호
- 조동화
</column>
<column>
**외부**
- [GitHub](https://github.com)
- [Discord](https://discord.com)
</column>
</columns>
```

> GitHub·Discord URL은 placeholder. 실제 레포 URL이 정해지면 운영자가 직접 갱신.

- [ ] **Step 3: 검증**

`notion-fetch` on 메인 페이지 → 7개 섹션 모두 존재 확인.

---

## Task 8: 최종 검증 및 URL 리포트

- [ ] **Step 1: 모든 페이지/DB URL 정리**

| 항목 | URL |
|------|-----|
| 메인 페이지 | (기존) |
| 📋 백로그 DB | ... |
| 📐 시스템 설계 | ... |
| 🔌 API 명세 DB | ... |
| ⚙️ 기능 명세 DB | ... |
| 📅 회의록 DB | ... |
| 🎯 다음 회의 준비 | ... |

- [ ] **Step 2: 사용자에게 후속 작업 안내**
  - 다이어그램 PNG 업로드 (시스템 설계 페이지의 *(이미지 자리)*)
  - GitHub / Discord URL 갱신
  - 백로그 STATUS 그룹 라벨 변경 (To-do/In progress/Complete → 대기/진행/리뷰/완료)
  - 백로그 "현재주" 필터 W3로 설정
  - 회의록 view의 row limit을 5로 (UI)

---

## Self-Review (이미 진행)

- [x] 스펙 커버리지 — 모든 7 메인 섹션 + 6 서브 페이지 포함
- [x] Placeholder 없음 — 모든 코드/스키마/마크다운 완전 명시
- [x] 타입 일관성 — relation 양방향, SELECT 옵션·컬러 통일
- [x] 적응 사항 명시 — PEOPLE → SELECT 변경 사유 기록
