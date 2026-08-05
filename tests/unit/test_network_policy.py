from __future__ import annotations

import socket

import pytest


def test_unit_tests_cannot_open_network_connections() -> None:
    with pytest.raises(RuntimeError, match="network access is disabled"):
        socket.create_connection(("api.coingecko.com", 443))
