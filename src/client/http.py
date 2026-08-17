"""One opener for every outbound call this agent makes.

Both endpoints this repository talks to — GitHub for the order channel, Stripe
for settlement — carry a credential in the request header. A credential must
never leave the process over anything but https, and the destination is not
always a constant: ``FIRM_REPO`` is environment-supplied, and a base URL that a
future edit reads from the environment would make the scheme a runtime value.
So the scheme is checked before the opener sees the URL.

Mirrors ``company/adapters/http.py`` in the counterparty repository, and is
duplicated for the same reason its contracts are: the two sides share a wire
format, not a package.
"""

from __future__ import annotations

import urllib.request
from typing import Any

ALLOWED_SCHEMES = frozenset({"https"})


class SchemeRefused(ValueError):
    """The request URL used a scheme this agent will not open."""


def open_https(req: urllib.request.Request, timeout: float) -> Any:
    """Open ``req`` if and only if its scheme is allowed."""
    if req.type not in ALLOWED_SCHEMES:
        raise SchemeRefused(f"refusing to open a {req.type!r} URL; allowed: https")
    # Audited: the scheme is checked on the line above.
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310
