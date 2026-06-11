"""사전 점검: 컨테이너가 떠 있고 실제로 응답하는지 확인한 뒤에만 테스트를 시작한다.

존재 여부는 docker ps로, 살아있는지는 HTTP 호출로 이중 확인한다.
잘못된 측정(죽은 서비스에 부하)을 막는 것이 목적이다.
"""

import json
import shutil
import subprocess
import time
from dataclasses import dataclass

import httpx

from testkit import config, ui


@dataclass
class CheckItem:
    name: str
    ok: bool
    detail: str
    hint: str = ""


def _docker_running_names() -> list[str] | None:
    """실행 중 컨테이너 이름 목록. docker를 못 쓰면 None."""
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{json .Names}}"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return None


def _http_check(name: str, url: str, hint: str) -> CheckItem:
    """GET 호출이 200이면 통과. 응답 시간을 함께 기록한다."""
    try:
        start = time.monotonic()
        resp = httpx.get(url, timeout=5)
        elapsed_ms = (time.monotonic() - start) * 1000
        ok = resp.status_code == 200
        detail = f"{url} {resp.status_code} ({elapsed_ms:.0f}ms)"
        return CheckItem(name, ok, detail, "" if ok else hint)
    except httpx.HTTPError as exc:
        return CheckItem(name, False, f"{url} 연결 실패 ({type(exc).__name__})", hint)


def check_backend() -> CheckItem:
    return _http_check(
        "backend", f"{config.BACKEND_HOST}/health",
        "cd backend && docker compose up -d",
    )


def check_agents() -> list[CheckItem]:
    items = []
    for n, port in config.AGENT_PORTS.items():
        items.append(_http_check(
            f"agent-{n} ({port})", f"{config.AGENT_HOST}:{port}/metrics",
            f"cd server-pool && docker compose up -d agent-{n}",
        ))
    return items


def check_docker() -> CheckItem:
    names = _docker_running_names()
    if names is None:
        return CheckItem("docker", False, "docker ps 실행 불가", "docker 데몬을 확인하세요")
    return CheckItem("docker", True, f"실행 중 컨테이너 {len(names)}개")


def check_binary(name: str, hint: str) -> CheckItem:
    path = shutil.which(name)
    if path:
        return CheckItem(name, True, path)
    return CheckItem(name, False, "설치되어 있지 않음", hint)


def run(*, agents: bool = True, need_k6: bool = False, need_docker: bool = False,
        skip: bool = False) -> None:
    """점검을 실행하고 표로 출력한다. 하나라도 실패하면 종료 코드 2로 중단.

    skip=True(--no-preflight)면 안내만 출력하고 건너뛴다.
    """
    ui.phase(1, 4, "사전 점검")
    if skip:
        ui.console.print("  [yellow]--no-preflight: 점검을 건너뜁니다 (측정 왜곡 주의)[/yellow]")
        return

    items: list[CheckItem] = [check_backend()]
    if agents:
        items.extend(check_agents())
    if need_docker:
        items.append(check_docker())
    if need_k6:
        items.append(check_binary("k6", "https://grafana.com/docs/k6/latest/set-up/install-k6/"))

    if not ui.check_table(items):
        ui.fail_exit("사전 점검 실패. 위 안내대로 컨테이너를 띄운 뒤 다시 실행하세요.", code=2)
