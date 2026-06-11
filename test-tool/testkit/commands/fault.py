"""장애 주입(fault injection): docker로 컨테이너를 죽이고/멈추고/괴롭혀 시스템 반응을 본다.

각 시나리오는 5단계로 진행한다:
  1) 사전 스냅샷  2) 장애 주입  3) 감지 폴링  4) 복구  5) 복구 폴링 + 데이터 불변 확인

컨테이너 이름은 프로젝트 접두사가 붙으므로(server-pool-agent-3-1 등) 항상 부분 일치로 찾는다.
backend의 MISSING 전환 로직은 아직 미구현이라, s1/s2에서 상태가 안 바뀌면
"도구 충돌"이 아니라 "발견(FINDING)"으로 보고한다. 이게 이 테스트의 가치다.
"""

import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx
import typer

from testkit import config, preflight, results, ui

SCENARIOS = ["s1", "s2", "s3", "s4", "s5"]
DETECT_TIMEOUT = 90      # 감지 폴링 한계 (초)
RECOVER_TIMEOUT = 60     # 복구 폴링 한계 (초)
SEED_EMAIL = "loadtest001@example.com"


def register(app: typer.Typer) -> None:
    @app.command(name="fault")
    def fault_cmd(scenario: str) -> None:
        """장애 주입. scenario: s1|s2|s3|s4|s5|all"""
        if scenario not in SCENARIOS and scenario != "all":
            ui.fail_exit(f"scenario는 {SCENARIOS + ['all']} 중 하나여야 합니다. (입력: {scenario})", code=2)

        preflight.run(agents=True, need_docker=True)
        run_dir = results.make_run_dir(f"fault-{scenario}")

        targets = SCENARIOS if scenario == "all" else [scenario]
        outcomes: list[dict] = []
        for sid in targets:
            outcomes.append(_run_scenario(sid, run_dir))

        _report(scenario, outcomes, run_dir)


# ---------------------------------------------------------------------------
# 시나리오 실행
# ---------------------------------------------------------------------------

def _run_scenario(sid: str, run_dir: Path) -> dict:
    ui.phase(2, 4, f"[{sid}] 시나리오")
    fn = {
        "s1": _s1_agent_stop, "s2": _s2_agent_pause, "s3": _s3_postgres_restart,
        "s4": _s4_redis_restart, "s5": _s5_stress_agent,
    }[sid]
    started = datetime.now(timezone.utc)
    before = snapshot()
    ui.console.print(f"  사전 스냅샷: 예약 {before['reservation_count']}건"
                     + ("" if before["auth_ok"] else " [yellow](인증 실패로 빈 스냅샷)[/yellow]"))

    verdict, note = fn()

    after = snapshot()
    unchanged = before["reservation_count"] == after["reservation_count"]
    _dump_backend_logs(run_dir, sid, started)

    mark = {"PASS": OK_MARK, "FAIL": NG_MARK, "FINDING": "[yellow]●[/yellow]"}[verdict]
    ui.console.print(f"  {mark} [{sid}] {verdict} — {note}")
    ui.console.print(f"    데이터 불변: {'예' if unchanged else '아니오'} "
                     f"(전 {before['reservation_count']} / 후 {after['reservation_count']})")
    return {"scenario": sid, "verdict": verdict, "note": note,
            "data_unchanged": unchanged,
            "before": before["reservation_count"], "after": after["reservation_count"]}


def _s1_agent_stop() -> tuple[str, str]:
    """agent-3 컨테이너 정지 -> backend가 90초 내 MISSING 표시하는지."""
    name = _resolve("agent-3")
    if not name:
        return "FAIL", "agent-3 컨테이너를 찾지 못함"
    docker_stop(name)
    detected = poll_until(DETECT_TIMEOUT, "agent-3 MISSING 감지", _agent_missing(3))
    docker_start(name)
    poll_until(RECOVER_TIMEOUT, "agent-3 복구", _agent_alive(3))
    if detected:
        return "PASS", "backend가 MISSING으로 전환함"
    return "FINDING", "MISSING 전환 미발생 (backend 미구현 — 설계상 예상된 발견)"


