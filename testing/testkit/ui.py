"""Rich 출력 헬퍼. testkit의 화면 출력 규약은 전부 이 파일에 모은다.

모든 명령은 4단계로 출력한다:
  [1/4] 사전 점검 -> [2/4] 테스트 계획 -> [3/4] 실행 -> [4/4] 결과
record=True 콘솔이라 실행이 끝나면 results.save()가 출력 전체를 report.txt로 남긴다.
"""

import typer
from collections import deque
from typing import Optional

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

console = Console(record=True)

# 진행 대시보드 전용 콘솔. record=False 라서 라이브 프레임이 report.txt에 섞이지 않는다.
_progress_console = Console()

OK = "[green]✔[/green]"
NG = "[red]✖[/red]"

_SPARK = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int = 48) -> str:
    """수치 목록을 유니코드 스파크라인 문자열로 만든다(최근 width개)."""
    vals = list(values)[-width:]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    last = len(_SPARK) - 1
    return "".join(_SPARK[min(last, int((v - lo) / span * last))] for v in vals)


def _fmt_clock(seconds: float) -> str:
    """초를 mm:ss 로 포맷."""
    s = max(0, int(seconds))
    return f"{s // 60:d}:{s % 60:02d}"


class LiveDashboard:
    """실행 중 '실시간 공대 감성' 대시보드.

    단계 진행 바 + 라이브 KPI(RPS·p95·요청·실패·사용자) + RPS/p95 추세 스파크라인을
    한 패널에 그리고 1초 단위로 갱신한다. transient=True 라 끝나면 화면에서 사라지고,
    별도 콘솔(record=False)을 쓰므로 report.txt에는 남지 않는다.
    """

    def __init__(self, title: str, total_sec: Optional[int], num_stages: int) -> None:
        self.title = title
        self.total_sec = total_sec
        self.num_stages = num_stages
        self._rps_hist: deque[float] = deque(maxlen=48)
        self._p95_hist: deque[float] = deque(maxlen=48)
        self._live = Live(
            console=_progress_console, transient=True, refresh_per_second=8
        )

    def __enter__(self) -> "LiveDashboard":
        self._live.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._live.stop()

    def update(
        self,
        elapsed: float,
        stage: int,
        target_users: int,
        metrics: Optional[dict],
    ) -> None:
        if metrics:
            self._rps_hist.append(metrics["rps"])
            self._p95_hist.append(metrics["p95"])
        self._live.update(self._render(elapsed, stage, target_users, metrics))

    def _render(
        self,
        elapsed: float,
        stage: int,
        target_users: int,
        metrics: Optional[dict],
    ) -> Panel:
        # 1행: 단계 + 진행 바 + 퍼센트 + 남은 시간
        total = self.total_sec or max(1, int(elapsed))
        pct = min(100, int(elapsed / total * 100)) if self.total_sec else 0
        remain = (self.total_sec - elapsed) if self.total_sec else 0
        bar = ProgressBar(
            total=total, completed=min(elapsed, total), width=34,
            complete_style="cyan", finished_style="green",
        )
        head = Table.grid(padding=(0, 1))
        head.add_column(no_wrap=True)
        head.add_column(no_wrap=True)
        head.add_column(justify="right", no_wrap=True)
        stage_txt = (
            f"[bold cyan]단계 {stage}/{self.num_stages}[/bold cyan] [dim]·[/dim] 목표 {target_users}명"
            if self.num_stages
            else "[bold cyan]실행 중[/bold cyan]"
        )
        tail = f"[bold]{pct:3d}%[/bold]  [dim]남은[/dim] {_fmt_clock(remain)}" if self.total_sec else ""
        head.add_row(stage_txt, bar, tail)

        # 2행: KPI 카드
        m = metrics or {}
        kpi = Table.grid(padding=(0, 3))
        for _ in range(5):
            kpi.add_column(justify="left")

        def cell(label: str, value: str, color: str) -> str:
            return f"[dim]{label}[/dim]\n[bold {color}]{value}[/bold {color}]"

        if metrics:
            fail_color = "red" if m["fail"] else "green"
            p95_color = "yellow" if m["p95"] >= 300 else "green"
            kpi.add_row(
                cell("RPS", f"{m['rps']:.0f}", "cyan"),
                cell("p95", f"{m['p95']:.0f}ms", p95_color),
                cell("요청", f"{m['total']:,}", "white"),
                cell("실패", f"{m['fail']:,}", fail_color),
                cell("사용자", f"{m['users']}명", "cyan"),
            )
        else:
            kpi.add_row("[dim]지표 수집 중…[/dim]")

        # 3행: 추세 스파크라인
        spark = Table.grid(padding=(0, 1))
        spark.add_column(no_wrap=True)
        spark.add_column(no_wrap=True)
        spark.add_row(
            "[dim]RPS [/dim]", f"[cyan]{sparkline(self._rps_hist)}[/cyan]"
        )
        spark.add_row(
            "[dim]p95 [/dim]", f"[green]{sparkline(self._p95_hist)}[/green]"
        )

        body = Group(head, Text(""), kpi, Text(""), spark)
        return Panel(
            body,
            title=f"[bold]⚡ {self.title}[/bold] [dim]· 실시간[/dim]",
            title_align="left",
            border_style="cyan",
            padding=(1, 2),
        )


