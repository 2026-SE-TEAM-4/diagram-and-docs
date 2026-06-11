"""성능 테스트 4종 커맨드: load, stress, spike, endurance.

각 커맨드는 아래 4단계를 따른다:
  [1/4] 사전 점검
  [2/4] 테스트 계획
  [3/4] 실행
  [4/4] 결과
"""

import csv
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import asyncpg
import typer

import asyncio

from datetime import datetime

from testkit import config, preflight, report_html, results, ui, verify
from testkit.engines.locust import stages_data


def _get_server_ids() -> list[int]:
    """DB에서 삭제되지 않은 서버 id 목록을 동기적으로 반환한다."""

    async def _query() -> list[int]:
        conn = await asyncpg.connect(config.DB_DSN)
        try:
            # 예약 대상이 될 수 있는 서버만 추린다(점검 상태는 제외).
            rows = await conn.fetch(
                "SELECT id FROM server WHERE status <> 'MAINTENANCE' ORDER BY id"
            )
            return [row["id"] for row in rows]
        finally:
            await conn.close()

    return asyncio.run(_query())


def _locust_csv_stats(run_dir: Path) -> dict[str, str]:
    """locust CSV 요약 파일에서 Aggregated 행의 주요 지표를 읽는다."""
    stats_file = run_dir / "locust_stats.csv"
    if not stats_file.exists():
        return {}

    result: dict[str, str] = {}
    with stats_file.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Name", "").strip() == "Aggregated":
                result["총 요청 수"] = row.get("Request Count", "-")
                result["실패 수"] = row.get("Failure Count", "-")
                result["중앙값 응답시간(ms)"] = row.get("50%", "-")
                result["p95 응답시간(ms)"] = row.get("95%", "-")
                result["p99 응답시간(ms)"] = row.get("99%", "-")
                result["최대 응답시간(ms)"] = row.get("Max", "-")
                result["평균 RPS"] = row.get("Requests/s", "-")
                result["평균 실패/s"] = row.get("Failures/s", "-")
                break
    return result


def _run_locust(
    shape: str,
    server_ids: list[int],
    run_dir: Path,
    no_preflight: bool,
    users_override: Optional[int],
    duration_sec: Optional[int],
) -> int:
    """locust를 subprocess로 실행하고 종료 코드를 반환한다."""
    locustfile = config.ENGINES_DIR / "locust" / "locustfile.py"
    host = config.BACKEND_HOST

    env = os.environ.copy()
    env["SHAPE"] = shape
    env["SERVER_IDS"] = ",".join(str(sid) for sid in server_ids)

    if users_override is not None:
        env["USERS_OVERRIDE"] = str(users_override)

    if duration_sec is not None:
        env["DURATION_SEC"] = str(duration_sec)

    cmd = [
        sys.executable, "-m", "locust",
        "-f", str(locustfile),
        "--headless",
        "--host", host,
        "--csv", str(run_dir / "locust"),
        "--csv-full-history",
        "--only-summary",
    ]

    # locust 자체 로그(stdout/stderr)는 파일로 보낸다.
    # 화면에는 우리가 직접 그리는 진행 바만 남겨 깔끔하게 유지하고,
    # 문제 발생 시 locust.log로 원인을 추적할 수 있게 한다.
    log_path = run_dir / "locust.log"
    history = run_dir / "locust_stats_history.csv"
    line = stages_data.timeline(shape, duration_sec)

    with log_path.open("w", encoding="utf-8") as log_f:
        proc = subprocess.Popen(
            cmd,
            env=env,
            cwd=str(config.TESTING_DIR),
            stdout=log_f,
            stderr=subprocess.STDOUT,
        )
        _render_dashboard(proc, shape, line, history)

    return proc.returncode


def _stage_index(elapsed: float, line: list[tuple[int, int]]) -> tuple[int, int]:
    """경과 시간이 속한 단계 번호(1-기반)와 그 단계의 목표 사용자수를 반환한다.

    shape.tick()의 'run_time < end_sec' 판정과 동일한 경계를 사용한다.
    """
    for idx, (end_sec, users) in enumerate(line, start=1):
        if elapsed < end_sec:
            return idx, users
    if line:
        return len(line), line[-1][1]
    return 1, 0


