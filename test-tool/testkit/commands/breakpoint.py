"""중단점(breakpoint) 테스트: 동시 사용자를 0->500까지 올리며 "몇 명에서 무너지는지"를 찾는다.

합격/불합격이 아니라 임계 동시 사용자 수를 산출하는 것이 목적이다.
  login/reserve/read -> k6 ramping-vus 로 10분간 0->500
  serverpool         -> hey 로 동시성 단계별 부하 (에이전트 /metrics)

판정은 정보성이다. k6/hey가 정상 실행되면 종료 코드 0.
"""

import json
import subprocess
from pathlib import Path

import typer

from testkit import config, preflight, results, ui

# 임계점 판정 기준
P95_LIMIT_MS = 300.0      # p95 응답시간 한계
ERR_RATE_LIMIT = 0.05     # 오류율 한계 (5%)
SUSTAIN_BUCKETS = 2       # 연속 2개 버킷에서 위반해야 임계점으로 인정
BUCKET_SEC = 10           # 10초 단위 버킷
RAMP_PEAK_VU = 500        # 최대 동시 사용자
RAMP_SEC = 600            # 램프 시간 (10분)

# serverpool(hey) 단계별 동시성
HEY_CONCURRENCY = [10, 20, 30, 40, 50, 75, 100, 150, 200]
HEY_DURATION = "30s"

# 부하 강도(intensity): 레벨이 곧 배율이다(레벨 N → ×N). 1은 기존 동작과 동일하다.
MIN_INTENSITY = 1
MAX_INTENSITY = 4

K6_PATHS = {"login", "reserve", "read"}
VALID_PATHS = K6_PATHS | {"serverpool"}


def _factor(intensity: int) -> int:
    """강도 레벨을 배율로 변환한다(범위 밖이면 클램프). 레벨 N → ×N."""
    return max(MIN_INTENSITY, min(MAX_INTENSITY, intensity))


def _validate_intensity(intensity: int) -> None:
    """강도 레벨이 1~4 범위인지 검증한다. 벗어나면 종료 코드 2로 실패한다."""
    if intensity < MIN_INTENSITY or intensity > MAX_INTENSITY:
        ui.fail_exit(
            f"강도(--intensity)는 {MIN_INTENSITY}~{MAX_INTENSITY} 사이여야 합니다. "
            f"(입력: {intensity})",
            code=2,
        )


def register(app: typer.Typer) -> None:
    @app.command(name="breakpoint")
    def breakpoint_cmd(
        path: str,
        intensity: int = typer.Option(
            1, "--intensity", "-i",
            help="부하 강도 1~4 (레벨이 곧 배율: 1=×1 ... 4=×4). 최대 동시 사용자/동시성을 배율만큼 늘린다.",
        ),
    ) -> None:
        """임계점 테스트. path: login|reserve|read|serverpool"""
        if path not in VALID_PATHS:
            ui.fail_exit(f"path는 {sorted(VALID_PATHS)} 중 하나여야 합니다. (입력: {path})", code=2)
        _validate_intensity(intensity)

        if path in K6_PATHS:
            _run_k6_breakpoint(path, intensity)
        else:
            _run_hey_breakpoint(intensity)


# ---------------------------------------------------------------------------
# k6 경로 (login/reserve/read)
# ---------------------------------------------------------------------------

