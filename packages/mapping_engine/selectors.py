"""Controlled source selectors for the mapping engine.

Supports a strict subset of JSONPath, XPath (via lxml), and CSV column names. No arbitrary
code execution. Selectors are validated by the mapping validator before use.
"""

from __future__ import annotations

import re
from typing import Any

from lxml import etree


def resolve_json_path(data: Any, path: str) -> list[Any]:
    """Resolve a restricted JSONPath (``$.a.b[*].c``, ``$.a[0].b``) to a list of values."""
    tokens = _tokenize(path)
    current: list[Any] = [data]
    for token in tokens:
        nxt: list[Any] = []
        for item in current:
            if token.kind == "key":
                if isinstance(item, dict) and token.value in item:
                    nxt.append(item[token.value])
            elif token.kind == "index":
                if isinstance(item, (list, tuple)) and 0 <= token.value < len(item):
                    nxt.append(item[token.value])
            elif token.kind == "wildcard":
                if isinstance(item, (list, tuple)):
                    nxt.extend(item)
                elif isinstance(item, dict):
                    nxt.extend(item.values())
            elif token.kind == "all":
                if isinstance(item, (list, tuple)):
                    nxt.extend(item)
        current = nxt
    return current


def resolve_xpath(element: etree._Element, path: str) -> list[str]:
    """Resolve an XPath expression against an lxml element, returning text values."""
    try:
        nodes = element.xpath(path)
    except (etree.XPathError, etree.XPathSyntaxError):
        return []
    if not isinstance(nodes, list):
        return []
    values: list[str] = []
    for node in nodes:
        if isinstance(node, etree._Element):
            values.append((node.text or "").strip())
        else:
            values.append(str(node).strip())
    return [v for v in values if v]


def resolve_csv(row: dict[str, str], column: str) -> str | None:
    """Resolve a CSV column by name from a row dict."""
    return row.get(column)


class _Token:
    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value: Any) -> None:
        self.kind = kind
        self.value = value


def _tokenize(path: str) -> list[_Token]:
    tokens: list[_Token] = []
    # Split into segments while preserving [n] / [*] brackets.
    parts = re.findall(r"([A-Za-z0-9_\-]+)|\[\*\]|\[(\d+)\]", path)
    for key, index in parts:
        if key:
            tokens.append(_Token("key", key))
        elif index:
            tokens.append(_Token("index", int(index)))
        else:
            tokens.append(_Token("wildcard", None))
    return tokens