def _s2_agent_pause() -> tuple[str, str]:
    """agent-3 일시정지(타임아웃 경로) -> 수집기 행(hang) 여부 관찰."""
    name = _resolve("agent-3")
    if not name:
        return "FAIL", "agent-3 컨테이너를 찾지 못함"
    docker_pause(name)
    detected = poll_until(DETECT_TIMEOUT, "agent-3 MISSING 감지(타임아웃)", _agent_missing(3))
    docker_unpause(name)
    poll_until(RECOVER_TIMEOUT, "agent-3 복구", _agent_alive(3))
    if detected:
        return "PASS", "타임아웃 후 MISSING으로 전환함"
    return "FINDING", "명시적 타임아웃 없음 — 수집기 행 가능 (예상된 발견)"


def _s3_postgres_restart() -> tuple[str, str]:
    """postgres 재시작 -> 다운 중 5xx 허용, 프로세스 생존, 60초 내 /health 200 복구."""
    return _restart_and_recover("postgres")


def _s4_redis_restart() -> tuple[str, str]:
    """redis 재시작 -> postgres와 동일한 회복 검증."""
    return _restart_and_recover("redis")


def _restart_and_recover(substr: str) -> tuple[str, str]:
    name = _resolve(substr)
    if not name:
        return "FAIL", f"{substr} 컨테이너를 찾지 못함"
    docker_restart(name)
    recovered = poll_until(RECOVER_TIMEOUT, f"{substr} 재시작 후 /health 200", _health_ok)
    if recovered:
        return "PASS", f"{substr} 다운 후 백엔드가 정상 복구됨"
    return "FAIL", f"{substr} 복구 후에도 /health 200 미달"


def _s5_stress_agent() -> tuple[str, str]:
    """agent-3에 stress-ng CPU 부하 -> /metrics(9103) 응답 유지 + cpuUsage 상승 확인."""
    name = _resolve("agent-3")
    if not name:
        return "FAIL", "agent-3 컨테이너를 찾지 못함"
    base = _agent_metrics(3)
    base_cpu = base.get("cpuUsage") if base else None
    docker_exec_stress(name)
    elevated = poll_until(60, "agent-3 cpuUsage 상승", _cpu_elevated(3, base_cpu))
    if elevated:
        return "PASS", f"부하 중 /metrics 응답 유지, cpuUsage 상승 (기준 {base_cpu})"
    return "FINDING", "cpuUsage 상승 미관측 (stress-ng 미설치 또는 응답 변화 없음)"


# ---------------------------------------------------------------------------
# 폴링 / 술어(predicate)
# ---------------------------------------------------------------------------

OK_MARK = ui.OK
NG_MARK = ui.NG


def poll_until(timeout_s: int, desc: str, predicate: Callable[[], bool]) -> bool:
    """predicate가 참이 될 때까지 폴링. 성공/시간초과를 경과 시간과 함께 출력한다."""
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        try:
            if predicate():
                ui.console.print(f"    {ui.OK} {desc} ({time.monotonic() - start:.0f}s)")
                return True
        except (httpx.HTTPError, subprocess.SubprocessError):
            pass
        time.sleep(2)
    ui.console.print(f"    {ui.NG} {desc} (시간초과 {timeout_s}s)")
    return False


def _agent_metrics(n: int) -> dict | None:
    try:
        resp = httpx.get(f"{config.AGENT_HOST}:{config.AGENT_PORTS[n]}/metrics", timeout=4)
        return resp.json() if resp.status_code == 200 else None
    except httpx.HTTPError:
        return None


def _agent_alive(n: int) -> Callable[[], bool]:
    return lambda: _agent_metrics(n) is not None


def _agent_missing(n: int) -> Callable[[], bool]:
    """backend가 해당 서버를 MISSING으로 표시하는지. 미구현이면 계속 False."""
    def check() -> bool:
        try:
            resp = httpx.get(f"{config.BACKEND_HOST}/servers", timeout=4)
            if resp.status_code != 200:
                return False
            for srv in resp.json():
                if srv.get("id") == n or srv.get("serverId") == n:
                    return str(srv.get("status", "")).upper() == "MISSING"
        except httpx.HTTPError:
            return False
        return False
    return check


def _cpu_elevated(n: int, base_cpu: float | None) -> Callable[[], bool]:
    def check() -> bool:
        m = _agent_metrics(n)
        if not m:
            return False
        cpu = m.get("cpuUsage")
        if cpu is None:
            return False
        if base_cpu is None:
            return float(cpu) > 50.0
        return float(cpu) > float(base_cpu) + 10.0
    return check