def _read_live_metrics(history: Path) -> Optional[dict]:
    """history CSV 끝에서 최신 Aggregated 행을 읽어 라이브 지표를 반환한다.

    파일이 아직 없거나 Aggregated 행이 없으면 None. 파일이 커져도 끝부분만 읽는다.
    """
    if not history.exists():
        return None
    try:
        with history.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 8192))
            chunk = f.read()
    except OSError:
        return None

    lines = chunk.decode("utf-8", "ignore").splitlines()
    for raw in reversed(lines):
        try:
            row = next(csv.reader([raw]))
        except StopIteration:
            continue
        # 헤더: Timestamp,User Count,Type,Name,Requests/s,...,95%(11),...,Total Request Count(17),Total Failure Count(18)
        if len(row) >= 19 and row[2] == "" and row[3] == "Aggregated":
            return {
                "users": _parse_int(row[1]),
                "rps": _parse_float(row[4]),
                "p95": _parse_float(row[11]),
                "total": _parse_int(row[17]),
                "fail": _parse_int(row[18]),
            }
    return None


_SHAPE_TITLES = {
    "load": "LOAD 부하 테스트",
    "stress": "STRESS 스트레스 테스트",
    "spike": "SPIKE 스파이크 테스트",
    "endurance": "ENDURANCE 지속 테스트",
}


def _render_dashboard(
    proc: "subprocess.Popen",
    shape: str,
    line: list[tuple[int, int]],
    history: Path,
) -> None:
    """locust 프로세스가 끝날 때까지 실시간 대시보드를 갱신한다.

    경과 시간은 부모 프로세스의 단조 시계로 잰다(타임라인의 마지막 종료초가 총 길이).
    타임라인을 모르면(빈 목록) 스피너 없이 경과 기준으로만 동작한다.
    """
    total_sec = line[-1][0] if line else None
    num_stages = len(line)
    title = _SHAPE_TITLES.get(shape, shape.upper())

    start = time.monotonic()
    elapsed = 0.0
    with ui.LiveDashboard(title, total_sec, num_stages) as dash:
        while proc.poll() is None:
            elapsed = time.monotonic() - start
            if total_sec:
                elapsed = min(elapsed, total_sec)
            stage, target_users = _stage_index(elapsed, line)
            dash.update(elapsed, stage, target_users, _read_live_metrics(history))
            time.sleep(0.5)

        # 종료 직후 최종 수치로 한 번 더 그린다(마지막 CSV 플러시 반영).
        final_stage = num_stages if num_stages else 0
        final_users = line[-1][1] if line else 0
        dash.update(total_sec or elapsed, final_stage, final_users, _read_live_metrics(history))


def _parse_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


# --- 합격 기준 평가 ---

def _error_rate(stats: dict[str, str]) -> float:
    """Aggregated 행에서 실패율(%)을 계산한다. 요청이 0이면 0%."""
    total = _parse_int(stats.get("총 요청 수", "0"))
    failures = _parse_int(stats.get("실패 수", "0"))
    return (failures / total * 100) if total > 0 else 0.0


def _evaluate_load(stats: dict[str, str]) -> list[tuple[str, bool, str]]:
    """부하 테스트 합격 기준: 지속 단계에서 p95 < 300ms, 실패율 < 1%."""
    p95 = _parse_float(stats.get("p95 응답시간(ms)", "0"))
    error_rate = _error_rate(stats)

    return [
        ("p95 응답시간 < 300ms", p95 < 300, f"{p95:.0f}ms"),
        ("실패율 < 1%", error_rate < 1.0, f"{error_rate:.2f}%"),
    ]


def _evaluate_stress(stats: dict[str, str]) -> list[tuple[str, bool, str]]:
    """스트레스 합격 기준: 프로세스 생존(요청 처리됨) + 최종 실패율 < 5%."""
    total = _parse_int(stats.get("총 요청 수", "0"))
    error_rate = _error_rate(stats)

    return [
        ("프로세스 생존(요청 처리)", total > 0, f"처리 요청 {total}건"),
        ("실패율 회복 < 5%", error_rate < 5.0, f"{error_rate:.2f}%"),
    ]


