"""pain.001 message identification."""

from __future__ import annotations

from typing import Any

from lxml import etree

from iso_engine.common import identify_message_version
from iso_engine.pain001.namespace import (
    KNOWN_PAIN_001_NAMESPACES,
    SUPPORTED_PAIN_001_VERSIONS,
)


def identify_pain001(root: etree._Element) -> Any:
    return identify_message_version(
        root,
        SUPPORTED_PAIN_001_VERSIONS,
        KNOWN_PAIN_001_NAMESPACES,
        "CstmrCdtTrfInitn",
    )
