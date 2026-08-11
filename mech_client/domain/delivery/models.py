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
from typing import Any, Optional


@dataclass(frozen=True)
class DeliveryResult:
    """A mech delivery, resolved to its content.

    Both watchers return this, so callers get the same shape whether the
    response was delivered on-chain or off-chain.

    ``data`` holds the parsed content of the delivered result file, or
    ``None`` when the gateway could not be read (``url`` still points at it).
    ``url`` is the gateway URL ``data`` was read from; it is ``None`` for
    offchain mechs that answer inline instead of pinning a result file.
    """

    request_id: str
    data: Any = None
    url: Optional[str] = None
