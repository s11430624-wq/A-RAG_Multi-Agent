import os
import pytest

def test_gateway_smoke_requires_explicit_opt_in():
    if os.getenv("ARAG_RUN_LIVE_GATEWAY") != "1" or os.getenv("ARAG_ALLOW_SINGLE_PROBE") != "1":
        pytest.skip("set ARAG_RUN_LIVE_GATEWAY=1 and ARAG_ALLOW_SINGLE_PROBE=1 to opt in")
