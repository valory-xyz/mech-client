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

"""Offchain delivery watcher for polling offchain mech endpoints."""

import asyncio
import logging
import time
from typing import Any, Dict, List

import requests

from mech_client.domain.delivery.base import DeliveryWatcher
from mech_client.domain.delivery.constants import WAIT_SLEEP


logger = logging.getLogger(__name__)

# Constants for offchain polling
OFFCHAIN_DELIVER_ENDPOINT = "fetch_offchain_info"


class OffchainDeliveryWatcher(
    DeliveryWatcher
):  # pylint: disable=too-few-public-methods
    """Watches for mech responses from offchain HTTP endpoints.

    Polls the offchain mech's delivery endpoint to fetch responses
    for given request IDs.
    """

    def __init__(self, mech_offchain_url: str, timeout: float):
        """
        Initialize offchain delivery watcher.

        :param mech_offchain_url: Base URL of the offchain mech
        :param timeout: Maximum time to wait for delivery (seconds)
        """
        super().__init__(timeout)
        self.mech_offchain_url = mech_offchain_url.rstrip("/")
        self.deliver_url = f"{self.mech_offchain_url}/{OFFCHAIN_DELIVER_ENDPOINT}"

    async def watch(self, request_ids: List[str]) -> Dict[str, Any]:
        """
        Watch for delivery of offchain mech responses.

        Polls the offchain endpoint for each request ID until all responses
        are received or timeout occurs.

        :param request_ids: List of request IDs to watch for
        :return: Dictionary mapping request ID to delivery data
        """
        results: Dict[str, Any] = {}
        start_time = time.time()

        # Convert request IDs to integers for offchain API
        request_id_ints = [str(int(rid, 16)) for rid in request_ids]

        while len(results) < len(request_ids):
            # Check timeout
            if time.time() - start_time > self.timeout:
                logger.warning(
                    f"Timeout after {self.timeout}s. "
                    f"Received {len(results)}/{len(request_ids)} responses."
                )
                break

            # Poll each pending request
            for request_id, request_id_int in zip(request_ids, request_id_ints):
                if request_id in results:
                    continue

                try:
                    response = await self._fetch_offchain_data(request_id_int)
                    if response:
                        results[request_id] = response
                        logger.info(
                            f"Received offchain response for request {request_id_int}"
                        )
                except Exception as e:  # pylint: disable=broad-except
                    # Log error but continue polling
                    logger.error(
                        f"Error fetching offchain data for {request_id_int}: {e}"
                    )

            # Sleep before next poll if not all results received
            if len(results) < len(request_ids):
                await asyncio.sleep(WAIT_SLEEP)

        return results

    async def _fetch_offchain_data(self, request_id: str) -> Any:
        """
        Fetch offchain data for a single request ID.

        :param request_id: Request ID (as integer string)
        :return: Response data if available, None otherwise
        """
        try:
            # Make synchronous request in async context
            # Note: Using requests in async is not ideal, but matches historic implementation
            # For production, consider using aiohttp
            response = requests.get(
                self.deliver_url,
                data={"request_id": request_id},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            # Return data if response is non-empty
            if data:
                return data

        except requests.exceptions.RequestException:
            # Return None if request fails (will retry)
            pass

        return None