def _health_ok() -> bool:
    try:
        resp = httpx.get(f"{config.BACKEND_HOST}/health", timeout=4)
        return resp.status_code == 200 and resp.json().get("status") == "ok"
    except httpx.HTTPError:
        return False


# ---------------------------------------------------------------------------
# 스냅샷 (데이터 불변 확인용)
# ---------------------------------------------------------------------------

def snapshot() -> dict:
    """예약 목록을 스냅샷한다. 인증 실패 시 빈 스냅샷으로 견고하게 처리한다."""
    token = _login()
    if not token:
        return {"auth_ok": False, "reservation_count": 0, "reservations": []}
    try:
        resp = httpx.get(f"{config.BACKEND_HOST}/reservations",
                         headers={"Authorization": f"Bearer {token}"}, timeout=6)
        if resp.status_code != 200:
            return {"auth_ok": True, "reservation_count": 0, "reservations": []}
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        return {"auth_ok": True, "reservation_count": len(items), "reservations": items}
    except httpx.HTTPError:
        return {"auth_ok": False, "reservation_count": 0, "reservations": []}


def _login() -> str | None:
    try:
        resp = httpx.post(f"{config.BACKEND_HOST}/auth/login",
                          json={"email": SEED_EMAIL, "password": config.SEED_PASSWORD},
                          timeout=6)
        if resp.status_code == 200:
            return resp.json().get("accessToken")
    except httpx.HTTPError:
        return None
    return None


# ---------------------------------------------------------------------------
# docker 헬퍼
# ---------------------------------------------------------------------------

def _resolve(substr: str) -> str | None:
    """실행 중 컨테이너 이름을 부분 일치로 찾는다. 없으면 None."""
    try:
        out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                             capture_output=True, text=True, timeout=10, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    for name in out.stdout.splitlines():
        if substr in name:
            return name.strip()
    return None


def _docker(*args: str) -> None:
    subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)


def docker_stop(name: str) -> None:
    _docker("stop", name)


def docker_start(name: str) -> None:
    _docker("start", name)


def docker_pause(name: str) -> None:
    _docker("pause", name)


def docker_unpause(name: str) -> None:
    _docker("unpause", name)


def docker_restart(name: str) -> None:
    _docker("restart", name)


def docker_exec_stress(name: str) -> None:
    """컨테이너 안에서 stress-ng로 CPU를 120초간 괴롭힌다 (백그라운드 실행)."""
    subprocess.Popen(
        ["docker", "exec", name, "stress-ng", "--cpu", "4", "--timeout", "120s"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _dump_backend_logs(run_dir: Path, sid: str, since: datetime) -> None:
    """장애 구간 동안의 backend 로그를 파일로 남긴다."""
    name = _resolve("api")
    if not name:
        return
    stamp = since.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        out = subprocess.run(["docker", "logs", name, "--since", stamp],
                             capture_output=True, text=True, timeout=30)
        (run_dir / f"backend-during-fault-{sid}.log").write_text(
            out.stdout + out.stderr, encoding="utf-8")
    except subprocess.SubprocessError:
        pass


# ---------------------------------------------------------------------------
# 결과
# ---------------------------------------------------------------------------

def _report(scenario: str, outcomes: list[dict], run_dir: Path) -> None:
    ui.phase(4, 4, "결과")
    criteria = [
        (f"[{o['scenario']}] {o['note']}",
         o["verdict"] in ("PASS", "FINDING"),
         o["verdict"])
        for o in outcomes
    ]
    ui.verdict(criteria)

    findings = [o for o in outcomes if o["verdict"] == "FINDING"]
    fails = [o for o in outcomes if o["verdict"] == "FAIL"]
    if findings:
        ui.console.print(f"\n  [yellow]발견(FINDING) {len(findings)}건 — 개선 후보[/yellow]")

    results.save(run_dir, {
        "command": f"fault-{scenario}",
        "scenarios": outcomes,
        "summary": {
            "pass": sum(1 for o in outcomes if o["verdict"] == "PASS"),
            "finding": len(findings),
            "fail": len(fails),
        },
    })
