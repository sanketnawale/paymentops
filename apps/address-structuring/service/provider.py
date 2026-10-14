"""Wraps the upstream address-structuring pipeline for town/country inference.

This is the ONLY module that touches upstream `data_structuring` internals. It is isolated
behind the internal service's HTTP interface.

Resource provisioning: the upstream engine requires a reference database derived from
GeoNames/restCountries data (towns parquet, aliases, postcodes). This data is NOT bundled; it
is mounted at ``/resources``. If it (or the model) is absent, the provider reports NOT READY
and PaymentOps falls back to the CloudNova provider.

No raw address is ever logged here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("paymentops.address-structuring")

RESOURCES_DIR = Path("/resources")


class ProviderNotReadyError(RuntimeError):
    """Raised when the upstream engine cannot be initialised (resources missing)."""


@dataclass(frozen=True)
class StructureResult:
    town: str | None
    country: str | None
    town_confidence: float | None
    country_confidence: float | None
    town_raw: str | None
    country_raw: str | None
    suggested_country: str | None
    force_suggested_country: bool
    diagnostics: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "town": self.town,
            "country": self.country,
            "town_confidence": self.town_confidence,
            "country_confidence": self.country_confidence,
            "town_raw": self.town_raw,
            "country_raw": self.country_raw,
            "suggested_country": self.suggested_country,
            "force_suggested_country": self.force_suggested_country,
            "diagnostics": self.diagnostics,
        }


class SwiftStructureProvider:
    """Lazily loads the upstream pipeline; exposes town/country inference."""

    def __init__(self, resources_dir: Path = RESOURCES_DIR) -> None:
        self._resources_dir = resources_dir
        self._pipeline = None
        self._reason: str | None = None
        self._try_init()

    def _ensure_ready(self) -> None:
        """Retry initialization if not ready (handles transient startup timing)."""
        if self._pipeline is None:
            self._try_init()

    def _try_init(self) -> None:
        try:
            import os

            os.environ["DS_PREFIX_FOLDER_PATH"] = str(self._resources_dir)
            # CRFConfig does NOT prepend the prefix, so model paths must be absolute.
            os.environ["DS_MODEL_WEIGHTS_PATH"] = str(
                self._resources_dir / "models" / "CRF_with_MLP_EPOCH_1.safetensors"
            )
            os.environ["DS_MODEL_CONFIG_PATH"] = str(
                self._resources_dir / "models" / "CRF_with_MLP_EPOCH_1.config.json"
            )

            from data_structuring.pipeline import AddressStructuringPipeline

            self._pipeline = AddressStructuringPipeline()
        except Exception as exc:  # noqa: BLE001 - provider availability is a runtime concern
            logger.warning("swift_provider_not_ready: %s", type(exc).__name__)
            self._pipeline = None
            self._reason = type(exc).__name__

    @property
    def ready(self) -> bool:
        self._ensure_ready()
        return self._pipeline is not None

    @property
    def reason(self) -> str | None:
        return self._reason

    def structure(
        self, text: str, *, suggested_country: str | None = None, force: bool = False
    ) -> StructureResult:
        self._ensure_ready()
        if self._pipeline is None:
            raise ProviderNotReadyError(self._reason or "provider not initialised")

        from data_structuring.components.readers.base_reader import AddressSample

        reader = ListReader(
            [
                AddressSample(
                    text=text, suggested_country=suggested_country, force_suggested_country=force
                )
            ]
        )
        results = self._pipeline.run(reader, batch_size=1)
        if not results:
            return StructureResult(None, None, None, None, None, None, suggested_country, force, {})

        result = results[0]
        country, country_conf, country_raw = result.i_th_best_match_country(0)
        town, town_conf, town_raw = result.i_th_best_match_town(0)

        diagnostics = {
            "suggested_country": result.suggested_country,
            "force_suggested_country": result.force_suggested_country,
            "country_confidence": country_conf,
            "town_confidence": town_conf,
        }
        return StructureResult(
            town=town,
            country=country,
            town_confidence=town_conf if isinstance(town_conf, float) else None,
            country_confidence=country_conf if isinstance(country_conf, float) else None,
            town_raw=town_raw,
            country_raw=country_raw,
            suggested_country=result.suggested_country,
            force_suggested_country=result.force_suggested_country,
            diagnostics=diagnostics,
        )


# Imported here to avoid import cycle and to keep upstream imports lazy.
from service.reader import ListReader  # noqa: E402
