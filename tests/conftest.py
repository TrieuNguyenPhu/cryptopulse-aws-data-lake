from __future__ import annotations

import json
import os
import socket
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture() -> Callable[[str], Any]:
    def load(name: str) -> Any:
        return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))

    return load


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    is_integration = request.node.get_closest_marker("integration") is not None
    is_live_api = request.node.get_closest_marker("live_api") is not None
    integration_enabled = os.getenv("CRYPTOPULSE_RUN_INTEGRATION") == "1"
    live_api_enabled = os.getenv("CRYPTOPULSE_ALLOW_LIVE_API") == "1"
    if is_integration and is_live_api and integration_enabled and live_api_enabled:
        return

    # Spark and local integration services need loopback sockets. External access remains
    # blocked unless a live-api test has both explicit opt-in flags.
    if "glue" in Path(str(request.node.path)).parts or (is_integration and integration_enabled):
        original_create_connection = socket.create_connection
        original_connect = socket.socket.connect

        def local_create_connection(
            address: tuple[str, int], *args: object, **kwargs: object
        ) -> socket.socket:
            if address[0] not in {"127.0.0.1", "::1", "localhost"}:
                raise RuntimeError("external network access is disabled in tests")
            return original_create_connection(address, *args, **kwargs)

        def local_connect(instance: socket.socket, address: tuple[str, int]) -> None:
            if address[0] not in {"127.0.0.1", "::1", "localhost"}:
                raise RuntimeError("external network access is disabled in tests")
            original_connect(instance, address)

        monkeypatch.setattr(socket, "create_connection", local_create_connection)
        monkeypatch.setattr(socket.socket, "connect", local_connect)
        return

    def blocked(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("network access is disabled in tests")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
