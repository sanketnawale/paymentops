"""Controlled XML reconstruction.

We never generate financial XML from an LLM. Given a securely-parsed XML tree and a list of
:class:`DiffEntry`, we deep-copy the tree, apply structured deterministic changes, and
serialize a candidate document. The original tree/object is never mutated. Unrelated fields
are preserved exactly.
"""

from __future__ import annotations

from copy import deepcopy

from lxml import etree

from repair_engine.models import ChangeStatus, DiffEntry

# PostalAddress24 child order (for inserting missing elements in schema-valid sequence).
_POSTAL_ADDRESS_ORDER = (
    "AdrTp",
    "Dept",
    "SubDept",
    "StrtNm",
    "BldgNb",
    "PstCd",
    "TwnNm",
    "Ctry",
    "AdrLine",
)


def apply_changes(
    root: etree._Element, changes: list[DiffEntry]
) -> tuple[etree._Element, list[DiffEntry]]:
    """Return a deep-copied tree with applied changes, plus the actually-applied entries."""
    tree = deepcopy(root)
    applied: list[DiffEntry] = []
    for change in changes:
        ok = _apply_one(tree, change)
        applied.append(
            DiffEntry(
                path=change.path,
                before=change.before,
                after=change.after,
                source=change.source,
                status=ChangeStatus.VALIDATED if ok else ChangeStatus.REJECTED,
            )
        )
    return tree, applied


def serialize(root: etree._Element, *, pretty: bool = True) -> str:
    return str(etree.tostring(root, encoding="unicode", pretty_print=pretty))


def _apply_one(root: etree._Element, change: DiffEntry) -> bool:
    element = _navigate(root, change.path)
    if element is not None:
        if change.after is None:
            element.text = None
        else:
            element.text = change.after
        return True

    # Element doesn't exist yet -> try to create it (e.g. a missing TwnNm / Ctry).
    created = _create_missing(root, change.path, change.after)
    return created is not None


def _navigate(root: etree._Element, path: str) -> etree._Element | None:
    """Navigate an XPath-like path such as ``/Document/.../Dbtr/PstlAdr/Ctry``."""
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None
    # If the path begins with the root element's name, start at the root itself.
    if _local(root.tag) == _strip_index(segments[0]):
        rest = segments[1:]
    else:
        rest = segments
    node: etree._Element = root
    for seg in rest:
        child = _child_by_local(node, seg)
        if child is None:
            return None
        node = child
    return node


def _child_by_local(node: etree._Element, segment: str) -> etree._Element | None:
    name, _sep, index_str = segment.partition("[")
    index = int(index_str.rstrip("]")) if index_str else 0
    matches = [c for c in node if _local(c.tag) == name]
    if index >= len(matches):
        return None
    return matches[index]


def _create_missing(root: etree._Element, path: str, value: str | None) -> etree._Element | None:
    """Create a missing leaf element (for PostalAddress24 children) in schema order."""
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        return None
    leaf = segments[-1]
    leaf_name = _strip_index(leaf)
    parent = _navigate(root, "/".join(segments[:-1]))
    if parent is None:
        return None
    if leaf_name not in _POSTAL_ADDRESS_ORDER:
        return None

    # Namespace of the parent (all ISO elements share the same namespace).
    ns = _ns(parent.tag)
    new_el = etree.SubElement(parent, f"{{{ns}}}{leaf_name}")
    new_el.text = value
    # Reorder children to respect schema sequence.
    _reorder_children(parent)
    return new_el


def _reorder_children(parent: etree._Element) -> None:
    order = _POSTAL_ADDRESS_ORDER
    # Stable sort by schema order; unknown names go last.
    parent[:] = sorted(
        parent, key=lambda c: order.index(_local(c.tag)) if _local(c.tag) in order else len(order)
    )


def _strip_index(segment: str) -> str:
    return segment.split("[", 1)[0]


def _local(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[1] if "}" in tag else tag


def _ns(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if "}" in tag else ""
