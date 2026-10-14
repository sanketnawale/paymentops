"""FastAPI application factory for PaymentOps."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from paymentops_api.db.base import Database
from paymentops_api.errors import register_exception_handlers
from paymentops_api.evolus import EvolusClient
from paymentops_api.logging import configure_logging, get_logger
from paymentops_api.middleware import (
    CorrelationIdMiddleware,
    MetricsMiddleware,
    SecurityHeadersMiddleware,
)
from paymentops_api.observability import MetricAddressProvider
from paymentops_api.routers import (
    account,
    analyze,
    audit,
    auth,
    batches,
    cases,
    clients,
    dashboard,
    health,
    info,
    integrations,
    investigations,
    iso,
    matching,
    metrics,
    profiles,
)
from paymentops_api.settings import Settings, get_settings

from address_engine.base import AddressProvider
from address_engine.providers import (
    CloudNovaAddressProvider,
    FallbackAddressProvider,
    SwiftDerivedAddressProvider,
)
from analysis import AnalysisPipeline
from iso_engine import build_default_registry
from rules_engine import build_address_ruleset

logger = get_logger("paymentops.app")


def build_address_provider(settings: Settings) -> AddressProvider:
    """Select the address provider based on settings.

    - cloudnova: deterministic provider (always available).
    - swift: Swift-derived provider (requires the internal component).
    - auto: Swift-derived when ``swift_address_url`` is configured, else CloudNova.
    When the Swift provider is used, wrap it in a fallback so the request never fails.
    """
    use_swift = settings.address_provider == "swift" or (
        settings.address_provider == "auto" and bool(settings.swift_address_url)
    )
    if use_swift:
        swift = SwiftDerivedAddressProvider(
            settings.swift_address_url,
            timeout_seconds=settings.swift_address_timeout,
            max_retries=settings.swift_address_max_retries,
        )
        return FallbackAddressProvider(swift, CloudNovaAddressProvider())
    return CloudNovaAddressProvider()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(settings.app_log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("application_started", version=settings.app_version)
        try:
            yield
        finally:
            await app.state.db.dispose()
            logger.info("application_stopped")

    app = FastAPI(
        title=settings.api_title,
        version=settings.app_version,
        description=(
            "CloudNova PaymentOps is a non-transactional payment-data intelligence "
            "platform. It does not execute, authorize, or settle payments."
        ),
        debug=settings.app_debug,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # Attach DB + settings at build time so they are available even without a running
    # lifespan (e.g. ASGITransport in tests) and so routes use THIS app's settings rather
    # than a globally-cached instance.
    app.state.settings = settings
    app.state.db = Database(settings)

    # --- Middleware (order matters: outermost last) ---
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    cors_origins = settings.cors_allowed_origins
    if settings.is_production:
        cors_origins = [
            origin for origin in cors_origins if origin not in ("http://localhost:3000", "*")
        ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins else [],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    if settings.metrics_enabled:
        app.add_middleware(MetricsMiddleware, settings=settings)

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(info.router)
    app.include_router(metrics.router)
    app.include_router(analyze.router)
    app.include_router(profiles.router)
    app.include_router(integrations.router)
    app.include_router(clients.router)
    app.include_router(cases.router)
    app.include_router(batches.router)
    app.include_router(dashboard.router)
    app.include_router(matching.router)
    app.include_router(iso.router)
    app.include_router(account.router)
    app.include_router(audit.router)
    app.include_router(auth.router)
    app.include_router(investigations.router)

    # Attach the analysis pipeline (deterministic engines) so routes can use it.
    provider = build_address_provider(settings)
    metric_label = (
        "swift_derived"
        if settings.address_provider == "swift"
        or (settings.address_provider == "auto" and bool(settings.swift_address_url))
        else "cloudnova"
    )
    app.state.analysis_pipeline = AnalysisPipeline(
        address_provider=MetricAddressProvider(provider, label=metric_label),
        rules_engine=build_address_ruleset(),
    )
    app.state.iso_registry = build_default_registry()
    app.state.evolus_client = EvolusClient(settings)

    return app
