"""Demo-tenant tooling tests: FK-safe reset ordering and admin CLI guards."""

from __future__ import annotations

from scripts.reset_demo import _deletion_order
from scripts.user_admin import _password_from_env


def test_deletion_order_deletes_children_before_parents():
    tables = ["payment_cases", "case_actions", "iso_messages"]
    edges = [("case_actions", "payment_cases"), ("iso_messages", "payment_cases")]
    order = _deletion_order(tables, edges)
    assert order.index("case_actions") < order.index("payment_cases")
    assert order.index("iso_messages") < order.index("payment_cases")
    assert set(order) == set(tables)


def test_deletion_order_handles_cycles_without_losing_tables():
    order = _deletion_order(["a", "b"], [("a", "b"), ("b", "a")])
    assert set(order) == {"a", "b"}
    assert len(order) == 2


def test_password_env_requires_min_length(monkeypatch):
    monkeypatch.delenv("PAYMENTOPS_USER_PASSWORD", raising=False)
    assert _password_from_env() is None
    monkeypatch.setenv("PAYMENTOPS_USER_PASSWORD", "short")
    assert _password_from_env() is None
    monkeypatch.setenv("PAYMENTOPS_USER_PASSWORD", "a-sufficiently-long-password")
    assert _password_from_env() == "a-sufficiently-long-password"
