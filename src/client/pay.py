"""The client agent settles its own invoices.

The firm never holds a credential that can move money: it gets a read-only
restricted key and watches ``/v1/charges``. The payer is the one that holds the
payment credential, which is the right way round -- a supplier who can charge
you at will is not a counterparty, it is a subscription.

Payment Links are hosted checkout and need a browser, so an agent cannot use
one. PaymentIntents can be created and confirmed over the API with a test
payment method, which is what makes this leg autonomous: no browser, no human,
no click. The resulting charge is a real Stripe object and flows through the
firm's ledger to its published P&L.

Sandbox only. ``pm_card_visa`` is a test payment method and exists nowhere else.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any

STRIPE_API = "https://api.stripe.com/v1"
TEST_PAYMENT_METHOD = "pm_card_visa"


class PaymentError(RuntimeError):
    """Settlement failed. The agent records it and does not retry blindly."""


def _post(path: str, key: str, form: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{STRIPE_API}{path}",
        data=urllib.parse.urlencode(form).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.load(exc)["error"]["message"]
        except Exception:
            detail = f"HTTP {exc.code}"
        raise PaymentError(detail) from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise PaymentError(f"{type(exc).__name__}") from exc


def to_minor_units(amount_usd: Decimal) -> int:
    """Stripe charges in cents. Below its $0.50 floor nothing can settle."""
    cents = int((amount_usd * 100).to_integral_value())
    if cents < 50:
        raise PaymentError(f"{amount_usd} is below Stripe's $0.50 minimum charge")
    return cents


def settle(
    amount_usd: Decimal,
    *,
    order_id: str,
    key: str | None = None,
    payment_method: str = TEST_PAYMENT_METHOD,
) -> dict[str, Any]:
    """Create and confirm a PaymentIntent in one call. Returns the result.

    ``order_id`` travels as metadata so the firm can attribute the charge to the
    work order without the two sides sharing a database.
    """
    key = key or os.environ.get("CLIENT_STRIPE_KEY", "").strip()
    if not key:
        raise PaymentError("CLIENT_STRIPE_KEY is not set")
    if not key.startswith("sk_test_"):
        # A live key here would move real money on an autonomous decision with
        # no human in the loop. Refuse rather than trust the caller.
        raise PaymentError("refusing to settle with a non-test key")

    intent = _post(
        "/payment_intents",
        key,
        {
            "amount": to_minor_units(amount_usd),
            "currency": "usd",
            "payment_method": payment_method,
            "confirm": "true",
            "automatic_payment_methods[enabled]": "true",
            "automatic_payment_methods[allow_redirects]": "never",
            "metadata[order_id]": order_id,
            "metadata[paid_by]": "client-agent",
            "description": f"Broker verdict for {order_id}",
        },
    )
    status = intent.get("status")
    if status != "succeeded":
        raise PaymentError(f"payment intent ended in status {status!r}")
    return {
        "id": intent.get("id", ""),
        "status": status,
        "amount_usd": str(amount_usd),
        "order_id": order_id,
        "livemode": bool(intent.get("livemode")),
    }
