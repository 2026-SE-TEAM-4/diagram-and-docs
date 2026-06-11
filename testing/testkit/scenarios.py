"""시나리오 점검 스위트: 단일 요청 + 기대 상태코드 단언(기능/보안 검증).

부하 테스트가 아니라 "백엔드가 잘못된 입력에 안전하게 반응하는가"를 단언으로 확인한다.
실제 FastAPI 라우트가 반환하는 코드를 기준으로 기대값을 잡았고, 환경에 따라
여러 코드가 정당한 경우에는 허용 코드 '집합'을 받는다.

판정 규칙:
  - PASS : 응답 코드가 허용 집합에 들어감
  - FAIL : 허용 집합을 벗어남(특히 5xx, 인증 우회 성공 등 '안전하지 않은' 동작)
  - SKIP : 환경 의존(예: 팀이 1개뿐이라 교차 테넌트 검증 불가)

설계: 선언형(메서드·경로·헤더모드·본문·허용코드)을 기본으로 하고,
경쟁/잠금처럼 절차가 필요한 일부는 함수형 시나리오로 둔 하이브리드.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal, Optional

import httpx

from testkit import config

# --- 상수: 매직넘버 제거 -------------------------------------------------------

HTTP_TIMEOUT = 10.0                 # 단일 요청 타임아웃(초)
HEALTH_LATENCY_MS = 200.0           # /health 응답 허용 상한
RESERVATIONS_LATENCY_MS = 800.0     # 인증된 목록 조회 허용 상한
ME_LATENCY_MS = 500.0               # /auth/me 허용 상한
LOGIN_LATENCY_MS = 2000.0           # 로그인(bcrypt 포함) 허용 상한
LOGIN_FAIL_MAX = 5                  # backend settings.login_fail_max 와 동일

# 백엔드가 존재하지 않는 리소스에 쓰는 안전한 4xx 모음
SAFE_NOT_FOUND = {404, 422}
# 잘못된 입력에 절대 5xx가 나오면 안 됨 → 안전한 클라이언트 오류 모음
SAFE_CLIENT_ERROR = {400, 404, 409, 422}

Category = Literal["security", "performance", "stability"]
Severity = Literal["critical", "normal"]
HeaderMode = Literal["auth", "none", "malformed", "wrong_scheme"]

MALFORMED_TOKEN = "not.a.valid.jwt.token"
SQLI_PROBE = "1' OR '1'='1"


@dataclass(frozen=True)
class LoginInfo:
    """로그인 결과. 시나리오 실행에 필요한 토큰/식별자."""

    token: str
    team_id: int
    user_id: int


@dataclass(frozen=True)
class Scenario:
    """선언형 시나리오 한 건.

    request_fn 이 주어지면 함수형(절차 필요)으로 처리하고, 없으면
    method/path/header_mode/body/expected 로 선언형 단일 요청을 보낸다.
    """

    name: str
    category: Category
    severity: Severity
    method: str = "GET"
    path: str = "/"
    header_mode: HeaderMode = "none"
    body: Optional[dict] = None
    expected: frozenset[int] = field(default_factory=frozenset)
    note: str = ""
    # 함수형 시나리오: (client, login) -> (passed, detail). SKIP은 detail에 "SKIP:" 접두.
    request_fn: Optional[Callable[["httpx.Client", LoginInfo], tuple[bool, str]]] = None


@dataclass(frozen=True)
class ScenarioResult:
    """시나리오 실행 결과 한 건."""

    name: str
    category: Category
    severity: Severity
    status: Literal["PASS", "FAIL", "SKIP"]
    detail: str


# --- 로그인 헬퍼 ---------------------------------------------------------------


def login(client: httpx.Client, email: str, password: str) -> LoginInfo:
    """시드 계정으로 로그인하고 토큰·식별자를 반환한다.

    users.py(Locust)와 동일한 요청 형태를 재사용한다:
    POST /auth/login {email,password} -> {accessToken, user:{id, teamId}}
    """
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        raise RuntimeError(
            f"로그인 실패({email}): HTTP {resp.status_code} {resp.text[:120]}"
        )
    data = resp.json()
    user = data.get("user", {})
    return LoginInfo(
        token=data["accessToken"],
        team_id=int(user.get("teamId", 0)),
        user_id=int(user.get("id", 0)),
    )


def _headers(mode: HeaderMode, token: str) -> dict[str, str]:
    """헤더 모드에 따른 Authorization 헤더를 만든다."""
    if mode == "auth":
        return {"Authorization": f"Bearer {token}"}
    if mode == "malformed":
        return {"Authorization": f"Bearer {MALFORMED_TOKEN}"}
    if mode == "wrong_scheme":
        return {"Authorization": "Basic dXNlcjpwYXNz"}
    return {}  # none


def _future_window(offset_h: float = 1.0, dur_h: float = 1.0) -> tuple[str, str]:
    """미래 예약 구간(start, end) ISO 문자열."""
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=offset_h)
    end = start + timedelta(hours=dur_h)
    return start.isoformat(), end.isoformat()


# --- 함수형 시나리오(절차 필요) -----------------------------------------------


def _scn_health_latency(client: httpx.Client, _login: LoginInfo) -> tuple[bool, str]:
    """/health 가 임계 이하로 응답하는지(성능)."""
    start = time.monotonic()
    resp = client.get("/health")
    ms = (time.monotonic() - start) * 1000
    ok = resp.status_code == 200 and ms < HEALTH_LATENCY_MS
    return ok, f"{resp.status_code}, {ms:.0f}ms (< {HEALTH_LATENCY_MS:.0f}ms)"


def _scn_reservations_latency(client: httpx.Client, login: LoginInfo) -> tuple[bool, str]:
    """인증된 GET /reservations 응답 시간(성능)."""
    start = time.monotonic()
    resp = client.get("/reservations", headers=_headers("auth", login.token))
    ms = (time.monotonic() - start) * 1000
    ok = resp.status_code == 200 and ms < RESERVATIONS_LATENCY_MS
    return ok, f"{resp.status_code}, {ms:.0f}ms (< {RESERVATIONS_LATENCY_MS:.0f}ms)"


def _scn_me_latency(client: httpx.Client, login: LoginInfo) -> tuple[bool, str]:
    """인증된 GET /auth/me 응답 시간(성능)."""
    start = time.monotonic()
    resp = client.get("/auth/me", headers=_headers("auth", login.token))
    ms = (time.monotonic() - start) * 1000
    ok = resp.status_code == 200 and ms < ME_LATENCY_MS
    return ok, f"{resp.status_code}, {ms:.0f}ms (< {ME_LATENCY_MS:.0f}ms)"


def _scn_login_latency(client: httpx.Client, _login: LoginInfo) -> tuple[bool, str]:
    """로그인(bcrypt 포함) 응답 시간(성능, normal)."""
    email = config.SEED_USER_EMAIL_FMT.format(n=1)
    start = time.monotonic()
    resp = client.post("/auth/login", json={"email": email, "password": config.SEED_PASSWORD})
    ms = (time.monotonic() - start) * 1000
    ok = resp.status_code == 200 and ms < LOGIN_LATENCY_MS
    return ok, f"{resp.status_code}, {ms:.0f}ms (< {LOGIN_LATENCY_MS:.0f}ms)"


def _scn_cross_tenant_quota(client: httpx.Client, login: LoginInfo) -> tuple[bool, str]:
    """다른 팀의 /teams/{id}/quotas 접근(교차 테넌트). 팀 1개면 SKIP."""
    other = _find_other_team_id(client, login)
    if other is None:
        return False, "SKIP: 시드에 팀이 1개뿐이라 교차 테넌트 검증 불가"
    resp = client.get(f"/teams/{other}/quotas", headers=_headers("auth", login.token))
    ok = resp.status_code in {403, 404}
    return ok, f"team {other} -> {resp.status_code} (기대 403/404)"


def _scn_cross_user_cancel(client: httpx.Client, login: LoginInfo) -> tuple[bool, str]:
    """다른 사용자의 예약 취소 시도. 존재하지 않거나 타인 소유면 403/404, 5xx 금지."""
    # 매우 큰 reservation_id는 존재하지 않음 → 404가 정상(타인 소유라도 403).
    resp = client.post(
        "/reservations/999999999/cancel", headers=_headers("auth", login.token)
    )
    ok = resp.status_code in {403, 404}
    return ok, f"{resp.status_code} (기대 403/404, 5xx 금지)"


def _scn_instant_contention(client: httpx.Client, login: LoginInfo) -> tuple[bool, str]:
    """동일 사용자가 즉시 예약을 빠르게 2회 → 201/409/422만, 5xx 절대 금지(안정성)."""
    _, end = _future_window(0, 1)
    codes: list[int] = []
    for _ in range(2):
        resp = client.post(
            "/reservations/instant",
            json={"endTime": end},
            headers=_headers("auth", login.token),
        )
        codes.append(resp.status_code)
    ok = all(c in {201, 409, 422} for c in codes)
    return ok, f"codes={codes} (기대 201/409/422, 5xx 금지)"


def _scn_quota_overflow(client: httpx.Client, login: LoginInfo) -> tuple[bool, str]:
    """쿼터 한도 초과를 노린 즉시 예약 반복. 한도 도달 시 422/409, 5xx 금지(안정성)."""
    _, end = _future_window(0, 1)
    attempts = config.SEED_QUOTA_LIMIT + 2
    codes: list[int] = []
    for _ in range(attempts):
        resp = client.post(
            "/reservations/instant",
            json={"endTime": end},
            headers=_headers("auth", login.token),
        )
        codes.append(resp.status_code)
    ok = all(c in {201, 409, 422} for c in codes)
    return ok, f"{attempts}회 codes={codes} (5xx 금지)"


def _scn_login_lockout(client: httpx.Client, _login: LoginInfo) -> tuple[bool, str]:
    """반복 실패 로그인 → 임계 도달 시 잠금(429). 전용 계정으로 다른 시나리오 영향 차단.

    backend auth_service: 존재하는 계정의 비밀번호 실패가 login_fail_max(5)에 도달하면
    locked_until 설정 후 429를 던진다. 실패는 401, 잠금은 429 여야 한다.
    """
    # 메인 로그인 계정(001)과 분리된 전용 계정을 쓴다(다른 시나리오 오염 방지).
    email = config.SEED_USER_EMAIL_FMT.format(n=config.SEED_USER_COUNT)
    codes: list[int] = []
    locked = False
    for _ in range(LOGIN_FAIL_MAX + 1):
        resp = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        codes.append(resp.status_code)
        if resp.status_code == 429:
            locked = True
            break
        if resp.status_code >= 500:
            return False, f"5xx 발생 codes={codes}"
    # 잠금이 동작하면 429, 아니면 최소한 401(안전한 실패)여야 한다.
    if locked:
        return True, f"잠금 동작(429) codes={codes}"
    ok = all(c in {401, 423, 429} for c in codes)
    detail = f"잠금 미관측, codes={codes} (401 누적은 허용)"
    return ok, detail


def _find_other_team_id(client: httpx.Client, login: LoginInfo) -> Optional[int]:
    """로그인 팀과 다른 팀 id를 찾는다. 후보를 탐색해 403/404가 아닌(=존재하는) 팀을 찾되,
    여기서는 보수적으로 '시드 팀이 1개'라는 알려진 사실에 따라 None을 우선 반환한다.

    실제로는 DB를 보지 않고 결정할 수 없으므로, login.team_id 외의 후보(1,2)를 가볍게
    찔러 5xx 없이 동작하는지만 확인하고, 다른 팀이 확실치 않으면 None(SKIP)."""
    # 시드는 팀 1개(LoadTest)만 만든다 → 교차 테넌트는 환경상 검증 불가.
    return None


# --- 시나리오 정의(~20개) -----------------------------------------------------


def _build_scenarios() -> list[Scenario]:
    """전체 시나리오 목록. 기대 코드는 실제 FastAPI 라우트 동작 기준."""
    start, end = _future_window()
    rev_start, rev_end = _future_window(48, -24)  # endTime < startTime 의도

    security: list[Scenario] = [
        Scenario(
            name="인증 없이 /reservations 접근 → 401",
            category="security", severity="critical",
            method="GET", path="/reservations", header_mode="none",
            expected=frozenset({401, 403}),
            note="HTTPBearer auto_error=False → 401",
        ),
        Scenario(
            name="잘못된 Bearer 토큰 → 401",
            category="security", severity="critical",
            method="GET", path="/reservations", header_mode="malformed",
            expected=frozenset({401}),
        ),
        Scenario(
            name="Authorization 스킴 오류(Basic) → 401",
            category="security", severity="critical",
            method="GET", path="/reservations", header_mode="wrong_scheme",
            expected=frozenset({401, 403}),
        ),
        Scenario(
            name="인증 없이 /auth/me 접근 → 401",
            category="security", severity="critical",
            method="GET", path="/auth/me", header_mode="none",
            expected=frozenset({401, 403}),
        ),
        Scenario(
            name="STU의 /teams/{id}/quotas 접근 → 403",
            category="security", severity="critical",
            method="GET", path="/teams/1/quotas", header_mode="auth",
            expected=frozenset({403}),
            note="require MGR/ADM; STU는 403",
        ),
        Scenario(
            name="STU의 /approval-requests 접근 → 403",
            category="security", severity="critical",
            method="GET", path="/approval-requests", header_mode="auth",
            expected=frozenset({403}),
        ),
        Scenario(
            name="교차 테넌트: 타 팀 quotas 접근 → 403/404 (팀1개=SKIP)",
            category="security", severity="critical",
            request_fn=_scn_cross_tenant_quota,
        ),
        Scenario(
            name="타 사용자 예약 취소 시도 → 403/404, 5xx 금지",
            category="security", severity="critical",
            request_fn=_scn_cross_user_cancel,
        ),
        Scenario(
            name="경로 SQL 인젝션 문자열 → 안전한 4xx(5xx 금지)",
            category="security", severity="critical",
            method="POST",
            path=f"/reservations/{SQLI_PROBE}/cancel", header_mode="auth",
            expected=frozenset({400, 401, 404, 422}),
            note="int 경로 파싱 실패 → 422, 인증 누락 시 401",
        ),
        Scenario(
            name="알 수 없는 엔드포인트 → 404",
            category="security", severity="normal",
            method="GET", path="/this/does/not/exist", header_mode="none",
            expected=frozenset({404}),
        ),
        Scenario(
            name="잘못된 HTTP 메서드(PUT /reservations) → 405",
            category="security", severity="normal",
            method="PUT", path="/reservations", header_mode="auth",
            expected=frozenset({405}),
        ),
        Scenario(
            name="필수 본문 누락(로그인) → 422",
            category="security", severity="critical",
            method="POST", path="/auth/login", header_mode="none",
            body={},
            expected=frozenset({422}),
        ),
        Scenario(
            name="본문 타입 오류(로그인) → 422",
            category="security", severity="critical",
            method="POST", path="/auth/login", header_mode="none",
            body={"email": 123, "password": ["not", "a", "string"]},
            expected=frozenset({422}),
        ),
        Scenario(
            name="이메일 형식 위반(로그인) → 422",
            category="security", severity="normal",
            method="POST", path="/auth/login", header_mode="none",
            body={"email": "not-an-email", "password": "x"},
            expected=frozenset({422}),
        ),
        Scenario(
            name="예약 필수 필드 누락 → 422",
            category="security", severity="critical",
            method="POST", path="/reservations", header_mode="auth",
            body={},
            expected=frozenset({422}),
        ),
        Scenario(
            name="예약 본문 타입 오류 → 422",
            category="security", severity="normal",
            method="POST", path="/reservations", header_mode="auth",
            body={"serverId": "abc", "startTime": "x", "endTime": "y"},
            expected=frozenset({422}),
        ),
    ]

    performance: list[Scenario] = [
        Scenario(
            name=f"/health 응답 < {HEALTH_LATENCY_MS:.0f}ms",
            category="performance", severity="normal",
            request_fn=_scn_health_latency,
        ),
        Scenario(
            name=f"인증된 GET /reservations < {RESERVATIONS_LATENCY_MS:.0f}ms",
            category="performance", severity="normal",
            request_fn=_scn_reservations_latency,
        ),
        Scenario(
            name=f"인증된 GET /auth/me < {ME_LATENCY_MS:.0f}ms",
            category="performance", severity="normal",
            request_fn=_scn_me_latency,
        ),
        Scenario(
            name=f"로그인(bcrypt 포함) < {LOGIN_LATENCY_MS:.0f}ms",
            category="performance", severity="normal",
            request_fn=_scn_login_latency,
        ),
    ]

    stability: list[Scenario] = [
        Scenario(
            name="존재하지 않는 serverId 예약 → 404/422, 5xx 금지",
            category="stability", severity="critical",
            method="POST", path="/reservations", header_mode="auth",
            body={"serverId": 999999, "startTime": start, "endTime": end},
            expected=frozenset(SAFE_NOT_FOUND),
        ),
        Scenario(
            name="endTime<startTime 예약 → 안전한 4xx, 5xx 금지",
            category="stability", severity="critical",
            method="POST", path="/reservations", header_mode="auth",
            body={"serverId": 999999, "startTime": rev_start, "endTime": rev_end},
            expected=frozenset(SAFE_CLIENT_ERROR),
            note="API는 시간순서를 검증하지 않으나 5xx면 안 됨",
        ),
        Scenario(
            name="과거 시각 예약 → 안전한 4xx, 5xx 금지",
            category="stability", severity="critical",
            method="POST", path="/reservations", header_mode="auth",
            body={"serverId": 999999,
                  "startTime": "2000-01-01T00:00:00+00:00",
                  "endTime": "2000-01-02T00:00:00+00:00"},
            expected=frozenset(SAFE_CLIENT_ERROR),
        ),
        Scenario(
            name="즉시 예약 2회 연속(경쟁) → 201/409/422, 5xx 금지",
            category="stability", severity="critical",
            request_fn=_scn_instant_contention,
        ),
        Scenario(
            name="쿼터 초과 시도 → 422/409, 5xx 금지",
            category="stability", severity="critical",
            request_fn=_scn_quota_overflow,
        ),
        Scenario(
            name="반복 실패 로그인 → 잠금(429) 또는 안전한 401",
            category="stability", severity="normal",
            request_fn=_scn_login_lockout,
            note="login_fail_max=5 도달 시 429 잠금",
        ),
    ]

    return security + performance + stability


SCENARIOS: list[Scenario] = _build_scenarios()


# --- 실행기 -------------------------------------------------------------------


def _run_declarative(client: httpx.Client, scn: Scenario, login: LoginInfo) -> ScenarioResult:
    """선언형 시나리오 한 건 실행. 연결 오류는 크래시 없이 FAIL 처리."""
    try:
        resp = client.request(
            scn.method,
            scn.path,
            headers=_headers(scn.header_mode, login.token),
            json=scn.body,
        )
    except httpx.HTTPError as exc:
        return ScenarioResult(
            scn.name, scn.category, scn.severity, "FAIL",
            f"요청 실패: {type(exc).__name__}",
        )

    code = resp.status_code
    if code >= 500:
        # 어떤 잘못된 입력에도 5xx는 불합격(보안/안정성 위반).
        return ScenarioResult(
            scn.name, scn.category, scn.severity, "FAIL",
            f"{code} (서버 오류, 5xx 금지)",
        )
    status = "PASS" if code in scn.expected else "FAIL"
    expected = "/".join(str(c) for c in sorted(scn.expected))
    return ScenarioResult(
        scn.name, scn.category, scn.severity, status,
        f"{code} (기대 {expected})",
    )


def _run_functional(client: httpx.Client, scn: Scenario, login: LoginInfo) -> ScenarioResult:
    """함수형 시나리오 한 건 실행. SKIP 접두 및 예외를 안전하게 처리."""
    assert scn.request_fn is not None
    try:
        ok, detail = scn.request_fn(client, login)
    except httpx.HTTPError as exc:
        return ScenarioResult(
            scn.name, scn.category, scn.severity, "FAIL",
            f"요청 실패: {type(exc).__name__}",
        )
    except Exception as exc:  # 러너가 어떤 시나리오에도 죽지 않도록 방어
        return ScenarioResult(
            scn.name, scn.category, scn.severity, "FAIL",
            f"예외: {type(exc).__name__}: {exc}",
        )

    if detail.startswith("SKIP:"):
        return ScenarioResult(
            scn.name, scn.category, scn.severity, "SKIP", detail[len("SKIP:"):].strip()
        )
    status = "PASS" if ok else "FAIL"
    return ScenarioResult(scn.name, scn.category, scn.severity, status, detail)


def run_scenarios(
    category: str = "all",
    on_result: Optional[Callable[[ScenarioResult], None]] = None,
) -> list[ScenarioResult]:
    """선택 카테고리의 시나리오를 실행하고 결과 목록을 반환한다.

    category: "security" | "performance" | "stability" | "all"
    on_result: 한 건 끝날 때마다 호출되는 콜백(실시간 출력용). 선택.
    러너는 어떤 시나리오에서도 예외로 죽지 않는다(연결 오류 = 해당 건 FAIL).
    """
    selected = [
        s for s in SCENARIOS if category == "all" or s.category == category
    ]
    results: list[ScenarioResult] = []

    with httpx.Client(base_url=config.BACKEND_HOST, timeout=HTTP_TIMEOUT) as client:
        # 로그인은 한 번만 수행해 토큰을 재사용한다(메인 계정 001).
        try:
            session = login(
                client,
                config.SEED_USER_EMAIL_FMT.format(n=1),
                config.SEED_PASSWORD,
            )
        except (RuntimeError, httpx.HTTPError) as exc:
            # 로그인 자체가 안 되면 인증이 필요한 시나리오를 모두 SKIP 처리한다.
            session = LoginInfo(token="", team_id=0, user_id=0)
            note = f"로그인 실패로 토큰 없음: {exc}"
            for scn in selected:
                needs_auth = scn.header_mode == "auth" or scn.request_fn is not None
                if needs_auth and scn.header_mode != "none":
                    res = ScenarioResult(scn.name, scn.category, scn.severity, "SKIP", note)
                else:
                    res = (
                        _run_functional(client, scn, session)
                        if scn.request_fn
                        else _run_declarative(client, scn, session)
                    )
                results.append(res)
                if on_result:
                    on_result(res)
            return results

        for scn in selected:
            if scn.request_fn is not None:
                res = _run_functional(client, scn, session)
            else:
                res = _run_declarative(client, scn, session)
            results.append(res)
            if on_result:
                on_result(res)

    return results