def _run_k6_breakpoint(path: str, intensity: int = 1) -> None:
    preflight.run(agents=True, need_k6=True)

    peak_vu = RAMP_PEAK_VU * _factor(intensity)

    ui.phase(2, 4, "테스트 계획")
    ui.plan({
        "무엇을": f"{path} 흐름에 동시 사용자를 0->{peak_vu}명까지 {RAMP_SEC // 60}분간 선형 증가",
        "강도": f"강도 {intensity} (×{_factor(intensity)}) · 최대 {peak_vu}명",
        "어떤 요청으로": "k6 ramping-vus 시나리오 (시드 계정 loadtest001~050)",
        "무엇을 측정": "10초 버킷별 p95 응답시간 / 오류율",
        "산출물": f"임계 동시 사용자 수 (p95>{P95_LIMIT_MS:.0f}ms 또는 오류율>{ERR_RATE_LIMIT:.0%} 연속 {SUSTAIN_BUCKETS}버킷)",
    })

    run_dir = results.make_run_dir(f"breakpoint-{path}")
    raw_path = run_dir / "raw.json"
    script = config.ENGINES_DIR / "k6" / "breakpoint.js"

    ui.phase(3, 4, "실행")
    ui.console.print(f"  k6 run (출력 -> {raw_path.name})")
    proc = subprocess.run(
        ["k6", "run", "--out", f"json={raw_path}", str(script)],
        env={
            "TARGET_PATH": path,
            "BASE_URL": config.BACKEND_HOST,
            "PEAK_VU": str(peak_vu),
            "PATH": _env_path(),
        },
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not raw_path.exists():
        ui.console.print(proc.stderr[-1500:] if proc.stderr else "(stderr 없음)")
        ui.fail_exit("k6 실행에 실패했습니다. 위 로그를 확인하세요.", code=2)

    ui.phase(4, 4, "결과")
    buckets = _parse_k6_buckets(raw_path, peak_vu)
    _write_breakpoint_csv(run_dir, buckets)
    breakpoint_vu = _find_breakpoint(buckets)
    _report_k6(path, buckets, breakpoint_vu, run_dir, peak_vu)


def _parse_k6_buckets(raw_path: Path, peak_vu: int = RAMP_PEAK_VU) -> list[dict]:
    """k6 json 라인을 10초 버킷으로 묶어 버킷별 p95/오류율을 계산한다.

    k6 json 각 라인: {"type":"Point","metric":"http_req_duration"|"http_req_failed",
                      "data":{"time": ISO, "value": float, ...}}
    VU는 라인에 직접 없으므로 경과 시간으로 선형 추정한다 (0->peak_vu, 600s).
    peak_vu는 강도 배율이 적용된 최대 동시 사용자 수다(기본 500).
    """
    durations: dict[int, list[float]] = {}
    fails: dict[int, list[float]] = {}
    t0: float | None = None

    with raw_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "Point":
                continue
            metric = rec.get("metric")
            if metric not in ("http_req_duration", "http_req_failed"):
                continue
            data = rec.get("data", {})
            ts = _parse_ts(data.get("time"))
            if ts is None:
                continue
            if t0 is None or ts < t0:
                t0 = ts
            bucket = int((ts - t0) // BUCKET_SEC)
            value = float(data.get("value", 0.0))
            if metric == "http_req_duration":
                durations.setdefault(bucket, []).append(value)
            else:  # http_req_failed (0=성공, 1=실패)
                fails.setdefault(bucket, []).append(value)

    buckets: list[dict] = []
    for idx in sorted(set(durations) | set(fails)):
        dur = durations.get(idx, [])
        fail = fails.get(idx, [])
        elapsed = idx * BUCKET_SEC
        vu = min(peak_vu, round(peak_vu * elapsed / RAMP_SEC))
        buckets.append({
            "bucket": idx,
            "time_s": elapsed,
            "vu": vu,
            "p95": _percentile(dur, 95),
            "errrate": (sum(fail) / len(fail)) if fail else 0.0,
            "samples": len(dur),
        })
    return buckets


def _find_breakpoint(buckets: list[dict]) -> int | None:
    """p95 또는 오류율이 연속 SUSTAIN_BUCKETS개 버킷에서 한계를 넘긴 첫 지점의 VU."""
    streak = 0
    for b in buckets:
        violated = b["p95"] > P95_LIMIT_MS or b["errrate"] > ERR_RATE_LIMIT
        if violated:
            streak += 1
            if streak >= SUSTAIN_BUCKETS:
                return b["vu"]
        else:
            streak = 0
    return None


def _write_breakpoint_csv(run_dir: Path, buckets: list[dict]) -> None:
    lines = ["time,vu,p95,errrate"]
    for b in buckets:
        lines.append(f"{b['time_s']},{b['vu']},{b['p95']:.1f},{b['errrate']:.4f}")
    (run_dir / "breakpoint.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _report_k6(path: str, buckets: list[dict], breakpoint_vu: int | None,
               run_dir: Path, peak_vu: int = RAMP_PEAK_VU) -> None:
    peak = max((b["p95"] for b in buckets), default=0.0)
    worst_err = max((b["errrate"] for b in buckets), default=0.0)
    ui.metrics_table(f"{path} 중단점 요약", [
        ("측정 버킷 수", str(len(buckets))),
        ("최대 p95", f"{peak:.0f}ms"),
        ("최대 오류율", f"{worst_err:.1%}"),
        ("판정 기준", f"p95>{P95_LIMIT_MS:.0f}ms 또는 오류율>{ERR_RATE_LIMIT:.0%}"),
    ])
    if breakpoint_vu is not None:
        ui.console.print(f"\n  [bold yellow]임계점: 동시 {breakpoint_vu}명[/bold yellow]")
    else:
        ui.console.print(f"\n  [bold green]임계점: 동시 {peak_vu}명까지 한계 미도달[/bold green]")

    results.save(run_dir, {
        "command": f"breakpoint-{path}",
        "engine": "k6",
        "criteria": {"p95_limit_ms": P95_LIMIT_MS, "err_rate_limit": ERR_RATE_LIMIT},
        "breakpoint_vu": breakpoint_vu,
        "max_p95_ms": peak,
        "max_err_rate": worst_err,
        "buckets": buckets,
    })


# ---------------------------------------------------------------------------
# hey 경로 (serverpool: 에이전트 /metrics)
# ---------------------------------------------------------------------------

def _run_hey_breakpoint(intensity: int = 1) -> None:
    preflight.run(agents=True, need_k6=False)

    # 각 동시성 단계에 강도 배율을 적용한다(최소 1). 레벨 1이면 기존 값과 동일.
    fac = _factor(intensity)
    concurrency_steps = [max(1, c * fac) for c in HEY_CONCURRENCY]

    ui.phase(2, 4, "테스트 계획")
    ui.plan({
        "무엇을": f"에이전트 /metrics 에 동시성을 {concurrency_steps[0]}->{concurrency_steps[-1]}까지 단계 증가",
        "강도": f"강도 {intensity} (×{fac}) · 최대 {concurrency_steps[-1]} 동시성",
        "어떤 요청으로": f"hey -z {HEY_DURATION} -c <동시성> (agent-1:9101)",
        "무엇을 측정": "단계별 p95 응답시간 / 오류 건수",
        "산출물": f"임계 동시 요청 수 (p95>{P95_LIMIT_MS:.0f}ms 또는 오류 발생 시점)",
    })

    target = f"{config.AGENT_HOST}:{config.AGENT_PORTS[1]}/metrics"
    run_dir = results.make_run_dir("breakpoint-serverpool")

    ui.phase(3, 4, "실행")
    stages: list[dict] = []
    raw_blocks: list[str] = []
    for conc in concurrency_steps:
        ui.console.print(f"  hey -z {HEY_DURATION} -c {conc} {target}")
        proc = subprocess.run(
            ["hey", "-z", HEY_DURATION, "-c", str(conc), target],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 and not proc.stdout:
            ui.console.print(proc.stderr[-800:] if proc.stderr else "(stderr 없음)")
            ui.fail_exit("hey 실행에 실패했습니다. hey 설치 여부를 확인하세요.", code=2)
        raw_blocks.append(f"=== -c {conc} ===\n{proc.stdout}")
        stages.append(_parse_hey(conc, proc.stdout))

    (run_dir / "hey-raw.txt").write_text("\n\n".join(raw_blocks), encoding="utf-8")

    ui.phase(4, 4, "결과")
    _report_hey(stages, target, run_dir, concurrency_steps[-1])


def _parse_hey(concurrency: int, text: str) -> dict:
    """hey 텍스트 출력에서 p95 지연(초)과 오류 건수를 뽑는다.

    hey는 Latency distribution 의 95% 줄과 Error distribution 섹션을 출력한다.
    """
    p95_ms = 0.0
    errors = 0
    in_latency = False
    in_errors = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("Latency distribution"):
            in_latency, in_errors = True, False
            continue
        if s.startswith("Error distribution"):
            in_errors, in_latency = True, False
            continue
        if in_latency and s.startswith("95%"):
            # 예: "95% in 0.0123 secs"
            parts = s.split()
            if len(parts) >= 3:
                try:
                    p95_ms = float(parts[2]) * 1000.0
                except ValueError:
                    pass
            in_latency = False
        if in_errors and s.startswith("[") and "]" in s:
            # 예: "[2] 5 responses"
            try:
                errors += int(s.split("]")[1].split()[0])
            except (IndexError, ValueError):
                pass
    return {"concurrency": concurrency, "p95_ms": p95_ms, "errors": errors}


def _report_hey(stages: list[dict], target: str, run_dir: Path,
                max_concurrency: int = HEY_CONCURRENCY[-1]) -> None:
    rows = [
        (f"-c {st['concurrency']}", f"p95 {st['p95_ms']:.0f}ms / 오류 {st['errors']}건")
        for st in stages
    ]
    ui.metrics_table(f"serverpool 단계별 결과 ({target})", rows)

    breakpoint_c: int | None = None
    for st in stages:
        if st["p95_ms"] > P95_LIMIT_MS or st["errors"] > 0:
            breakpoint_c = st["concurrency"]
            break
    if breakpoint_c is not None:
        ui.console.print(f"\n  [bold yellow]임계점: 동시 {breakpoint_c}명[/bold yellow]")
    else:
        ui.console.print(
            f"\n  [bold green]임계점: 동시 {max_concurrency}명까지 한계 미도달[/bold green]"
        )

    results.save(run_dir, {
        "command": "breakpoint-serverpool",
        "engine": "hey",
        "target": target,
        "criteria": {"p95_limit_ms": P95_LIMIT_MS},
        "breakpoint_concurrency": breakpoint_c,
        "stages": stages,
    })


# ---------------------------------------------------------------------------
# 공용 유틸
# ---------------------------------------------------------------------------

def _percentile(values: list[float], pct: float) -> float:
    """단순 백분위수. 빈 리스트면 0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(ordered) - 1)
    frac = rank - lo
    return ordered[lo] + (ordered[hi] - ordered[lo]) * frac


def _parse_ts(raw: str | None) -> float | None:
    """k6 ISO8601 시각 문자열을 epoch 초로 변환한다."""
    if not raw:
        return None
    from datetime import datetime
    text = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        # 나노초 등 fromisoformat이 못 읽는 형식이면 소수점 6자리로 잘라 재시도
        try:
            head, _, tail = text.partition(".")
            frac = tail[:6]
            tz = ""
            for sign in ("+", "-"):
                if sign in tail:
                    tz = sign + tail.split(sign, 1)[1]
                    frac = tail.split(sign, 1)[0][:6]
                    break
            return datetime.fromisoformat(f"{head}.{frac}{tz}").timestamp()
        except ValueError:
            return None


def _env_path() -> str:
    """subprocess가 k6 바이너리를 찾을 수 있도록 현재 PATH를 넘긴다."""
    import os
    return os.environ.get("PATH", "")
