"""camt.054 message identification."""

from __future__ import annotations

from typing import Any

from lxml import etree

from iso_engine.camt054.namespace import (
    KNOWN_CAMT_054_NAMESPACES,
    SUPPORTED_CAMT_054_VERSIONS,
)
from iso_engine.common import identify_message_version


def identify_camt054(root: etree._Element) -> Any:
    return identify_message_version(
        root,
        SUPPORTED_CAMT_054_VERSIONS,
        KNOWN_CAMT_054_NAMESPACES,
        "Ntfctn",
    )
