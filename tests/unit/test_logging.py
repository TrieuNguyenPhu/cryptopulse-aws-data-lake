from __future__ import annotations

import json
import logging
from io import StringIO

from cryptopulse.logging import REDACTED, configure_json_logging


def test_json_logging_redacts_headers_query_values_extras_and_known_secret() -> None:
    stream = StringIO()
    logger = configure_json_logging(
        logger=logging.getLogger("cryptopulse.test.redaction"),
        secrets=("fixture-secret",),
        stream=stream,
    )

    logger.info(
        "request x-cg-demo-api-key=fixture-secret",
        extra={
            "authorization": "Bearer fixture-secret",
            "parameters": {"x_cg_demo_api_key": "fixture-secret", "page": 1},
            "run_id": "run-1",
        },
    )

    output = stream.getvalue()
    document = json.loads(output)
    assert "fixture-secret" not in output
    assert REDACTED in document["message"]
    assert document["authorization"] == REDACTED
    assert document["parameters"]["x_cg_demo_api_key"] == REDACTED
    assert document["parameters"]["page"] == 1
    assert document["run_id"] == "run-1"
    assert document["timestamp"].endswith("Z")


def test_json_logging_redacts_exception_text() -> None:
    stream = StringIO()
    logger = configure_json_logging(
        logger=logging.getLogger("cryptopulse.test.exception"),
        secrets=("fixture-secret",),
        stream=stream,
    )

    try:
        raise RuntimeError("credential fixture-secret")
    except RuntimeError:
        logger.exception("safe failure")

    output = stream.getvalue()
    document = json.loads(output)
    assert "fixture-secret" not in output
    assert REDACTED in document["exception"]