def phase(step: int, total: int, title: str) -> None:
    """단계 머리글. 예: [1/4] 사전 점검"""
    console.print(f"\n[bold cyan]\\[{step}/{total}][/bold cyan] [bold]{title}[/bold]")


def check_table(items: list) -> bool:
    """사전 점검 결과 표를 그리고 전부 통과했는지 반환한다.

    items: preflight.CheckItem 리스트 (name, ok, detail, hint 속성)
    """
    table = Table(show_header=False, box=None, padding=(0, 1))
    for it in items:
        mark = OK if it.ok else NG
        hint = f"[yellow]→ {it.hint}[/yellow]" if (not it.ok and it.hint) else ""
        table.add_row(f"  {mark}", it.name, it.detail, hint)
    console.print(table)
    return all(it.ok for it in items)


def plan(rows: dict[str, str]) -> None:
    """테스트 계획 표. '무엇을, 어떤 요청으로, 무엇을 측정, 무엇이면 합격'을 실행 전에 보여준다."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    for key, value in rows.items():
        table.add_row(f"  [bold]{key}[/bold]", value)
    console.print(table)


def metrics_table(title: str, rows: list[tuple[str, str]]) -> None:
    """결과 지표 표. rows: (지표 이름, 값)"""
    table = Table(title=title, title_justify="left", min_width=44)
    table.add_column("지표")
    table.add_column("값", justify="right")
    for name, value in rows:
        table.add_row(name, value)
    console.print(table)


def verdict(criteria: list[tuple[str, bool, str]]) -> bool:
    """합격 기준별 PASS/FAIL 표를 그리고 종합 판정을 반환한다.

    criteria: (기준 설명, 통과 여부, 상세 값)
    """
    table = Table(title="합격 판정", title_justify="left", min_width=44)
    table.add_column("기준")
    table.add_column("상세")
    table.add_column("판정", justify="center")
    for name, passed, detail in criteria:
        mark = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        table.add_row(name, detail, mark)
    console.print(table)

    overall = all(passed for _, passed, _ in criteria)
    color = "green" if overall else "red"
    label = "PASS" if overall else "FAIL"
    console.print(f"\n  종합 판정: [bold {color}]{label}[/bold {color}]")
    return overall


def fail_exit(message: str, code: int = 2) -> None:
    """치명적 실패를 출력하고 종료한다. 사전 점검 실패=2, 테스트 FAIL=1."""
    console.print(f"\n[bold red]중단:[/bold red] {message}")
    raise typer.Exit(code)
