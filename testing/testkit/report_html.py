"""locust history CSV → 인터랙티브 HTML 리포트(Plotly).

각 실행 폴더의 locust_stats_history.csv(시계열)를 읽어, 줌·호버·범례 토글이 되는
단일 HTML 파일(report.html)을 만든다. Plotly는 CDN에서 불러오고 데이터는 HTML에
JSON으로 박아 넣으므로, CSV가 사라져도 리포트만으로 그래프가 보인다.

디자인 원칙: 라이트 테마, Pretendard, 장식 최소화 — 결과 가독성과 시각화에만 집중.
locust에 의존하지 않으므로 CLI 부모 프로세스에서 안전하게 import할 수 있다.
"""

import csv
import json
from pathlib import Path
from typing import Optional

from jinja2 import Template

# --- history CSV 컬럼 인덱스 ---
_TS = 0
_USERS = 1
_TYPE = 2
_NAME = 3
_RPS = 4
_FAIL_S = 5
_P50 = 6
_P95 = 11
_P99 = 13
_TOTAL_REQ = 17
_TOTAL_FAIL = 18

# Plotly CDN(SRI 고정). 폰트는 Pretendard CDN.
_PLOTLY_SRI = "sha384-cCVCZkAjYNxaYKbM8lsArLznDF/SvMFr1jcZrvOpSTCa0W40ZAdLzHCEulnUa5i7"
_PRETENDARD_HREF = (
    "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9"
    "/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
)
_PRETENDARD_SRI = "sha384-GIdEBaqGN9mNkDkMkzMHW8EKUqtpPIe/sLj1X7DIrnc9uPtLROJgmuDlh+3rBw0j"

# 흰 배경에서 읽기 좋은 차트 색.
_C_PRIMARY = "#2563eb"
_C_GREEN = "#16a34a"
_C_AMBER = "#d97706"
_C_VIOLET = "#7c3aed"
_C_RED = "#dc2626"


