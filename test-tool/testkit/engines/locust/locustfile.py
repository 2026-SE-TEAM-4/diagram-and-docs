"""Locust 진입점. SHAPE 환경변수로 시나리오와 사용자 클래스를 선택한다.

SHAPE 값:
  load      - BrowsingUser + LoadShape
  stress    - BrowsingUser + LoginUser + StressShape
  spike     - InstantUser + SpikeShape
  endurance - BrowsingUser + EnduranceShape

locust는 이 모듈에서 LoadTestShape 서브클래스 1개와 HttpUser 서브클래스를 자동으로 찾는다.
선택된 클래스만 모듈 네임스페이스에 남기고 나머지는 삭제해 locust가 오직 해당 클래스만 인식하게 한다.

testkit 패키지가 editable 설치되어 있으므로 절대 import를 사용한다.
"""

import os
import sys

from testkit.engines.locust.shapes import (
    EnduranceShape,
    LoadShape,
    SpikeShape,
    StressShape,
)
from testkit.engines.locust.users import BrowsingUser, InstantUser, LoginUser

_SHAPE = os.environ.get("SHAPE", "load").lower()

if _SHAPE == "load":
    # BrowsingUser 한 종류만 남긴다.
    del LoginUser, InstantUser
    del StressShape, SpikeShape, EnduranceShape
    # LoadShape는 이미 import되어 있으므로 그대로 둔다.

elif _SHAPE == "stress":
    # BrowsingUser + LoginUser 두 종류를 남긴다.
    del InstantUser
    del LoadShape, SpikeShape, EnduranceShape
    # StressShape는 그대로.

elif _SHAPE == "spike":
    # InstantUser 한 종류만 남긴다.
    del BrowsingUser, LoginUser
    del LoadShape, StressShape, EnduranceShape
    # SpikeShape는 그대로.

elif _SHAPE == "endurance":
    # BrowsingUser 한 종류만 남긴다.
    del LoginUser, InstantUser
    del LoadShape, StressShape, SpikeShape
    # EnduranceShape는 그대로.

else:
    print(
        f"알 수 없는 SHAPE: {_SHAPE!r}. load/stress/spike/endurance 중 하나를 지정하세요.",
        file=sys.stderr,
    )
    sys.exit(1)
