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

import gevent

class NonceAllocator:
    """
    Thread/greenlet-safe nonce allocator per account.
    Uses 'pending' count so unmined txs are included.
    """
    def __init__(self, w3, address: str):
        self._w3 = w3
        self._addr = address
        self._lock = gevent.lock.Semaphore()
        self._next = self._w3.eth.get_transaction_count(address, "pending")

    def allocate_batch(self, n: int) -> int:
        """Reserve n sequential nonces, returning the base nonce."""
        with self._lock:
            base = self._next
            self._next += n
            return base

class MapNonceAllocator:
    def __init__(self, marketplace_contract, address: str):
        self._c = marketplace_contract
        self._addr = address
        self._lock = gevent.lock.Semaphore()
        self._next = self._c.functions.mapNonces(address).call()
    def allocate_batch(self, n: int) -> int:
        with self._lock:
            base = self._next
            self._next += n
            return base