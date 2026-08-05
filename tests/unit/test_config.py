from __future__ import annotations

import pytest

from cryptopulse.config import COINGECKO_BASE_URL, Settings, SettingsError


def test_settings_defaults_are_safe() -> None:
    settings = Settings.from_env({})

    assert settings.environment == "dev"
    assert settings.aws_region == "ap-southeast-1"
    assert settings.timezone == "UTC"
    assert settings.coingecko_base_url == COINGECKO_BASE_URL
    assert settings.coingecko_api_key is None


def test_settings_read_key_without_exposing_it_in_repr() -> None:
    settings = Settings.from_env(
        {
            "CRYPTOPULSE_ENVIRONMENT": "demo",
            "AWS_DEFAULT_REGION": "us-east-1",
            "COINGECKO_API_KEY": "  fixture-secret  ",
        },
        require_api_key=True,
    )

    assert settings.coingecko_api_key == "fixture-secret"
    assert "fixture-secret" not in repr(settings)


@pytest.mark.parametrize(
    ("environment", "message"),
    [
        ({"CRYPTOPULSE_ENVIRONMENT": "prod"}, "CRYPTOPULSE_ENVIRONMENT"),
        ({"AWS_REGION": "not-a-region"}, "aws_region"),
        ({"CRYPTOPULSE_TIMEZONE": "Asia/Saigon"}, "UTC"),
    ],
)
def test_settings_reject_invalid_environment_values(
    environment: dict[str, str], message: str
) -> None:
    with pytest.raises(SettingsError, match=message):
        Settings.from_env(environment)


def test_settings_require_api_key_without_revealing_a_value() -> None:
    with pytest.raises(SettingsError, match="COINGECKO_API_KEY is required"):
        Settings.from_env({}, require_api_key=True)


def test_settings_reject_alternate_api_host() -> None:
    with pytest.raises(SettingsError, match="Demo API"):
        Settings(coingecko_base_url="https://pro-api.coingecko.com/api/v3")
