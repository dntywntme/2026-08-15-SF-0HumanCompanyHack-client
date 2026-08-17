"""The unattended loop: read what Broker published, judge it, decide to pay.

Nothing here touches the network. ``fetch_published`` is stubbed, which is the
seam the trust boundary actually has -- we consume the counterparty's published
JSON and validate it, so the interesting cases are the ones where that JSON is
not what we expected.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from client import agent as agent_mod
from client.agent import MANDATE_CEILING_USD, fetch_deliverable, update_activity
from client.channel import ChannelError
from client.http import SchemeRefused, open_https

MANIFEST = {"stages": ["00-intake", "01-comply", "07-deliver", "08-market"]}
DELIVER = {
    "output": {
        "deliverable": {
            "work_order_id": "wo-1",
            "answer": "Headline B wins.",
            "sourced_from": "agent+human",
            "cogs_usd": "9.00",
            "price_usd": "1.00",
            "margin_usd": "-8.00",
        }
    }
}


def _stub(monkeypatch, responses):
    def fake(url, timeout=20.0):
        for suffix, payload in responses.items():
            if url.endswith(suffix):
                if isinstance(payload, Exception):
                    raise payload
                return payload
        raise ChannelError(f"unexpected fetch: {url}")

    monkeypatch.setattr(agent_mod, "fetch_published", fake)


def test_the_deliverable_is_found_through_the_manifest(monkeypatch):
    # Not by guessing a filename: the pipeline's shape has changed once already
    # and a hard-coded 05-deliver.json would have stopped resolving.
    _stub(monkeypatch, {"index.json": MANIFEST, "07-deliver.json": DELIVER})
    d = fetch_deliverable(site="https://example.com")
    assert d.work_order_id == "wo-1"
    assert d.price_usd == Decimal("1.00")


def test_extra_fields_from_the_firm_do_not_break_us(monkeypatch):
    payload = json.loads(json.dumps(DELIVER))
    payload["output"]["deliverable"]["a_field_we_have_never_seen"] = True
    _stub(monkeypatch, {"index.json": MANIFEST, "07-deliver.json": payload})
    assert fetch_deliverable(site="https://example.com").answer == "Headline B wins."


def test_a_run_with_no_deliver_checkpoint_is_reported_not_guessed(monkeypatch):
    _stub(monkeypatch, {"index.json": {"stages": ["00-intake", "01-comply"]}})
    with pytest.raises(ChannelError, match="no deliver checkpoint"):
        fetch_deliverable(site="https://example.com")


def test_a_malformed_deliverable_is_refused_by_our_own_contract(monkeypatch):
    broken = {"output": {"deliverable": {"work_order_id": "wo-1", "answer": ""}}}
    _stub(monkeypatch, {"index.json": MANIFEST, "07-deliver.json": broken})
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        fetch_deliverable(site="https://example.com")


def test_the_settle_lane_pays_only_what_it_judged_acceptable(monkeypatch, tmp_path, capsys):
    _stub(monkeypatch, {"index.json": MANIFEST, "07-deliver.json": DELIVER})
    monkeypatch.setattr(agent_mod, "ACTIVITY", tmp_path / "activity.json")
    paid = {}

    def fake_settle(amount, *, order_id, **kw):
        paid["amount"], paid["order_id"] = amount, order_id
        return {"id": "pi_test", "status": "succeeded", "livemode": False}

    monkeypatch.setattr(agent_mod, "settle", fake_settle)
    assert agent_mod.run_settle(dry_run=False) == 0
    assert paid == {"amount": Decimal("1.00"), "order_id": "wo-1"}


def test_the_settle_lane_declines_an_overpriced_deliverable(monkeypatch, tmp_path):
    dear = json.loads(json.dumps(DELIVER))
    dear["output"]["deliverable"]["price_usd"] = "39.00"
    _stub(monkeypatch, {"index.json": MANIFEST, "07-deliver.json": dear})
    monkeypatch.setattr(agent_mod, "ACTIVITY", tmp_path / "activity.json")

    def refuse(*a, **kw):
        raise AssertionError("must not settle a deliverable we declined")

    monkeypatch.setattr(agent_mod, "settle", refuse)
    assert agent_mod.run_settle(dry_run=False) == 0
    written = json.loads((tmp_path / "activity.json").read_text())
    assert written["evaluation"]["acceptable"] is False
    assert "settlement" not in written


def test_the_activity_record_is_written_by_the_agent(tmp_path):
    path = tmp_path / "activity.json"
    update_activity(path, order={"id": "wo-1", "question": "q", "budget_usd": "1.00"})
    first = json.loads(path.read_text())
    assert first["mandate_ceiling_usd"] == str(MANDATE_CEILING_USD)
    assert first["attacks"]  # the page renders these, so the agent supplies them

    # A later lane adds to the record rather than replacing it.
    update_activity(path, settlement={"id": "pi_x", "status": "succeeded"})
    second = json.loads(path.read_text())
    assert second["order"] == first["order"]
    assert second["settlement"]["id"] == "pi_x"


def test_a_corrupt_activity_file_is_replaced_not_propagated(tmp_path):
    path = tmp_path / "activity.json"
    path.write_text("{not json")
    assert update_activity(path, settlement={"id": "pi_y"})["settlement"]["id"] == "pi_y"


def test_credentials_never_leave_over_plain_http():
    import urllib.request

    with pytest.raises(SchemeRefused):
        open_https(urllib.request.Request("http://api.stripe.com/v1/charges"), 1.0)