def _evaluate_spike(stats: dict[str, str]) -> list[tuple[str, bool, str]]:
    """스파이크 합격 기준: 5xx 크래시 없음. DB 정합성 3종은 호출부에서 접합한다."""
    failures = _parse_int(stats.get("실패 수", "0"))

    return [
        ("5xx 크래시 없음", failures == 0, f"실패(5xx) {failures}건"),
    ]


def _evaluate_endurance(stats: dict[str, str]) -> list[tuple[str, bool, str]]:
    """지속 테스트 합격 기준(간소화): 실패율 < 2%면 PASS."""
    error_rate = _error_rate(stats)

    return [
        ("실패율 < 2%", error_rate < 2.0, f"{error_rate:.2f}%"),
    ]


# --- 공통 실행 흐름 ---

def _run_test(
    shape: str,
    plan_rows: dict[str, str],
    evaluate_fn,
    no_preflight: bool,
    users_override: Optional[int],
    duration_sec: Optional[int],
    verify_db: bool = False,
) -> None:
    run_dir = results.make_run_dir(shape)

    # 1단계: 사전 점검 (모든 시나리오가 백엔드를 쓰므로 에이전트까지 점검한다)
    preflight.run(agents=True, skip=no_preflight)

    # 2단계: 테스트 계획
    ui.phase(2, 4, "테스트 계획")
    ui.plan(plan_rows)

    # 3단계: 실행
    ui.phase(3, 4, "실행")

    try:
        server_ids = _get_server_ids()
    except Exception as exc:
        ui.fail_exit(f"DB에서 서버 목록을 가져오지 못했습니다: {exc}", code=2)
        return

    if not server_ids:
        ui.console.print("  [yellow]경고: 활성 서버가 없습니다. 예약 생성 태스크가 건너뜁니다.[/yellow]")

    ui.console.print(f"  활성 서버 ID: {server_ids}")
    ui.console.print(f"  결과 디렉터리: {run_dir.relative_to(config.TESTING_DIR.parent)}")
    ui.console.print(f"  locust 실행 중 (SHAPE={shape})...")

    ret = _run_locust(shape, server_ids, run_dir, no_preflight, users_override, duration_sec)
    if ret != 0:
        ui.console.print(f"  [yellow]locust 종료 코드: {ret}[/yellow]")

    # 4단계: 결과
    ui.phase(4, 4, "결과")

    stats = _locust_csv_stats(run_dir)
    if stats:
        ui.metrics_table(
            f"{shape} 테스트 지표",
            list(stats.items()),
        )
    else:
        ui.console.print("  [yellow]CSV 결과를 찾을 수 없습니다.[/yellow]")

    criteria = evaluate_fn(stats)
    if verify_db:
        # spike: 부하 직후 DB 정합성 3종을 그대로 판정에 접합한다.
        # run_checks()는 화면에 출력하지 않으므로 verdict 표에서 한 번에 보인다.
        ui.console.print("  DB 정합성 검사 실행 중...")
        criteria = criteria + asyncio.run(verify.run_checks())
    passed = ui.verdict(criteria)

    summary = {
        "command": shape,
        "shape": shape,
        "server_ids": server_ids,
        "stats": stats,
        "criteria": [
            {"name": name, "passed": ok, "detail": detail}
            for name, ok, detail in criteria
        ],
        "passed": passed,
    }
    results.save(run_dir, summary)

    # 인터랙티브 HTML 리포트 생성(시계열 차트). 데이터가 없으면 조용히 건너뛴다.
    report = report_html.build_report(
        run_dir,
        title=_SHAPE_TITLES.get(shape, shape.upper()),
        host=config.BACKEND_HOST,
        passed=passed,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    if report is not None:
        ui.console.print(
            f"  인터랙티브 리포트: [bold]{report.relative_to(config.TESTING_DIR.parent)}[/bold]"
            "  [dim](브라우저로 열기)[/dim]"
        )

    if not passed:
        raise typer.Exit(1)


# --- 커맨드 등록 ---

def register(app: typer.Typer) -> None:
    """부하 테스트 4종 커맨드를 app에 등록한다."""

    @app.command()
    def load(
        no_preflight: bool = typer.Option(False, "--no-preflight", help="사전 점검을 건너뜁니다."),
        users: Optional[int] = typer.Option(None, "--users", help="최대 사용자 수 오버라이드."),
    ) -> None:
        """[2.1] 점진적 부하 증가 테스트 (0→200명, 1200초)."""
        _run_test(
            shape="load",
            plan_rows={
                "테스트 계획": "2.1 점진적 부하 증가",
                "시나리오": "일반 탐색 사용자 (예약 조회 5 / 쿼터 조회 2 / 예약 생성 1)",
                "부하 모양": "0→10→50→100→200명 (단계별 300s, spawn_rate=20)",
                "측정": "p95 응답시간, 실패율, RPS",
                "합격 기준": "p95 < 300ms, 실패율 < 1%",
            },
            evaluate_fn=_evaluate_load,
            no_preflight=no_preflight,
            users_override=users,
            duration_sec=None,
        )

    @app.command()
    def stress(
        no_preflight: bool = typer.Option(False, "--no-preflight", help="사전 점검을 건너뜁니다."),
        users: Optional[int] = typer.Option(None, "--users", help="최대 사용자 수 오버라이드."),
    ) -> None:
        """[2.2] 스트레스 테스트 (50→300→50명, 720초) — 급증 후 복귀 성능 확인."""
        _run_test(
            shape="stress",
            plan_rows={
                "테스트 계획": "2.2 스트레스 (급증 + 복귀)",
                "시나리오": "탐색 사용자 + 로그인 사용자 (bcrypt 병목 측정, 1:1 가중)",
                "부하 모양": "50명(120s) → 300명(420s) → 50명(720s), spawn_rate=20",
                "측정": "프로세스 생존 여부, 복귀 구간 실패율",
                "합격 기준": "프로세스 생존 + 실패율 < 5%",
            },
            evaluate_fn=_evaluate_stress,
            no_preflight=no_preflight,
            users_override=users,
            duration_sec=None,
        )

    @app.command()
    def spike(
        no_preflight: bool = typer.Option(False, "--no-preflight", help="사전 점검을 건너뜁니다."),
    ) -> None:
        """[2.3] 스파이크 테스트 (5→200→5명, 300초) — 즉시 예약 쟁탈전."""
        _run_test(
            shape="spike",
            plan_rows={
                "테스트 계획": "2.3 스파이크 (즉시 예약 쟁탈전)",
                "시나리오": "즉시 예약 사용자 (POST /reservations/instant 반복, 대기 없음)",
                "부하 모양": "5명(60s) → 200명(75s, spawn_rate=200) → 5명(300s)",
                "측정": "5xx 발생 여부 + DB 정합성(초과배정·쿼터·카운터)",
                "합격 기준": "5xx 크래시 없음 + DB 정합성 3종 모두 통과",
            },
            evaluate_fn=_evaluate_spike,
            no_preflight=no_preflight,
            users_override=None,
            duration_sec=None,
            verify_db=True,
        )

    @app.command()
    def endurance(
        no_preflight: bool = typer.Option(False, "--no-preflight", help="사전 점검을 건너뜁니다."),
        duration: int = typer.Option(21600, "--duration", help="테스트 지속 시간(초). 기본 6시간."),
    ) -> None:
        """[2.4] 지속 테스트 — 20명으로 장시간 안정성 확인 (기본 6시간)."""
        _run_test(
            shape="endurance",
            plan_rows={
                "테스트 계획": "2.4 지속 (장기 안정성)",
                "시나리오": "일반 탐색 사용자 20명 고정",
                "부하 모양": f"20명 유지 ({duration}초 = {duration // 3600}시간 {(duration % 3600) // 60}분)",
                "측정": "실패율 추이, 메모리 누수 징후 (간접 관찰)",
                "합격 기준": "실패율 < 2% (간소화 판정)",
            },
            evaluate_fn=_evaluate_endurance,
            no_preflight=no_preflight,
            users_override=None,
            duration_sec=duration,
        )
