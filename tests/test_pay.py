"""Settlement: the client pays, and refuses to pay with the wrong credential."""

from __future__ import annotations

from decimal import Decimal

import pytest

from client.pay import PaymentError, to_minor_units


@pytest.mark.parametrize(
    ("usd", "cents"),
    [("0.50", 50), ("1.00", 100), ("0.99", 99), ("19.00", 1900)],
)
def test_amounts_convert_to_cents(usd, cents):
    assert to_minor_units(Decimal(usd)) == cents


@pytest.mark.parametrize("usd", ["0.00", "0.01", "0.49"])
def test_below_stripes_floor_is_refused_before_any_network_call(usd):
    # Stripe rejects charges under $0.50. Catching it here means a doomed
    # payment never leaves the process.
    with pytest.raises(PaymentError, match="minimum charge"):
        to_minor_units(Decimal(usd))


def test_settling_without_a_credential_fails_closed(monkeypatch):
    monkeypatch.delenv("CLIENT_STRIPE_KEY", raising=False)
    from client.pay import settle

    with pytest.raises(PaymentError, match="not set"):
        settle(Decimal("1.00"), order_id="wo-1")


def test_a_live_key_is_refused(monkeypatch):
    # An agent settling autonomously with no human in the loop must not be able
    # to reach live money. This is the guard, not a convention.
    monkeypatch.setenv("CLIENT_STRIPE_KEY", "sk_live_pretend")
    from client.pay import settle

    with pytest.raises(PaymentError, match="non-test key"):
        settle(Decimal("1.00"), order_id="wo-1")


def test_a_restricted_read_key_cannot_settle(monkeypatch):
    # The firm's key is rk_ and read-only; if it ever leaked into the payer's
    # slot the failure should be immediate and obvious.
    monkeypatch.setenv("CLIENT_STRIPE_KEY", "rk_test_readonly")
    from client.pay import settle

    with pytest.raises(PaymentError, match="non-test key"):
        settle(Decimal("1.00"), order_id="wo-1")
