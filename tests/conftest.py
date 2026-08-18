"""Test isolation from a developer's own credentials.

`make test` loads `.env` now, which is what a reader filling it in expects. It
also means a machine with real keys would run the suite against a live GitHub
token and a live Stripe key -- and this repo's whole job is placing orders and
moving money. A test suite that can do either by accident is not a test suite.

Every live credential is cleared for every test. A test that wants one passes it
explicitly.
"""

from __future__ import annotations

import pytest

LIVE_KEYS = ("CLIENT_GITHUB_TOKEN", "CLIENT_STRIPE_KEY", "FIRM_REPO", "FIRM_SITE")


@pytest.fixture(autouse=True)
def no_live_credentials(monkeypatch):
    for key in LIVE_KEYS:
        monkeypatch.delenv(key, raising=False)