def _num(value: str) -> Optional[float]:
    """'N/A'·빈칸은 None, 그 외는 float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _read_series(history: Path) -> Optional[dict]:
    """history CSV에서 차트용 시계열을 추출한다. 데이터가 없으면 None."""
    if not history.exists():
        return None

    agg: list[list[str]] = []
    endpoints: dict[str, list[tuple[float, float]]] = {}

    with history.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return None
        for row in reader:
            if len(row) <= _TOTAL_FAIL:
                continue
            ts = _num(row[_TS])
            if ts is None:
                continue
            if row[_TYPE] == "" and row[_NAME] == "Aggregated":
                agg.append(row)
            elif row[_TYPE] != "":
                rps = _num(row[_RPS]) or 0.0
                endpoints.setdefault(row[_NAME], []).append((ts, rps))

    if not agg:
        return None

    ts0 = float(agg[0][_TS])

    def elapsed(row: list[str]) -> float:
        return float(row[_TS]) - ts0

    t = [elapsed(r) for r in agg]
    rps = [_num(r[_RPS]) or 0.0 for r in agg]
    fail_s = [_num(r[_FAIL_S]) or 0.0 for r in agg]
    p50 = [_num(r[_P50]) for r in agg]
    p95 = [_num(r[_P95]) for r in agg]
    p99 = [_num(r[_P99]) for r in agg]
    users = [int(_num(r[_USERS]) or 0) for r in agg]
    total_req = [int(_num(r[_TOTAL_REQ]) or 0) for r in agg]
    total_fail = [int(_num(r[_TOTAL_FAIL]) or 0) for r in agg]

    endpoint_series = {
        name: {
            "t": [pt[0] - ts0 for pt in pts],
            "rps": [pt[1] for pt in pts],
        }
        for name, pts in endpoints.items()
    }

    # KPI(최종/최대값)
    p95_vals = [v for v in p95 if v is not None]
    kpis = {
        "total_req": total_req[-1] if total_req else 0,
        "total_fail": total_fail[-1] if total_fail else 0,
        "peak_rps": max(rps) if rps else 0.0,
        "peak_p95": max(p95_vals) if p95_vals else 0.0,
        "max_users": max(users) if users else 0,
        "duration": int(t[-1]) if t else 0,
    }
    kpis["error_rate"] = (
        (kpis["total_fail"] / kpis["total_req"] * 100) if kpis["total_req"] else 0.0
    )

    return {
        "t": t,
        "rps": rps,
        "fail_s": fail_s,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "users": users,
        "total_req": total_req,
        "endpoints": endpoint_series,
        "kpis": kpis,
    }


# 라이트 테마 공통 스타일(단일·비교 리포트 공유).
_BASE_CSS = """
  :root {
    --bg: #ffffff; --fg: #111827; --muted: #6b7280;
    --line: #e5e7eb; --line-soft: #f3f4f6; --card: #ffffff;
    --good: #16a34a; --warn: #d97706; --bad: #dc2626;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font-family: "Pretendard Variable", Pretendard, -apple-system, BlinkMacSystemFont,
      system-ui, "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
    padding: 32px clamp(16px, 5vw, 64px) 64px;
    font-feature-settings: "tnum";
  }
  header {
    display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;
    border-bottom: 1px solid var(--line); padding-bottom: 16px; margin-bottom: 28px;
  }
  h1 { font-size: clamp(19px, 2.4vw, 26px); margin: 0; font-weight: 700; letter-spacing: -0.01em; }
  header .meta { color: var(--muted); font-size: 13px; margin-left: auto; }
  .verdict { font-weight: 600; font-size: 12px; padding: 2px 10px; border-radius: 6px; }
  .verdict.pass { color: var(--good); background: #f0fdf4; border: 1px solid #bbf7d0; }
  .verdict.fail { color: var(--bad); background: #fef2f2; border: 1px solid #fecaca; }
  .panel {
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 18px 18px 8px; margin-bottom: 18px;
  }
  .panel h2 {
    margin: 0 4px 10px; font-size: 14px; font-weight: 600; color: var(--fg);
    letter-spacing: -0.005em;
  }
  .chart { width: 100%; height: 320px; }
  footer { color: var(--muted); font-size: 12px; margin-top: 28px; text-align: center; }
"""


_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} · 부하 리포트</title>
<link rel="stylesheet" href="{{ pretendard_href }}"
  integrity="{{ pretendard_sri }}" crossorigin="anonymous">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"
  integrity="{{ plotly_sri }}" crossorigin="anonymous"></script>
<style>
{{ base_css }}
  .kpis { display: grid; gap: 12px; margin-bottom: 24px;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
  .kpi { border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
  .kpi .label { color: var(--muted); font-size: 12px; }
  .kpi .value { font-size: 24px; font-weight: 700; margin-top: 6px; letter-spacing: -0.01em; }
  .kpi .unit { color: var(--muted); font-size: 13px; font-weight: 500; margin-left: 3px; }
  .kpi .value.warn { color: var(--warn); } .kpi .value.bad { color: var(--bad); }
</style>
</head>
<body>
<header>
  <h1>{{ title }}</h1>
  {% if passed is not none %}
  <span class="verdict {{ 'pass' if passed else 'fail' }}">{{ 'PASS' if passed else 'FAIL' }}</span>
  {% endif %}
  <span class="meta">{{ host }} · {{ generated }}</span>
</header>

<section class="kpis">
  <div class="kpi"><div class="label">총 요청</div><div class="value">{{ '{:,}'.format(k.total_req) }}</div></div>
  <div class="kpi"><div class="label">실패율</div>
    <div class="value {{ 'bad' if k.error_rate >= 1 else '' }}">{{ '%.2f'|format(k.error_rate) }}<span class="unit">%</span></div></div>
  <div class="kpi"><div class="label">최대 RPS</div><div class="value">{{ '%.0f'|format(k.peak_rps) }}</div></div>
  <div class="kpi"><div class="label">최대 p95</div>
    <div class="value {{ 'warn' if k.peak_p95 >= 300 else '' }}">{{ '%.0f'|format(k.peak_p95) }}<span class="unit">ms</span></div></div>
  <div class="kpi"><div class="label">최대 동시 사용자</div><div class="value">{{ k.max_users }}<span class="unit">명</span></div></div>
  <div class="kpi"><div class="label">실행 시간</div>
    <div class="value">{{ k.duration // 60 }}<span class="unit">분</span> {{ k.duration % 60 }}<span class="unit">초</span></div></div>
</section>

<div class="panel"><h2>처리량 (RPS) · 시간별</h2><div id="rps" class="chart"></div></div>
<div class="panel"><h2>응답시간 백분위 (ms) · 시간별</h2><div id="lat" class="chart"></div></div>
<div class="panel"><h2>동시 사용자 · 누적 요청</h2><div id="users" class="chart"></div></div>
<div class="panel"><h2>실패율 (failures/s) · 시간별</h2><div id="fail" class="chart"></div></div>

<footer>locust_stats_history.csv 기반 · 줌 드래그 / 더블클릭 리셋 / 범례 클릭 토글</footer>

<script>
const DATA = {{ data_json | safe }};
const FONT = '"Pretendard Variable", Pretendard, system-ui, sans-serif';
const GRID = "#eef1f4";
const baseLayout = (yTitle) => ({
  paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff",
  font: { color: "#374151", family: FONT, size: 12 },
  margin: { l: 56, r: 18, t: 8, b: 40 },
  xaxis: { title: "경과(초)", gridcolor: GRID, zerolinecolor: GRID, linecolor: "#d1d5db" },
  yaxis: { title: yTitle, gridcolor: GRID, zerolinecolor: GRID, rangemode: "tozero", linecolor: "#d1d5db" },
  legend: { orientation: "h", y: -0.25, font: { size: 11 } },
  hovermode: "x unified",
});
const CFG = { responsive: true, displayModeBar: false, displaylogo: false };

const rpsTraces = [{
  x: DATA.t, y: DATA.rps, name: "전체", mode: "lines",
  line: { color: "{{ c_primary }}", width: 2.5 }, fill: "tozeroy", fillcolor: "rgba(37,99,235,0.08)",
}];
const palette = ["{{ c_green }}", "{{ c_amber }}", "{{ c_violet }}", "{{ c_red }}", "#0891b2"];
Object.keys(DATA.endpoints).forEach((name, i) => {
  const e = DATA.endpoints[name];
  rpsTraces.push({ x: e.t, y: e.rps, name: name, mode: "lines",
    line: { color: palette[i % palette.length], width: 1.3, dash: "dot" } });
});
Plotly.newPlot("rps", rpsTraces, baseLayout("req/s"), CFG);

Plotly.newPlot("lat", [
  { x: DATA.t, y: DATA.p50, name: "p50", mode: "lines", line: { color: "{{ c_green }}", width: 1.8 } },
  { x: DATA.t, y: DATA.p95, name: "p95", mode: "lines", line: { color: "{{ c_amber }}", width: 2.4 } },
  { x: DATA.t, y: DATA.p99, name: "p99", mode: "lines", line: { color: "{{ c_red }}", width: 1.8 } },
], baseLayout("ms"), CFG);

Plotly.newPlot("users", [
  { x: DATA.t, y: DATA.users, name: "동시 사용자", mode: "lines",
    line: { color: "{{ c_primary }}", width: 2 }, fill: "tozeroy", fillcolor: "rgba(37,99,235,0.06)" },
  { x: DATA.t, y: DATA.total_req, name: "누적 요청", mode: "lines", yaxis: "y2",
    line: { color: "{{ c_violet }}", width: 1.8 } },
], Object.assign(baseLayout("사용자(명)"), {
  yaxis2: { title: "누적 요청", overlaying: "y", side: "right", showgrid: false, rangemode: "tozero" },
}), CFG);

Plotly.newPlot("fail", [
  { x: DATA.t, y: DATA.fail_s, name: "failures/s", mode: "lines",
    line: { color: "{{ c_red }}", width: 2 }, fill: "tozeroy", fillcolor: "rgba(220,38,38,0.08)" },
], baseLayout("fail/s"), CFG);
</script>
</body>
</html>
"""
)


def build_report(
    run_dir: Path,
    title: str,
    host: str = "",
    passed: Optional[bool] = None,
    generated: str = "",
) -> Optional[Path]:
    """run_dir의 history CSV로 report.html을 만들고 경로를 반환한다.

    데이터가 없으면(테스트가 요청을 거의 못 보냄) None을 반환한다.
    """
    history = run_dir / "locust_stats_history.csv"
    series = _read_series(history)
    if series is None:
        return None

    data_json = json.dumps(
        {
            "t": series["t"],
            "rps": series["rps"],
            "fail_s": series["fail_s"],
            "p50": series["p50"],
            "p95": series["p95"],
            "p99": series["p99"],
            "users": series["users"],
            "total_req": series["total_req"],
            "endpoints": series["endpoints"],
        },
        ensure_ascii=False,
    )

    html = _TEMPLATE.render(
        title=title,
        host=host,
        passed=passed,
        generated=generated,
        k=series["kpis"],
        data_json=data_json,
        base_css=_BASE_CSS,
        pretendard_href=_PRETENDARD_HREF,
        pretendard_sri=_PRETENDARD_SRI,
        plotly_sri=_PLOTLY_SRI,
        c_primary=_C_PRIMARY,
        c_green=_C_GREEN,
        c_amber=_C_AMBER,
        c_violet=_C_VIOLET,
        c_red=_C_RED,
    )
    out = run_dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


_COMPARE_TEMPLATE = Template(
    """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>실행 비교 · 부하 리포트</title>
<link rel="stylesheet" href="{{ pretendard_href }}"
  integrity="{{ pretendard_sri }}" crossorigin="anonymous">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"
  integrity="{{ plotly_sri }}" crossorigin="anonymous"></script>
<style>
{{ base_css }}
  table.runs { width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 13px; }
  table.runs th, table.runs td { text-align: right; padding: 9px 12px; border-bottom: 1px solid var(--line); }
  table.runs th:first-child, table.runs td:first-child { text-align: left; }
  table.runs th { color: var(--muted); font-weight: 600; }
  table.runs tbody tr:hover { background: var(--line-soft); }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 8px; vertical-align: middle; }
  .chart { height: 360px; }
</style>
</head>
<body>
<header>
  <h1>실행 비교</h1>
  <span class="meta">{{ runs|length }}개 실행 · {{ generated }}</span>
</header>

<table class="runs">
  <thead><tr><th>실행</th><th>총 요청</th><th>실패율</th><th>최대 RPS</th><th>최대 p95</th><th>최대 사용자</th><th>시간</th></tr></thead>
  <tbody>
  {% for r in runs %}
    <tr>
      <td><span class="swatch" style="background:{{ r.color }}"></span>{{ r.name }}</td>
      <td>{{ '{:,}'.format(r.kpis.total_req) }}</td>
      <td>{{ '%.2f'|format(r.kpis.error_rate) }}%</td>
      <td>{{ '%.0f'|format(r.kpis.peak_rps) }}</td>
      <td>{{ '%.0f'|format(r.kpis.peak_p95) }}ms</td>
      <td>{{ r.kpis.max_users }}명</td>
      <td>{{ r.kpis.duration // 60 }}:{{ '%02d'|format(r.kpis.duration % 60) }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>

<div class="panel"><h2>처리량 (RPS) · 실행 겹쳐 보기</h2><div id="rps" class="chart"></div></div>
<div class="panel"><h2>응답시간 p95 (ms) · 실행 겹쳐 보기</h2><div id="p95" class="chart"></div></div>

<footer>경과(초) 기준 정렬 · 줌 드래그 / 범례 클릭 토글</footer>

<script>
const RUNS = {{ data_json | safe }};
const FONT = '"Pretendard Variable", Pretendard, system-ui, sans-serif';
const GRID = "#eef1f4";
const layout = (yTitle) => ({
  paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff",
  font: { color: "#374151", family: FONT, size: 12 },
  margin: { l: 56, r: 18, t: 8, b: 40 },
  xaxis: { title: "경과(초)", gridcolor: GRID, linecolor: "#d1d5db" },
  yaxis: { title: yTitle, gridcolor: GRID, rangemode: "tozero", linecolor: "#d1d5db" },
  legend: { orientation: "h", y: -0.22, font: { size: 11 } }, hovermode: "x unified",
});
const CFG = { responsive: true, displayModeBar: false, displaylogo: false };
Plotly.newPlot("rps", RUNS.map(r => ({ x: r.t, y: r.rps, name: r.name, mode: "lines", line: { color: r.color, width: 2 } })), layout("req/s"), CFG);
Plotly.newPlot("p95", RUNS.map(r => ({ x: r.t, y: r.p95, name: r.name, mode: "lines", line: { color: r.color, width: 2 } })), layout("ms"), CFG);
</script>
</body>
</html>
"""
)

_COMPARE_COLORS = [_C_PRIMARY, _C_GREEN, _C_AMBER, _C_VIOLET, _C_RED, "#0891b2", "#db2777"]


def build_compare_report(
    run_dirs: list[Path], out: Path, generated: str = ""
) -> Optional[Path]:
    """여러 실행의 history CSV를 한 HTML에 겹쳐 그린다. 유효 데이터가 없으면 None."""
    runs = []
    for rd in run_dirs:
        series = _read_series(rd / "locust_stats_history.csv")
        if series is None:
            continue
        runs.append(
            {
                "name": rd.name,
                "color": _COMPARE_COLORS[len(runs) % len(_COMPARE_COLORS)],
                "t": series["t"],
                "rps": series["rps"],
                "p95": series["p95"],
                "kpis": series["kpis"],
            }
        )

    if not runs:
        return None

    html = _COMPARE_TEMPLATE.render(
        runs=runs,
        generated=generated,
        data_json=json.dumps(
            [
                {"name": r["name"], "color": r["color"], "t": r["t"], "rps": r["rps"], "p95": r["p95"]}
                for r in runs
            ],
            ensure_ascii=False,
        ),
        base_css=_BASE_CSS,
        pretendard_href=_PRETENDARD_HREF,
        pretendard_sri=_PRETENDARD_SRI,
        plotly_sri=_PLOTLY_SRI,
    )
    out.write_text(html, encoding="utf-8")
    return out
