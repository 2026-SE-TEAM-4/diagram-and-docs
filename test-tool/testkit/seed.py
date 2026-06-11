"""시드 데이터 투입: 모든 테스트가 같은 초기 데이터에서 출발하게 한다.

- 팀·서버 3대(에이전트 1~3에 대응)·쿼터는 DB에 직접 넣는다 (관리 API가 없으므로).
- 부하용 계정은 POST /auth/register API로 만든다 (비밀번호 해싱을 백엔드에 맡김).
여러 번 실행해도 안전하다(있으면 건너뜀).
"""

import asyncio

import asyncpg
import httpx

from testkit import config, ui


async def _ensure_team_and_servers(conn: asyncpg.Connection) -> int:
    """부하 테스트용 팀과 서버 3대를 보장하고 team_id를 반환한다."""
    team_id = await conn.fetchval("SELECT id FROM team WHERE code = $1", config.SEED_TEAM_CODE)
    if team_id is None:
        team_id = await conn.fetchval(
            "INSERT INTO team (name, code, total_quota_limit, created_at) "
            "VALUES ($1, $2, $3, now()) RETURNING id",
            "LoadTest", config.SEED_TEAM_CODE, config.SEED_USER_COUNT * config.SEED_QUOTA_LIMIT,
        )
        ui.console.print(f"  팀 생성: {config.SEED_TEAM_CODE} (id={team_id})")
    else:
        ui.console.print(f"  팀 존재: {config.SEED_TEAM_CODE} (id={team_id})")

    for n in config.AGENT_PORTS:
        name = f"agent-{n}"
        exists = await conn.fetchval("SELECT 1 FROM server WHERE name = $1", name)
        if not exists:
            await conn.execute(
                "INSERT INTO server (name, ip, cpu_cores, ram_gb, status, version, created_at) "
                "VALUES ($1, $2, 8, 32, 'AVAILABLE', 1, now())",
                name, f"127.0.0.{n}",
            )
            ui.console.print(f"  서버 생성: {name}")
    return team_id


async def _register_users(team_id: int) -> int:
    """부하용 계정을 API로 등록한다. 이미 있으면(409) 건너뛴다."""
    created = 0
    async with httpx.AsyncClient(base_url=config.BACKEND_HOST, timeout=30) as client:
        for n in range(1, config.SEED_USER_COUNT + 1):
            email = config.SEED_USER_EMAIL_FMT.format(n=n)
            resp = await client.post("/auth/register", json={
                "name": f"부하테스트{n:03d}",
                "email": email,
                "password": config.SEED_PASSWORD,
                "role": "STU",
                "teamId": team_id,
            })
            if resp.status_code == 201:
                created += 1
            elif resp.status_code != 409:
                ui.fail_exit(f"계정 등록 실패 {email}: {resp.status_code} {resp.text}")
    return created


async def _ensure_quotas(conn: asyncpg.Connection, team_id: int) -> None:
    """시드 계정마다 쿼터 행을 보장한다 (없으면 limit=SEED_QUOTA_LIMIT로 생성)."""
    await conn.execute(
        """
        INSERT INTO quota (user_id, team_id, "limit", used, version)
        SELECT u.id, u.team_id, $2, 0, 1
        FROM "user" u
        WHERE u.team_id = $1 AND NOT EXISTS (SELECT 1 FROM quota q WHERE q.user_id = u.id)
        """,
        team_id, config.SEED_QUOTA_LIMIT,
    )


async def run() -> None:
    conn = await asyncpg.connect(config.DB_DSN)
    try:
        team_id = await _ensure_team_and_servers(conn)
        created = await _register_users(team_id)
        await _ensure_quotas(conn, team_id)
    finally:
        await conn.close()
    ui.console.print(
        f"  시드 완료: 계정 {config.SEED_USER_COUNT}개 중 신규 {created}개 "
        f"(비밀번호 {config.SEED_PASSWORD}, 쿼터 한도 {config.SEED_QUOTA_LIMIT})"
    )


def seed_command() -> None:
    """testkit seed 진입점."""
    asyncio.run(run())
