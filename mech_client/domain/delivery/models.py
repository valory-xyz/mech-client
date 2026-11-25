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
    """One request's delivery, in the same shape on-chain and off-chain.

    ``data``: the delivered content, or ``None`` when the gateway could not be
    read. A failed off-chain run also sets it (the mech's failure body), so
    check ``failure`` before treating ``data`` as an answer.
    ``url``: the gateway URL ``data`` was read from; ``None`` off-chain.
    ``actual_delivery_rate``: what the mech charged, in base units of its
    payment asset; ``None`` when not reported, always so on-chain.
    ``failure``: set when an off-chain run failed.
    """

    request_id: str
    data: JSONValue = None
    url: Optional[str] = None
    actual_delivery_rate: Optional[int] = None
    failure: Optional[RunFailure] = None
