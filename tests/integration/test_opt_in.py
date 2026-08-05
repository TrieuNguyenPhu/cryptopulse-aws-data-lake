from __future__ import annotations

import os
import socket

import pytest


@pytest.mark.integration
def test_integration_suite_requires_explicit_opt_in() -> None:
    if os.getenv("CRYPTOPULSE_RUN_INTEGRATION") != "1":
        pytest.skip("set CRYPTOPULSE_RUN_INTEGRATION=1 to run external integration tests")
    assert os.getenv("CRYPTOPULSE_ALLOW_LIVE_API") != "1", (
        "Phase 1 integration must not enable live CoinGecko calls"
    )
    with pytest.raises(RuntimeError, match="external network access is disabled"):
        socket.create_connection(("api.coingecko.com", 443))
