"""pacs.009 message identification."""

from __future__ import annotations

from typing import Any

from lxml import etree

from iso_engine.common import identify_message_version
from iso_engine.pacs009.namespace import (
    KNOWN_PACS_009_NAMESPACES,
    SUPPORTED_PACS_009_VERSIONS,
)


def identify_pacs009(root: etree._Element) -> Any:
    return identify_message_version(
        root,
        SUPPORTED_PACS_009_VERSIONS,
        KNOWN_PACS_009_NAMESPACES,
        "FICdtTrf",
    )
