"""실행 결과 저장 규약: testing/results/<YYYY-MM-DD-HHMM>-<명령>/

- summary.json : 계획·지표·판정 (기계가 읽는 용도, 추이 비교)
- report.txt   : 화면 출력 그대로 (사람이 읽는 용도)
- 엔진 원본 산출물(Locust CSV, k6 JSON 등)은 각 명령이 이 폴더에 직접 둔다.
"""

import json
from datetime import datetime
from pathlib import Path

from testkit import config, ui


def make_run_dir(command: str) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    run_dir = config.RESULTS_DIR / f"{stamp}-{command}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save(run_dir: Path, summary: dict) -> None:
    """summary.json과 report.txt를 남기고 저장 위치를 화면에 알린다."""
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    (run_dir / "report.txt").write_text(ui.console.export_text(), encoding="utf-8")
    ui.console.print(f"\n  결과 저장: [bold]{run_dir.relative_to(config.TESTING_DIR.parent)}[/bold]")
