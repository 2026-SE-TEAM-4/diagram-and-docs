"""결과 시각화 커맨드: chart.

각 실행 폴더의 locust_stats_history.csv로 만든 인터랙티브 HTML 리포트를 열거나,
여러 실행을 겹쳐 비교하는 대시보드를 만든다.

  testkit chart                  최신 실행의 report.html (없으면 생성) 경로 출력
  testkit chart --open           생성 후 브라우저로 열기
  testkit chart results/<dir>    특정 실행 지정
  testkit chart --list           최근 실행 목록
  testkit chart --compare 3      최근 3개 실행을 겹쳐 비교(compare-*.html)
"""

import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from testkit import config, report_html, ui

# 성능 4종만 시계열 CSV를 남긴다. 그 외(중단점/장애) 폴더는 대상에서 제외.
_SHAPE_SUFFIXES = ("-load", "-stress", "-spike", "-endurance")


def _run_dirs() -> list[Path]:
    """history CSV가 있는 실행 폴더를 최신순으로 반환한다."""
    if not config.RESULTS_DIR.exists():
        return []
    dirs = [
        d
        for d in config.RESULTS_DIR.iterdir()
        if d.is_dir()
        and d.name.endswith(_SHAPE_SUFFIXES)
        and (d / "locust_stats_history.csv").exists()
    ]
    return sorted(dirs, key=lambda d: d.name, reverse=True)


def _title_for(run_dir: Path) -> str:
    """폴더명 접미사로 제목을 만든다(예: ...-load → LOAD)."""
    for suffix in _SHAPE_SUFFIXES:
        if run_dir.name.endswith(suffix):
            return f"{suffix.lstrip('-').upper()} 테스트"
    return run_dir.name


def _rel(path: Path) -> str:
    return str(path.relative_to(config.TESTING_DIR.parent))


def register(app: typer.Typer) -> None:
    """chart 커맨드를 app에 등록한다."""

    @app.command()
    def chart(
        run_dir: Optional[Path] = typer.Argument(
            None, help="대상 실행 폴더. 생략하면 최신 실행."
        ),
        open_browser: bool = typer.Option(
            False, "--open", "-o", help="생성 후 브라우저로 연다."
        ),
        show_list: bool = typer.Option(
            False, "--list", "-l", help="최근 실행 목록만 출력한다."
        ),
        compare: Optional[int] = typer.Option(
            None, "--compare", "-c", help="최근 N개 실행을 겹쳐 비교한다."
        ),
    ) -> None:
        """[결과] 부하 테스트 시계열 CSV를 인터랙티브 HTML로 본다."""
        runs = _run_dirs()

        if show_list:
            ui.phase(1, 1, "최근 실행")
            if not runs:
                ui.console.print("  [yellow]시각화할 실행이 없습니다.[/yellow]")
                return
            for d in runs:
                has_html = (d / "report.html").exists()
                mark = ui.OK if has_html else "[dim]·[/dim]"
                ui.console.print(f"  {mark} {d.name}")
            return

        if compare is not None:
            if compare < 2:
                ui.fail_exit("비교는 최소 2개 실행이 필요합니다 (--compare 2 이상).", code=2)
            targets = runs[:compare]
            if len(targets) < 2:
                ui.fail_exit(
                    f"비교할 실행이 부족합니다(현재 {len(targets)}개). 테스트를 더 실행하세요.",
                    code=2,
                )
            ui.phase(1, 1, "실행 비교")
            stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
            out = config.RESULTS_DIR / f"compare-{stamp}.html"
            result = report_html.build_compare_report(
                targets, out, generated=datetime.now().strftime("%Y-%m-%d %H:%M")
            )
            if result is None:
                ui.fail_exit("비교할 시계열 데이터가 없습니다.", code=2)
            for d in targets:
                ui.console.print(f"  • {d.name}")
            ui.console.print(f"\n  비교 리포트: [bold]{_rel(result)}[/bold]")
            if open_browser:
                webbrowser.open(result.resolve().as_uri())
            return

        # 단일 실행 리포트
        target = run_dir if run_dir is not None else (runs[0] if runs else None)
        if target is None:
            ui.fail_exit("시각화할 실행이 없습니다. 먼저 부하 테스트를 실행하세요.", code=2)
        if not (target / "locust_stats_history.csv").exists():
            ui.fail_exit(f"history CSV가 없습니다: {_rel(target)}", code=2)

        ui.phase(1, 1, "리포트")
        out = report_html.build_report(
            target,
            title=_title_for(target),
            host=config.BACKEND_HOST,
            passed=None,
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        if out is None:
            ui.fail_exit("시계열 데이터가 비어 리포트를 만들 수 없습니다.", code=2)
        ui.console.print(f"  인터랙티브 리포트: [bold]{_rel(out)}[/bold]")
        if open_browser:
            webbrowser.open(out.resolve().as_uri())
        else:
            ui.console.print("  [dim]브라우저로 열거나 --open 옵션을 쓰세요.[/dim]")
