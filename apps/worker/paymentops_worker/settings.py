"""Worker settings reusing the platform Settings (subset)."""

from __future__ import annotations

from functools import lru_cache

from paymentops_api.settings import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()
