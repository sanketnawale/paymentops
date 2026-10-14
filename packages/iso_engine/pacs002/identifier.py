"""pacs.002 message identification."""

from __future__ import annotations

from typing import Any

from lxml import etree

from iso_engine.common import identify_message_version
from iso_engine.pacs002.namespace import (
    KNOWN_PACS_002_NAMESPACES,
    SUPPORTED_PACS_002_VERSIONS,
)


def identify_pacs002(root: etree._Element) -> Any:
    return identify_message_version(
        root,
        SUPPORTED_PACS_002_VERSIONS,
        KNOWN_PACS_002_NAMESPACES,
        "FIToFIPmtStsRpt",
    )
