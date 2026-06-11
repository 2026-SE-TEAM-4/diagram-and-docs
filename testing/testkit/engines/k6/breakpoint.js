// 중단점(breakpoint) 부하 스크립트.
// 동시 사용자를 0명에서 500명까지 10분에 걸쳐 선형으로 올린다.
// 목적은 합격/불합격이 아니라 "몇 명에서 무너지는지"를 찾는 것.
//
// 환경변수:
//   TARGET_PATH = login | reserve | read  (어떤 흐름에 부하를 줄지)
//   BASE_URL    = 백엔드 주소 (예: http://localhost:8000)
//   PEAK_VU     = 최대 동시 사용자 수 (강도 배율이 적용된 값, 기본 500)
//
// 결과는 k6 json 출력(raw.json)으로 남기고, 파이썬 쪽에서 10초 버킷으로 분석한다.

import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

// 시드 계정 수(loadtest001~loadtest050). __VU를 이 범위로 돌려 계정을 분산한다.
const SEED_USER_COUNT = 50;

// 예약 충돌(409)은 실패가 아니라 정상 동작이므로 따로 센다.
const conflict409 = new Counter('conflict_409');

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const TARGET_PATH = __ENV.TARGET_PATH || 'login';
// 강도 배율이 적용된 최대 동시 사용자 수. 파이썬 쪽에서 PEAK_VU로 넘긴다(기본 500).
const PEAK_VU = parseInt(__ENV.PEAK_VU, 10) || 500;

export const options = {
  scenarios: {
    breakpoint: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [{ duration: '10m', target: PEAK_VU }],
    },
  },
};

// __VU 번호로 시드 계정 이메일을 고른다 (001~050 순환).
function seedEmail() {
  const n = ((__VU - 1) % SEED_USER_COUNT) + 1;
  return `loadtest${String(n).padStart(3, '0')}@example.com`;
}

// 로그인해서 accessToken을 돌려준다. 실패하면 null.
function login() {
  const res = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ email: seedEmail(), password: 'password123' }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(res, { 'login 200': (r) => r.status === 200 });
  if (res.status !== 200) return null;
  try {
    return res.json('accessToken');
  } catch (e) {
    return null;
  }
}

// 예약 1건을 만든다. 시작 시각을 __VU/__ITER로 흩어 충돌을 줄인다.
function reserve(token) {
  const base = Date.now() + (__VU * 3600 + __ITER * 60) * 1000;
  const start = new Date(base).toISOString();
  const end = new Date(base + 30 * 60 * 1000).toISOString();
  const res = http.post(
    `${BASE_URL}/reservations`,
    JSON.stringify({ serverId: ((__VU - 1) % 3) + 1, startTime: start, endTime: end }),
    {
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
    },
  );
  if (res.status === 409) conflict409.add(1);
  check(res, { 'reserve 201/409': (r) => r.status === 201 || r.status === 409 });
}

// 예약 목록을 읽는다.
function read(token) {
  const res = http.get(`${BASE_URL}/reservations`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  check(res, { 'read 200': (r) => r.status === 200 });
}

export default function () {
  if (TARGET_PATH === 'login') {
    login();
    return;
  }

  // reserve/read는 토큰이 필요하므로 매 반복마다 로그인 후 본 요청을 보낸다.
  const token = login();
  if (!token) return;

  if (TARGET_PATH === 'reserve') {
    reserve(token);
  } else if (TARGET_PATH === 'read') {
    read(token);
  }
}
