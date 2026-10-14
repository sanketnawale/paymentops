"""Unit tests for the repair engine (candidate generation, XML reconstruction, diff)."""

from __future__ import annotations

from tests.conftest import load_fixture

from iso_engine.xml_security import secure_parse
from repair_engine.models import ChangeSource, ChangeStatus, DiffEntry
from repair_engine.xml_reconstruction import apply_changes, serialize


def test_diff_entry_status_defaults_to_proposed():
    d = DiffEntry(path="/x", before=None, after="y", source=ChangeSource.ADDRESS_PROVIDER)
    assert d.status == ChangeStatus.PROPOSED


def test_apply_changes_sets_existing_element():
    doc = secure_parse(load_fixture("country_full_name"))
    change = DiffEntry(
        path="/Document/FIToFICstmrCdtTrf/CdtTrfTxInf[0]/Dbtr/PstlAdr/Ctry",
        before="Italy",
        after="IT",
        source=ChangeSource.ADDRESS_PROVIDER,
    )
    new_root, applied = apply_changes(doc.root, [change])
    xml = serialize(new_root)
    assert "Ctry>IT" in xml
    assert applied[0].status == ChangeStatus.VALIDATED


def test_apply_changes_creates_missing_element_in_order():
    doc = secure_parse(load_fixture("address_adrline_only"))
    change = DiffEntry(
        path="/Document/FIToFICstmrCdtTrf/CdtTrfTxInf[0]/Dbtr/PstlAdr/Ctry",
        before=None,
        after="IT",
        source=ChangeSource.ADDRESS_PROVIDER,
    )
    new_root, applied = apply_changes(doc.root, [change])
    xml = serialize(new_root)
    # Ctry must appear before AdrLine (schema order).
    assert xml.index("Ctry") < xml.index("AdrLine")
    assert applied[0].status == ChangeStatus.VALIDATED


def test_original_tree_not_mutated():
    doc = secure_parse(load_fixture("country_full_name"))
    before = serialize(doc.root)
    change = DiffEntry(
        path="/Document/FIToFICstmrCdtTrf/CdtTrfTxInf[0]/Dbtr/PstlAdr/Ctry",
        before="Italy",
        after="IT",
        source=ChangeSource.ADDRESS_PROVIDER,
    )
    apply_changes(doc.root, [change])
    after = serialize(doc.root)
    assert before == after


def test_generate_candidate_validated_for_normalizable():
    from address_engine.providers import CloudNovaAddressProvider
    from iso_engine.pacs008.adapter import map_pacs008_to_canonical
    from iso_engine.pacs008.identifier import identify_pacs008
    from payment_domain.models import CandidateStatus
    from repair_engine.generator import generate_candidate
    from rules_engine import build_address_ruleset

    doc = secure_parse(load_fixture("country_full_name"))
    version = identify_pacs008(doc.root)
    msg = map_pacs008_to_canonical(doc.root, version)
    cand = generate_candidate(
        msg, doc, address_provider=CloudNovaAddressProvider(), rules_engine=build_address_ruleset()
    )
    assert cand.status == CandidateStatus.VALIDATED
    assert any(c.path.endswith("/Ctry") and c.after == "IT" for c in cand.changes)
