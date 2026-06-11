"""Rich 출력 헬퍼. testkit의 화면 출력 규약은 전부 이 파일에 모은다.

모든 명령은 4단계로 출력한다:
  [1/4] 사전 점검 -> [2/4] 테스트 계획 -> [3/4] 실행 -> [4/4] 결과
record=True 콘솔이라 실행이 끝나면 results.save()가 출력 전체를 report.txt로 남긴다.
"""

import typer
from rich.console import Console
from rich.table import Table

console = Console(record=True)

OK = "[green]✔[/green]"
NG = "[red]✖[/red]"


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
