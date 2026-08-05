"""Manual local workflow for collection, transforms, and dashboard startup."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from cryptopulse.coingecko import CoinGeckoClient
from cryptopulse.config import Settings
from cryptopulse.gold import build_gold
from cryptopulse.logging import configure_json_logging
from cryptopulse.silver import build_silver
from cryptopulse.storage import DATA_DIR, write_bronze

_JOB_ALIASES = {
    "market": "market_snapshot",
    "global": "global_market",
    "trending": "trending",
}


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    data_dir = Path(arguments.data_dir)

    if arguments.command == "collect":
        _load_env_file(Path(arguments.env_file))
        jobs = (
            ("market_snapshot", "global_market")
            if arguments.job == "all"
            else (_JOB_ALIASES[arguments.job],)
        )
        paths = collect(jobs, data_dir=data_dir)
        for path in paths:
            print(path)
        if arguments.job in {"market", "global", "all"}:
            _build_when_ready(data_dir)
        return 0

    if arguments.command == "build":
        build_silver(data_dir=data_dir)
        print(build_gold(data_dir=data_dir))
        return 0

    if arguments.command == "dashboard":
        environment = {**os.environ, "CRYPTOPULSE_DATA_DIR": str(data_dir.resolve())}
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(Path(__file__).with_name("dashboard.py")),
            ],
            check=True,
            env=environment,
        )
        return 0

    parser.error("unknown command")


def collect(jobs: tuple[str, ...], *, data_dir: Path = DATA_DIR) -> list[Path]:
    """Collect reviewed jobs sequentially under one run identity."""

    settings = Settings.from_env(require_api_key=True)
    assert settings.coingecko_api_key is not None
    logger = configure_json_logging(secrets=(settings.coingecko_api_key,))
    run_id = str(uuid4())
    paths: list[Path] = []
    with CoinGeckoClient(settings.coingecko_api_key, logger=logger) as client:
        for job_name in jobs:
            response = client.fetch(job_name, run_id=run_id)
            paths.append(write_bronze(response, job_name, data_dir=data_dir))
    return paths


def _build_when_ready(data_dir: Path) -> None:
    try:
        build_silver(data_dir=data_dir)
        output = build_gold(data_dir=data_dir)
    except FileNotFoundError:
        print("Silver/Gold chưa được build: cần cả market và global Bronze.")
    else:
        print(f"Gold đã cập nhật: {output}")


def _load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries without overwriting the process environment."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key.replace("_", "").isalnum():
            os.environ.setdefault(key, value.strip().strip("'\""))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cryptopulse")
    parser.add_argument("--data-dir", default=str(DATA_DIR), help="local runtime data directory")
    subcommands = parser.add_subparsers(dest="command", required=True)

    collect_parser = subcommands.add_parser("collect", help="collect one reviewed API job")
    collect_parser.add_argument("job", choices=(*_JOB_ALIASES, "all"))
    collect_parser.add_argument("--env-file", default=".env")

    subcommands.add_parser("build", help="rebuild Silver and Gold from local Bronze")
    subcommands.add_parser("dashboard", help="start the local Streamlit dashboard")
    return parser
