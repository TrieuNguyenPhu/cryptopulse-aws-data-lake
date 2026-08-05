"""Typed runtime settings with safe defaults."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, cast

DEFAULT_AWS_REGION = "ap-southeast-1"
COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"

Environment = Literal["dev", "demo"]
_AWS_REGION_PATTERN = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-\d$")


class SettingsError(ValueError):
    """Raised when runtime settings violate the project contract."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated settings shared by local and AWS entry points."""

    environment: Environment = "dev"
    aws_region: str = DEFAULT_AWS_REGION
    timezone: str = "UTC"
    coingecko_base_url: str = COINGECKO_BASE_URL
    coingecko_api_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.environment not in {"dev", "demo"}:
            raise SettingsError("environment must be 'dev' or 'demo'")
        if not _AWS_REGION_PATTERN.fullmatch(self.aws_region):
            raise SettingsError("aws_region is not a valid AWS region name")
        if self.timezone != "UTC":
            raise SettingsError("CryptoPulse timestamps and schedules must use UTC")
        if self.coingecko_base_url != COINGECKO_BASE_URL:
            raise SettingsError("only the CoinGecko Demo API base URL is allowed")
        if self.coingecko_api_key is not None and not self.coingecko_api_key.strip():
            raise SettingsError("COINGECKO_API_KEY cannot be blank")

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        require_api_key: bool = False,
    ) -> Settings:
        """Build settings without loading dotenv files or printing secrets."""

        source = os.environ if environ is None else environ
        environment_value = source.get("CRYPTOPULSE_ENVIRONMENT", "dev")
        if environment_value not in {"dev", "demo"}:
            raise SettingsError("CRYPTOPULSE_ENVIRONMENT must be 'dev' or 'demo'")

        api_key_value = source.get("COINGECKO_API_KEY")
        api_key = api_key_value.strip() if api_key_value else None
        if require_api_key and api_key is None:
            raise SettingsError("COINGECKO_API_KEY is required")

        return cls(
            environment=cast(Environment, environment_value),
            aws_region=source.get(
                "AWS_REGION",
                source.get("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION),
            ),
            timezone=source.get("CRYPTOPULSE_TIMEZONE", "UTC"),
            coingecko_api_key=api_key,
        )
