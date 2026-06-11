"""Locust 가상 사용자 정의 3종.

BrowsingUser: 일반 탐색 패턴 (예약 조회, 쿼터 조회, 예약 생성)
LoginUser: 로그인 반복 (bcrypt 병목 측정용)
InstantUser: 즉시 예약 쟁탈전 (높은 동시성)
"""

import os
import random
from datetime import datetime, timedelta, timezone

from locust import HttpUser, between, constant, task

from testkit import config


def _random_email() -> str:
    """계정 풀에서 무작위 이메일을 반환한다."""
    n = random.randint(1, config.SEED_USER_COUNT)
    return config.SEED_USER_EMAIL_FMT.format(n=n)


def _future_iso(offset_hours: float, duration_hours: float) -> tuple[str, str]:
    """현재 UTC 기준 미래 시각 범위를 ISO 8601 문자열로 반환한다."""
    now = datetime.now(timezone.utc)
    start = now + timedelta(hours=offset_hours)
    end = start + timedelta(hours=duration_hours)
    return start.isoformat(), end.isoformat()


def _server_ids() -> list[int]:
    """환경변수 SERVER_IDS에서 서버 id 목록을 읽는다. 없으면 빈 목록."""
    raw = os.environ.get("SERVER_IDS", "")
    if not raw.strip():
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


class BrowsingUser(HttpUser):
    """일반 사용자 탐색 패턴: 조회 위주에 가끔 예약을 시도한다."""

    wait_time = between(1, 3)
    _token: str = ""
    _team_id: int = 0

    def on_start(self) -> None:
        email = _random_email()
        with self.client.post(
            "/auth/login",
            json={"email": email, "password": config.SEED_PASSWORD},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                self._token = data["accessToken"]
                self._team_id = data["user"]["teamId"]
                resp.success()
            else:
                resp.failure(f"로그인 실패: {resp.status_code}")
                self.environment.runner.quit()

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    @task(5)
    def get_reservations(self) -> None:
        """예약 목록 조회."""
        with self.client.get(
            "/reservations",
            headers=self._auth_headers(),
            catch_response=True,
            name="/reservations [GET]",
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"서버 오류: {resp.status_code}")
            else:
                resp.success()

    @task(2)
    def get_quotas(self) -> None:
        """팀 쿼터 조회."""
        with self.client.get(
            f"/teams/{self._team_id}/quotas",
            headers=self._auth_headers(),
            catch_response=True,
            name="/teams/{teamId}/quotas [GET]",
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"서버 오류: {resp.status_code}")
            else:
                resp.success()

    @task(1)
    def create_reservation(self) -> None:
        """서버 예약 생성. 409(충돌)/422(쿼터 부족)는 정상 동작으로 성공 처리한다."""
        servers = _server_ids()
        if not servers:
            return

        offset_hours = random.uniform(1, 72)
        duration_hours = random.uniform(1, 4)
        start_time, end_time = _future_iso(offset_hours, duration_hours)
        server_id = random.choice(servers)

        with self.client.post(
            "/reservations",
            json={"serverId": server_id, "startTime": start_time, "endTime": end_time},
            headers=self._auth_headers(),
            catch_response=True,
            name="/reservations [POST]",
        ) as resp:
            if resp.status_code in (201, 409, 422):
                resp.success()
            elif resp.status_code >= 500:
                resp.failure(f"서버 오류: {resp.status_code}")
            else:
                resp.success()


class LoginUser(HttpUser):
    """로그인만 반복하는 사용자. bcrypt 처리 성능 측정 전용.

    429(잠금 응답)도 정상 동작으로 성공 처리한다.
    """

    wait_time = between(1, 3)

    @task
    def login(self) -> None:
        email = _random_email()
        with self.client.post(
            "/auth/login",
            json={"email": email, "password": config.SEED_PASSWORD},
            catch_response=True,
            name="/auth/login [POST]",
        ) as resp:
            if resp.status_code in (200, 429):
                resp.success()
            elif resp.status_code >= 500:
                resp.failure(f"서버 오류: {resp.status_code}")
            else:
                resp.success()


class InstantUser(HttpUser):
    """즉시 예약 쟁탈전 사용자. 대기 없이 즉시 예약을 반복 시도한다.

    201(성공)/409(가용 서버 없음)/422(쿼터 부족)는 모두 정상 동작이다.
    서버 오류(5xx)만 실패로 기록한다.
    """

    wait_time = constant(0)
    _token: str = ""

    def on_start(self) -> None:
        email = _random_email()
        with self.client.post(
            "/auth/login",
            json={"email": email, "password": config.SEED_PASSWORD},
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                self._token = resp.json()["accessToken"]
                resp.success()
            else:
                resp.failure(f"로그인 실패: {resp.status_code}")
                self.environment.runner.quit()

    @task
    def instant_reserve(self) -> None:
        """즉시 예약 요청. 쟁탈전에서 409는 정상이다."""
        _, end_time = _future_iso(0, 1)
        with self.client.post(
            "/reservations/instant",
            json={"endTime": end_time},
            headers={"Authorization": f"Bearer {self._token}"},
            catch_response=True,
            name="/reservations/instant [POST]",
        ) as resp:
            if resp.status_code in (201, 409, 422):
                resp.success()
            elif resp.status_code >= 500:
                resp.failure(f"서버 오류: {resp.status_code}")
            else:
                resp.success()
