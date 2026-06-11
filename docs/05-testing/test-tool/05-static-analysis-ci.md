# 05. 정적 분석 · 회귀 CI 파이프라인

## 목적

코드를 실행하지 않고 잡을 수 있는 결함(린트·타입·보안 패턴·취약 의존성)을 자동화하고,
회귀 테스트(pytest 스위트)와 함께 **매 PR마다 자동 실행**되게 묶습니다. "상시 실행" 항목이므로 사람이 기억할 필요가 없어야 합니다.

- 담당 테스트: 계획서 4.2 정적 분석 / 3.3 회귀(CI 자동화 부분)
- 도구: `ruff`(린트+포맷) · `mypy`(타입) · `bandit`(보안 패턴) · `pip-audit`(의존성 취약점)

## 구성

```text
backend/pyproject.toml        # 도구 설정을 한 파일에 모음 (ruff, mypy 섹션)
server-pool/pyproject.toml    # 동일 구성 (대상 경로만 다름)
.github/workflows/ci.yml      # PR마다: 정적 분석 → 단위 → 통합 순서
```

### 1) 도구 설정 — `pyproject.toml`

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]   # 기본 + import 정렬 + 버그 패턴

[tool.mypy]
python_version = "3.12"
strict = false                # 처음엔 느슨하게 시작, 통과하면 단계적으로 강화
ignore_missing_imports = true
```

bandit은 별도 설정 없이 실행하되, 테스트 코드의 `assert` 경고(B101)만 제외합니다:
`bandit -r app -x tests`

### 2) 검사 항목과 우리 시스템에서 기대하는 효과

| 도구 | 명령 | 우리 코드에서 잡아줄 것 |
| :--- | :--- | :--- |
| ruff | `ruff check . && ruff format --check .` | 미사용 변수(예: 정의만 된 `quota.version`), import 누락, 버그 패턴(B계열) |
| mypy | `mypy app` | 스키마↔서비스 간 타입 불일치, Optional 미처리 |
| bandit | `bandit -r app -x tests` | 하드코딩 시크릿(기본 `JWT_SECRET` 등), 취약 패턴 |
| pip-audit | `pip-audit` | 의존성의 알려진 CVE |

### 3) CI 워크플로 — `.github/workflows/ci.yml`

빠른 검사를 앞에 둬서 실패를 일찍 알립니다. 정적 분석(수십 초) → 단위(수 초) → 통합(수 분, testcontainers).

```yaml
name: ci
on: [pull_request, push]

jobs:
  static:
    runs-on: ubuntu-latest
    strategy:
      matrix: { repo: [backend, server-pool] }
    steps:
      - uses: actions/checkout@v4
      - run: pip install uv && uv sync          # working-directory: ${{ matrix.repo }}
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run mypy app                    # server-pool은 agent
      - run: uv run bandit -r app -x tests
      - run: uv run pip-audit

  unit:
    needs: static
    steps:
      - run: uv run pytest tests/unit -v

  integration:        # 회귀 테스트 본체 (retest-all)
    needs: unit
    steps:
      - run: uv run pytest tests/integration -m integration
      - run: uv run pytest tests --cov=app/services --cov-branch --cov-fail-under=80
```

> GitHub Actions 러너는 docker를 기본 제공하므로 testcontainers가 그대로 동작합니다.

### 4) 회귀 테스트 운영 규칙 (교재 5유형 → 우리 흐름)

| 교재 유형 | 우리 운영 |
| :--- | :--- |
| 선택적 회귀 | 로컬에서 개발 중: `pytest -k <변경 모듈>` 만 빠르게 |
| 수정 회귀 | 버그 수정 PR: CI가 전체 스위트 자동 실행 |
| 전체 재테스트 | 핵심 로직(예약/쿼터) 변경·릴리스 전: CI 전체 + 커버리지 게이트 |
| 점진적 회귀 | 새 기능 추가 시 신규 테스트를 스위트에 통합 (04 문서의 파일 구조 따름) |
| 부분 회귀 | 경미한 수정: 로컬 `pytest -k` + CI는 어차피 전체 실행 |

### 5) 로컬에서 PR 전에 한 번에 돌리기

```bash
# backend/scripts/check.sh (server-pool에도 동일하게)
set -e
ruff check . && ruff format --check .
mypy app
bandit -r app -x tests -q
pip-audit
pytest tests/unit -q
echo "정적 분석 + 단위 테스트 통과. 통합 테스트는 CI 또는 pytest tests/integration"
```

## 합격 판정

- ruff·mypy·bandit 위반 0건 (도입 직후 기존 위반은 일괄 수정하거나 명시적 예외 주석으로 기록)
- pip-audit 알려진 취약 의존성 0건
- 회귀: 전체 스위트 통과 + `--cov-fail-under=80` (핵심 서비스 모듈 기준)

## 구현 순서

1. `pyproject.toml`에 ruff·mypy 설정 추가 → 로컬에서 돌려 기존 위반 정리
2. `check.sh` 스크립트 (CI 없이도 팀원이 바로 사용 가능)
3. `ci.yml` — static 잡부터 올리고, 통과하면 unit → integration 추가
4. 커버리지 게이트(`--cov-fail-under=80`)는 04 문서의 테스트 보강이 끝난 뒤에 켬 (지금 켜면 항상 실패)
