"""Tests for the Settings list parsing used by CORS_ORIGINS / ALLOWED_HOSTS.

These directly verify the Pydantic Settings V2 behavior that caused the
production 400: a comma-separated env string must be parsable into a
List[str] and MUST include the localhost development origins.
"""
import os

from app.core.config import Settings


def test_settings_parse_comma_separated_string():
    """A comma-separated CORS_ORIGINS env string must parse into a list."""
    s = Settings(
        _env_file=None,
        CORS_ORIGINS="http://localhost:3000,http://localhost:5173",
    )
    assert s.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:5173"]


def test_settings_parse_json_array_string():
    """A JSON-array CORS_ORIGINS env string must parse into the list."""
    s = Settings(
        _env_file=None,
        CORS_ORIGINS='["http://localhost:3000","https://bitebrew.netlify.app"]',
    )
    assert s.CORS_ORIGINS == ["http://localhost:3000", "https://bitebrew.netlify.app"]


def test_settings_parse_single_origin_string():
    s = Settings(_env_file=None, CORS_ORIGINS="http://localhost:3000")
    assert s.CORS_ORIGINS == ["http://localhost:3000"]


def test_settings_parse_mixed_with_whitespace():
    s = Settings(
        _env_file=None,
        CORS_ORIGINS="  http://localhost:3000 , https://bitebrew.netlify.app  ",
    )
    assert s.CORS_ORIGINS == ["http://localhost:3000", "https://bitebrew.netlify.app"]


def test_settings_parse_empty_env_uses_default():
    """If no env override, the default list (all four origins) is used."""
    os.environ.pop("CORS_ORIGINS", None)
    s = Settings(_env_file=None)
    assert "http://localhost:3000" in s.CORS_ORIGINS
    assert "http://localhost:5173" in s.CORS_ORIGINS
    assert "http://127.0.0.1:3000" in s.CORS_ORIGINS
    assert "https://bitebrew.netlify.app" in s.CORS_ORIGINS


def test_settings_allowed_hosts_parse():
    s = Settings(_env_file=None, ALLOWED_HOSTS="localhost,127.0.0.1,0.0.0.0")
    assert "localhost" in s.ALLOWED_HOSTS
    assert "0.0.0.0" in s.ALLOWED_HOSTS
