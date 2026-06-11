"""DB 정합성 검사 3종. 부하 테스트가 만든 데이터가 규칙을 깼는지 직접 확인한다.

asyncpg로 config.DB_DSN에 접속해 SQL로만 판정한다 (백엔드를 거치지 않음).
  (a) 서버 초과 배정 — 한 서버에 활성 예약은 1건 이하 (낙관적 락이 동작했는가)
  (b) 쿼터 초과     — 팀별 quota.used 가 quota."limit" 를 넘지 않았는가 (핵심: 경쟁 조건)
  (c) 카운터 일치   — quota.used 가 실제 활성 예약 수와 같은가

활성 상태(active status)는 RESERVED, IN_USE 두 가지로 정의한다.
spike 명령이 run_checks()를 재사용하므로, 화면 출력 없이 결과만 반환하는 함수를 따로 둔다.
"""

import asyncio

import asyncpg

from testkit import config, results, ui

# 활성 예약으로 간주하는 상태값. 이 둘만 서버를 실제로 점유한다.
ACTIVE_STATUSES = ("RESERVED", "IN_USE")

# 결과 표/판정에서 너무 길어지지 않도록 위반 행은 이 개수까지만 보여준다.
MAX_ROWS_SHOWN = 5


async def _check_server_overbooking(conn: asyncpg.Connection) -> tuple[str, bool, str]:
    """(a) 활성 예약이 2건 이상인 서버를 찾는다. 하나라도 있으면 초과 배정."""
    rows = await conn.fetch(
        """
        SELECT server_id, COUNT(*) AS active_count
        FROM reservation
        WHERE status = ANY($1::text[])
        GROUP BY server_id
        HAVING COUNT(*) > 1
        ORDER BY active_count DESC
        """,
        list(ACTIVE_STATUSES),
    )
    passed = len(rows) == 0
    if passed:
        detail = "초과 배정 서버 없음 (서버당 활성 예약 ≤ 1)"
    else:
        sample = ", ".join(f"server {r['server_id']}={r['active_count']}건" for r in rows[:MAX_ROWS_SHOWN])
        detail = f"초과 배정 서버 {len(rows)}대: {sample}"
    return "서버 초과 배정 없음", passed, detail


async def _check_quota_limit(conn: asyncpg.Connection) -> tuple[str, bool, str]:
    """(b) quota.used 가 quota.\"limit\" 를 초과한 행을 찾는다. 핵심 경쟁 조건 검사."""
    rows = await conn.fetch(
        """
        SELECT user_id, team_id, used, "limit"
        FROM quota
        WHERE used > "limit"
        ORDER BY used - "limit" DESC
        """,
    )
    passed = len(rows) == 0
    if passed:
        detail = "쿼터 초과 없음 (used ≤ limit)"
    else:
        sample = ", ".join(
            f"user {r['user_id']} used={r['used']}>limit={r['limit']}" for r in rows[:MAX_ROWS_SHOWN]
        )
        detail = f"쿼터 초과 {len(rows)}건: {sample}"
    return "쿼터 한도 준수", passed, detail


async def _check_quota_counter(conn: asyncpg.Connection) -> tuple[str, bool, str]:
    """(c) quota.used 가 해당 사용자의 실제 활성 예약 수와 일치하는지 확인한다."""
    rows = await conn.fetch(
        """
        SELECT q.user_id, q.used,
               COALESCE(r.active_count, 0) AS actual
        FROM quota q
        LEFT JOIN (
            SELECT user_id, COUNT(*) AS active_count
            FROM reservation
            WHERE status = ANY($1::text[])
            GROUP BY user_id
        ) r ON r.user_id = q.user_id
        WHERE q.used <> COALESCE(r.active_count, 0)
        ORDER BY ABS(q.used - COALESCE(r.active_count, 0)) DESC
        """,
        list(ACTIVE_STATUSES),
    )
    passed = len(rows) == 0
    if passed:
        detail = "카운터 일치 (quota.used == 실제 활성 예약 수)"
    else:
        sample = ", ".join(
            f"user {r['user_id']} used={r['used']}≠actual={r['actual']}" for r in rows[:MAX_ROWS_SHOWN]
        )
        detail = f"카운터 불일치 {len(rows)}건: {sample}"
    return "쿼터 카운터 일치", passed, detail


async def run_checks() -> list[tuple[str, bool, str]]:
    """3종 검사를 실행하고 (기준 설명, 통과 여부, 상세) 리스트를 반환한다.

    화면에 아무것도 출력하지 않는다. spike 명령이 결과를 그대로 verdict에 접합할 수 있게 한다.
    """
    conn = await asyncpg.connect(config.DB_DSN)
    try:
        return [
            await _check_server_overbooking(conn),
            await _check_quota_limit(conn),
            await _check_quota_counter(conn),
        ]
    finally:
        await conn.close()


def verify_command() -> None:
    """testkit verify 진입점. 단독 실행 시 머리글·판정표·결과 저장까지 처리한다."""
    ui.phase(1, 1, "DB 정합성 검사")
    criteria = asyncio.run(run_checks())
    overall = ui.verdict(criteria)

    run_dir = results.make_run_dir("verify")
    results.save(run_dir, {
        "command": "verify",
        "active_statuses": list(ACTIVE_STATUSES),
        "criteria": [
            {"name": name, "passed": passed, "detail": detail}
            for name, passed, detail in criteria
        ],
        "overall": "PASS" if overall else "FAIL",
    })

    if not overall:
        ui.fail_exit("DB 정합성 검사 실패. 위 위반 내역을 확인하세요.", code=1)
