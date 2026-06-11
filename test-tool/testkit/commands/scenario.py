"""시나리오 점검 커맨드: 단일 요청 단언으로 보안/성능/안정성을 검증한다.

부하 테스트가 아니라 기능/단언 테스트다. 다른 명령과 동일한 4단계로 출력한다:
  [1/4] 사전 점검 -> [2/4] 테스트 계획 -> [3/4] 실행 -> [4/4] 결과
"""

from collections import Counter
from typing import Optional

import typer

from testkit import preflight, results, scenarios, ui

# 카테고리 한글 이름·색상(출력 일관성)
_CATEGORY_LABEL = {
    "security": "보안",
    "performance": "성능",
    "stability": "안정성",
}
_VALID_CATEGORIES = {"all", "security", "performance", "stability"}

_STATUS_MARK = {
    "PASS": "[green]PASS[/green]",
    "FAIL": "[red]FAIL[/red]",
    "SKIP": "[yellow]SKIP[/yellow]",
}


def _plan_rows(category: str) -> dict[str, str]:
    """실행 전 계획 표 내용."""
    target = "전체" if category == "all" else _CATEGORY_LABEL.get(category, category)
    return {
        "테스트 계획": "시나리오 점검(단일 요청 단언)",
        "대상": f"{target} 시나리오",
        "어떤 요청으로": "httpx 단건 호출 (시드 계정 loadtest001 로그인 재사용)",
        "무엇을 측정": "응답 상태코드 vs 기대 집합, 일부 응답시간",
        "합격 기준": "critical 시나리오 전부 통과(5xx·인증우회 없음). normal 실패는 경고.",
    }


def _print_live(res: scenarios.ScenarioResult) -> None:
    """시나리오 한 건이 끝날 때마다 한 줄로 출력(읽기 쉬운 진행 표시)."""
    mark = _STATUS_MARK.get(res.status, res.status)
    sev = "[dim](critical)[/dim]" if res.severity == "critical" else ""
    ui.console.print(f"    {mark}  {res.name} {sev}  [dim]{res.detail}[/dim]")


def _result_table(items: list[scenarios.ScenarioResult]) -> None:
    """카테고리별로 묶어 결과 표를 그린다."""
    from rich.table import Table

    table = Table(title="시나리오 결과", title_justify="left", min_width=60)
    table.add_column("카테고리")
    table.add_column("시나리오")
    table.add_column("상세")
    table.add_column("판정", justify="center")

    order = {"security": 0, "performance": 1, "stability": 2}
    for res in sorted(items, key=lambda r: (order.get(r.category, 9), r.name)):
        label = _CATEGORY_LABEL.get(res.category, res.category)
        table.add_row(label, res.name, res.detail, _STATUS_MARK.get(res.status, res.status))
    ui.console.print(table)


def _summarize(items: list[scenarios.ScenarioResult]) -> tuple[bool, Counter]:
    """종합 판정을 계산한다. critical FAIL이 하나라도 있으면 전체 FAIL."""
    counts: Counter = Counter(r.status for r in items)
    critical_fail = [
        r for r in items if r.status == "FAIL" and r.severity == "critical"
    ]
    overall = len(critical_fail) == 0
    return overall, counts


def register(app: typer.Typer) -> None:
    """시나리오 점검 커맨드를 app에 등록한다."""

    @app.command()
    def scenario(
        category: str = typer.Option(
            "all", "--category",
            help="실행 카테고리: security|performance|stability|all",
        ),
        no_preflight: bool = typer.Option(
            False, "--no-preflight", help="사전 점검을 건너뜁니다."
        ),
    ) -> None:
        """[3] 시나리오 점검 — 단일 요청 단언으로 보안/성능/안정성 검증."""
        if category not in _VALID_CATEGORIES:
            ui.fail_exit(
                f"--category는 {sorted(_VALID_CATEGORIES)} 중 하나여야 합니다. (입력: {category})",
                code=2,
            )

        run_dir = results.make_run_dir("scenario")

        # 1단계: 사전 점검 (백엔드만 사용하므로 에이전트 점검 불필요)
        preflight.run(agents=False, skip=no_preflight)

        # 2단계: 테스트 계획
        ui.phase(2, 4, "테스트 계획")
        ui.plan(_plan_rows(category))

        # 3단계: 실행 (한 건씩 라이브 출력)
        ui.phase(3, 4, "실행")
        ui.console.print(f"  결과 디렉터리: {run_dir.name}")
        items = scenarios.run_scenarios(category, on_result=_print_live)

        # 4단계: 결과
        ui.phase(4, 4, "결과")
        _result_table(items)

        overall, counts = _summarize(items)
        ui.metrics_table("시나리오 집계", [
            ("총 시나리오", str(len(items))),
            ("PASS", str(counts.get("PASS", 0))),
            ("FAIL", str(counts.get("FAIL", 0))),
            ("SKIP", str(counts.get("SKIP", 0))),
        ])

        # critical FAIL만 종합 FAIL로. normal FAIL은 경고로 표시.
        normal_fail = [
            r for r in items if r.status == "FAIL" and r.severity == "normal"
        ]
        if normal_fail:
            ui.console.print(
                f"  [yellow]경고: normal 시나리오 {len(normal_fail)}건 실패(종합 판정엔 미반영)[/yellow]"
            )
            for r in normal_fail:
                ui.console.print(f"    [yellow]· {r.name} — {r.detail}[/yellow]")

        color = "green" if overall else "red"
        label = "PASS" if overall else "FAIL"
        ui.console.print(f"\n  종합 판정: [bold {color}]{label}[/bold {color}]  [dim](critical 기준)[/dim]")

        summary = {
            "command": "scenario",
            "category": category,
            "counts": dict(counts),
            "overall_passed": overall,
            "results": [
                {
                    "name": r.name,
                    "category": r.category,
                    "severity": r.severity,
                    "status": r.status,
                    "detail": r.detail,
                }
                for r in items
            ],
        }
        results.save(run_dir, summary)

        if not overall:
            raise typer.Exit(1)
