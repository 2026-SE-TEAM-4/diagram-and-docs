# report-documentation

최종 **docx 보고서**가 만들어지는 곳. 디자인은 python-docx 스크립트로 구현한다.

확정 디자인: **A 기반 모던 학술형 · Pretendard · 네이비 `#1F3A5F`**
상세 스펙: `../docs-web/docs/superpowers/specs/2026-06-13-report-docx-design.md`

## 구성

| 파일 | 역할 |
|---|---|
| `report_style.py` | 디자인 토큰(색·글꼴)과 빌더 헬퍼 — 표지·목차·제목·표·캡션·머리말/꼬리말 |
| `build_report.py` | 문서 조립 — 표지 → 목차 → 디자인 데모(제Ⅵ장 일부) |
| `서버예약할당관리시스템_보고서_초안.docx` | 생성물(초안) |

## 생성

```bash
cd report-documentation
python3 build_report.py          # docx 재생성
```

의존성: `python-docx`. 미설치 시 `uv pip install python-docx` 또는 `pip install python-docx`.

## 미리보기(헤드리스 렌더)

```bash
soffice --headless --convert-to pdf --outdir /tmp "서버예약할당관리시스템_보고서_초안.docx"
```

## 현재 범위 (초안)

- ✅ 표지 · 목차 · 디자인 시스템(제목/표/캡션/머리말·꼬리말)
- ⬜ 12장 본문 — 다음 단계에서 `report-outline.md`·설계 문서를 옮겨 채움
- 목차 페이지 번호는 **자리표시 추정치**(본문 확정 후 갱신)
- 팀원 이름·정확한 제출일은 자리표시(`○○○`) — `build_report.py` 상단 상수에서 교체

## 폰트

Pretendard 설치 환경에서 의도대로 렌더된다. 미설치 환경 배포 시 글꼴 임베드는 다음 단계 검토.
