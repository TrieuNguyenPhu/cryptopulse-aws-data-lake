from __future__ import annotations

import os
from pathlib import Path

import pytest

from cryptopulse import cli


def test_env_file_loads_simple_values_without_overwriting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# local only\nCOINGECKO_API_KEY='from-file'\nINVALID KEY=ignored\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("COINGECKO_API_KEY", "from-process")

    cli._load_env_file(env_file)

    assert os.environ["COINGECKO_API_KEY"] == "from-process"
    assert "INVALID KEY" not in os.environ


def test_collect_command_maps_alias_and_reports_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "market.json.gz"
    captured: list[tuple[tuple[str, ...], Path]] = []

    def fake_collect(jobs: tuple[str, ...], *, data_dir: Path) -> list[Path]:
        captured.append((jobs, data_dir))
        return [output]

    monkeypatch.setattr(cli, "collect", fake_collect)
    monkeypatch.setattr(cli, "_build_when_ready", lambda _data_dir: None)

    result = cli.main(["--data-dir", str(tmp_path), "collect", "market"])

    assert result == 0
    assert captured == [(("market_snapshot",), tmp_path)]
    assert str(output) in capsys.readouterr().out
