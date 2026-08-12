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
from typing import Any, Dict, List, Optional

import requests
from mech_client.domain.delivery.base import DeliveryWatcher
from mech_client.domain.delivery.constants import WAIT_SLEEP
from mech_client.domain.delivery.models import DeliveryResult
from mech_client.infrastructure.ipfs.result_file import (
    build_result_file_url,
    fetch_result_file,
)

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

    async def watch(self, request_ids: List[str]) -> Dict[str, DeliveryResult]:
        """
        Watch for delivery of offchain mech responses.

        Polls the offchain endpoint for each request ID until all responses
        are received or timeout occurs, then reads the result file each
        response points at.

        :param request_ids: List of request IDs to watch for
        :return: Dictionary mapping request ID to its delivery result
        """
        results: Dict[str, DeliveryResult] = {}
        # Result-file URLs seen for requests whose file has not been read yet.
        # A read that keeps failing is retried for as long as there is budget,
        # so the URL is held here to report at timeout rather than written into
        # `results`, which would mark the request done after a single attempt.
        # Retrying matters most for the ordinary case — a pinned file that
        # 404s until the gateway catches up — not just for unexpected errors.
        pending_urls: Dict[str, str] = {}
        prev_count = -1
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
                    if not response:
                        continue

                    url = self._result_file_url(response, request_id_int)
                    if url is None:
                        # The mech answered inline; the envelope is the answer.
                        results[request_id] = DeliveryResult(
                            request_id=request_id, data=response
                        )
                    else:
                        pending_urls[request_id] = url
                        # Off the event loop: a gateway round-trip here would
                        # otherwise stall every other request's poll.
                        data = await asyncio.to_thread(
                            fetch_result_file, url, request_id
                        )
                        if data is None:
                            # Not readable yet. `fetch_result_file` returns
                            # `None` for every HTTP failure, and a freshly
                            # pinned file routinely 404s while it propagates,
                            # so leave the request out of `results` to have the
                            # next cycle try again. The backfill below reports
                            # it with this URL if it never becomes readable.
                            continue
                        results[request_id] = DeliveryResult(
                            request_id=request_id, data=data, url=url
                        )
                    logger.info(
                        f"Received offchain response for request {request_id_int}"
                    )
                except Exception as e:  # pylint: disable=broad-except
                    # Log error but continue polling. Leaving the request out of
                    # `results` is what keeps it eligible for the next cycle.
                    logger.error(
                        f"Error fetching offchain data for {request_id_int}: {e}"
                    )

            # Sleep before next poll if not all results received
            if len(results) < len(request_ids):
                current_count = len(results)
                if current_count != prev_count:
                    logger.info(
                        "Waiting for offchain delivery: %d/%d received",
                        current_count,
                        len(request_ids),
                    )
                    prev_count = current_count
                await asyncio.sleep(WAIT_SLEEP)

        # A request whose file never became readable still reports where to look,
        # the same shape the on-chain path returns for an unreadable result.
        for request_id, url in pending_urls.items():
            results.setdefault(
                request_id, DeliveryResult(request_id=request_id, data=None, url=url)
            )

        return results

    @staticmethod
    def _result_file_url(response: Any, request_id_decimal: str) -> Optional[str]:
        """
        Locate the result file an offchain response points at.

        The endpoint answers with an envelope carrying ``task_result``, the
        IPFS hash of the directory the mech filed the result under. Reading
        that file gives callers the same content the on-chain watcher returns.

        :param response: Raw response from the offchain endpoint
        :param request_id_decimal: Request ID in decimal, the name of the
            result file inside the delivery directory
        :return: URL of the result file, or ``None`` for a mech that answered
            inline and pinned no file
        """
        task_result = (
            response.get("task_result") if isinstance(response, dict) else None
        )
        if not isinstance(task_result, str) or not task_result:
            return None
        return build_result_file_url(task_result, request_id_decimal)

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
