# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025 Valory AG
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

"""Base delivery watcher interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class DeliveryWatcher(ABC):
    """Abstract base class for delivery watchers.

    Defines the interface for watching and retrieving mech responses
    from different delivery mechanisms (on-chain, off-chain, etc.).
    """

    def __init__(self, timeout: float):
        """
        Initialize delivery watcher.

        :param timeout: Maximum time to wait for delivery (seconds)
        """
        self.timeout = timeout

    @abstractmethod
    async def watch(self, request_ids: List[str]) -> Dict[str, Any]:
        """
        Watch for delivery of mech responses.

        :param request_ids: List of request IDs to watch for
        :return: Dictionary mapping request ID to delivery data
        """
