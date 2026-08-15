"""The client's OWN copy of the wire contracts.

Deliberately duplicated rather than imported from the firm. The two sides are
separate repositories that trust each other only as far as the wire format, so
sharing a package would create exactly the coupling the boundary exists to
prevent: a change on one side could not silently redefine what the other
accepts.

The duplication is the honest cost of a zero-trust boundary. It is also what
lets the adversarial lane send payloads the firm's contracts reject -- an
imported model could not express a malformed order.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WorkOrder(BaseModel):
    """What we ask Broker for. Mirrors the firm's intake contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    client_id: str = Field(min_length=1, max_length=64)
    question: str = Field(min_length=1, max_length=4000)
    budget_usd: Decimal = Field(ge=0, decimal_places=2)

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Verdict(BaseModel):
    """Our own judgement of a deliverable. The firm never sees this."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    acceptable: bool
    reason: str
    pay_usd: Decimal = Field(ge=0, decimal_places=2)
