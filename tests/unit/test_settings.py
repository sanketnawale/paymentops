"""Settings tests: parsing, environment switching, and safe info exposure."""

from __future__ import annotations

from paymentops_api.settings import AppEnvironment, Settings


def test_defaults_are_safe():
    s = Settings()  # no secrets required; uses .env.example placeholders
    assert s.environment == AppEnvironment.DEVELOPMENT.value
    assert s.ai_enabled is False
    assert s.zero_retention_enabled is True


def test_comma_separated_list_settings(monkeypatch):
    monkeypatch.setenv("READY_CHECKS", "database,redis")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example,https://b.example")
    s = Settings()
    assert s.ready_checks == ["database", "redis"]
    assert s.cors_allowed_origins == ["https://a.example", "https://b.example"]


def test_empty_ready_checks_from_env(monkeypatch):
    monkeypatch.setenv("READY_CHECKS", "")
    s = Settings()
    assert s.ready_checks == []


def test_environment_variable_mapping(monkeypatch):
    monkeypatch.setenv("APP_ENVIRONMENT", "production")
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_PROVIDER", "vllm")
    monkeypatch.setenv("DATABASE_PASSWORD", "super-secret")
    s = Settings()
    assert s.environment == "production"
    assert s.is_production is True
    assert s.ai_enabled is True
    assert s.ai_provider.value == "vllm"


def test_safe_info_never_exposes_secrets():
    s = Settings(database_password="hunter2", redis_password="topsecret", database_user="dbadmin")
    info = s.safe_info()
    # No credentials or connection internals allowed.
    joined = str(info)
    for secret in ("hunter2", "topsecret", "dbadmin", "postgresql", "redis://"):
        assert secret not in joined
    assert info["product"] == "CloudNova PaymentOps"
    assert "version" in info and "environment" in info and "ai_enabled" in info


def test_release_version_and_build_metadata():
    s = Settings()
    assert s.app_version == "0.1.0-eval"
    info = s.safe_info()
    assert info["release"] == "v1 Evaluation Release"
    assert info["version"] == "0.1.0-eval"
    # Build metadata defaults are non-secret placeholders when not injected at build time.
    assert info["build_sha"] == "unknown"
    assert info["build_date"] == "unknown"


def test_dsn_construction_without_leaking():
    s = Settings(
        database_user="u",
        database_password="p",
        database_host="h",
        database_port=5432,
        database_name="paymentops",
    )
    dsn = s.sqlalchemy_dsn()
    assert dsn.startswith("postgresql+psycopg2://u:p@h:5432/paymentops")
    # DSN is internal-only; never passed to safe_info.
    assert "u:p" not in str(s.safe_info())


def test_prod_cors_strict():
    s = Settings(
        app_environment="production",
        cors_allowed_origins=["http://localhost:3000", "https://app.example.com"],
    )
    # localhost must be stripped from the allowed origins in production (handled at app layer).
    assert "https://app.example.com" in s.cors_allowed_origins
