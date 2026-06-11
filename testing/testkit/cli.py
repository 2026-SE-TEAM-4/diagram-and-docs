"""testkit 진입점. 서브커맨드 등록만 담당하고 로직은 각 모듈에 둔다.

사용법: uv run testkit --help
"""

import typer

from testkit import preflight, seed, ui
from testkit.commands import breakpoint as breakpoint_cmd
from testkit.commands import fault as fault_cmd
from testkit.commands import loadtest as loadtest_cmd
from testkit.commands import report as report_cmd
from testkit.commands import scenario as scenario_cmd

app = typer.Typer(
    help="SE Team 4 테스트 CLI — 사전 점검 + 부하/중단점/장애 테스트 + 다듬어진 결과",
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def check() -> None:
    """사전 점검만 단독 실행한다 (백엔드·에이전트·docker·k6)."""
    preflight.run(agents=True, need_k6=True, need_docker=True)
    ui.console.print("\n  모든 점검 통과. 테스트를 시작할 수 있습니다.")


@app.command(name="seed")
def seed_cmd() -> None:
    """시드 데이터를 투입한다 (팀·서버 3대·부하용 계정·쿼터)."""
    preflight.run(agents=False)
    ui.phase(2, 2, "시드 투입")
    seed.seed_command()


@app.command()
def verify() -> None:
    """DB 정합성 검사 3종만 단독 실행한다 (초과 배정·쿼터 초과·카운터 일치)."""
    from testkit import verify as verify_mod
    verify_mod.verify_command()


# 성능 4종(load/stress/spike/endurance), 중단점, 장애 주입은 각 모듈이 등록한다.
loadtest_cmd.register(app)
breakpoint_cmd.register(app)
fault_cmd.register(app)
report_cmd.register(app)
scenario_cmd.register(app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
