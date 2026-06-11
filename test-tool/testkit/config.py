"""testkit 전역 설정값. 환경에 따라 바뀌는 값은 전부 여기에 모은다."""

import os
from pathlib import Path

# 경로
TESTING_DIR = Path(__file__).resolve().parent.parent       # testing/
RESULTS_DIR = TESTING_DIR / "results"
ENGINES_DIR = Path(__file__).resolve().parent / "engines"  # testkit/engines/

# 백엔드
BACKEND_HOST = os.environ.get("TESTKIT_HOST", "http://localhost:8000")

# server-pool 에이전트 (에이전트 번호 -> 포트)
AGENT_HOST = os.environ.get("TESTKIT_AGENT_HOST", "http://localhost")
AGENT_PORTS = {1: 9101, 2: 9102, 3: 9103}

# DB 직접 접속 (정합성 검증·시드용. backend/docker-compose.yml 기본값과 동일)
DB_DSN = os.environ.get("TESTKIT_DB_DSN", "postgresql://app:app@localhost:5432/app")

# docker compose 컨테이너 이름 부분 일치 패턴 (프로젝트명-서비스-번호 형식)
BACKEND_CONTAINERS = ["api", "postgres", "redis", "scheduler"]
AGENT_CONTAINER_FMT = "agent-{n}"   # server-pool-agent-1-1 등에 부분 일치

# 시드 기본값
SEED_PASSWORD = "password123"       # backend/scripts/seed.py와 동일한 개발용 비밀번호
SEED_TEAM_CODE = "LOADTEST"
SEED_USER_COUNT = 50                # 부하 테스트용 계정 수
SEED_QUOTA_LIMIT = 3                # 계정당 쿼터 한도
SEED_USER_EMAIL_FMT = "loadtest{n:03d}@example.com"
