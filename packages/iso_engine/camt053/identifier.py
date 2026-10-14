"""camt.053 message identification."""

from __future__ import annotations

from typing import Any

from lxml import etree

from iso_engine.camt053.namespace import (
    KNOWN_CAMT_053_NAMESPACES,
    SUPPORTED_CAMT_053_VERSIONS,
)
from iso_engine.common import identify_message_version


def identify_camt053(root: etree._Element) -> Any:
    return identify_message_version(
        root,
        SUPPORTED_CAMT_053_VERSIONS,
        KNOWN_CAMT_053_NAMESPACES,
        "Stmt",
    )
