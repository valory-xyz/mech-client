# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2026 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Models shared by the delivery watchers."""

from dataclasses import dataclass
from typing import Optional

from mech_client.utils.types import JSONValue

# Who caused a failed off-chain run, as the mech's delivery envelope states it.
FAULT_CLIENT = "client"
FAULT_MECH = "mech"


@dataclass(frozen=True)
class RunFailure:
    """An off-chain run the mech settled as failed.

    ``error`` is the mech's ``"<ExceptionType>: <message>"``. ``fault`` is
    :data:`FAULT_CLIENT` when the request could not be run as sent, which the
    mech charges at the full signed cap, or :data:`FAULT_MECH` when the mech
    could not complete it, whose charge depends on the mech's settings. It
    is ``None`` when the mech named neither.
    """

    error: str
    fault: Optional[str] = None


@dataclass(frozen=True)
class DeliveryResult:
    """A mech delivery, resolved to its content.

    Both watchers return this, so callers get the same shape whether the
    response was delivered on-chain or off-chain.

    ``data`` holds the parsed content of the delivered result file, or
    ``None`` when the gateway could not be read (``url`` still points at it).
    ``url`` is the gateway URL ``data`` was read from; it is ``None`` for
    offchain mechs that answer inline instead of pinning a result file.
    ``actual_delivery_rate`` is what the mech charged for the request, in
    the base units of its payment asset: at or below the maximum the
    requester signed (the ``delivery_rate`` of the request payload), with
    the difference staying in the requester's balance. It is ``None`` when
    the mech did not report a charge, which is always the case for on-chain
    delivery. ``failure`` is set when an off-chain run failed; the charge is
    then what the mech settles for the failed run.
    """

    request_id: str
    data: JSONValue = None
    url: Optional[str] = None
    actual_delivery_rate: Optional[int] = None
    failure: Optional[RunFailure] = None
