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

"""Local signer wrapping an in-process private key (default implementation)."""

from typing import Any, Dict

from aea_ledger_ethereum import EthereumApi, EthereumCrypto


class LocalSigner:
    """Default :class:`Signer` implementation backed by a local private key.

    Wraps an ``EthereumCrypto`` (raw key in-process) and an ``EthereumApi``
    (for nonce/gas fill and broadcasting), preserving the historic signing
    behavior of mech-client.
    """

    def __init__(self, crypto: EthereumCrypto, ledger_api: EthereumApi):
        """
        Initialize local signer.

        :param crypto: Ethereum crypto object holding the private key
        :param ledger_api: Ethereum API used to fill tx defaults and broadcast
        """
        self.crypto = crypto
        self.ledger_api = ledger_api

    @property
    def address(self) -> str:
        """The EOA address of the wrapped key.

        :return: Signer's EOA address
        """
        return str(self.crypto.address)

    def send_transaction(self, unsigned_tx: Dict[str, Any]) -> str:
        """Sign an EOA transaction with the local key and broadcast it.

        Fills ``nonce``, gas price, and ``gas`` from the connected node when
        absent, then signs and sends via the ledger API (``raise_on_try=True``
        propagates build/sign/send failures).

        :param unsigned_tx: Unsigned transaction dict
        :return: Transaction hash (0x-prefixed hex string)
        """
        tx = dict(unsigned_tx)
        tx.setdefault("from", self.address)
        if tx.get("nonce") is None:
            tx["nonce"] = self.ledger_api.api.eth.get_transaction_count(self.address)
        if "gasPrice" not in tx and "maxFeePerGas" not in tx:
            tx["gasPrice"] = self.ledger_api.api.eth.gas_price
        if not tx.get("gas"):
            tx["gas"] = self.ledger_api.api.eth.estimate_gas(tx)
        signed_transaction = self.crypto.sign_transaction(tx)
        transaction_digest = self.ledger_api.send_signed_transaction(
            signed_transaction,
            raise_on_try=True,
        )
        return str(transaction_digest)

    def sign_message(self, message: bytes) -> bytes:
        """Sign ``message`` with the local key.

        For 32-byte inputs (the mech request-id digest) this signs the digest
        directly (``unsafe_sign_hash``), matching the marketplace contract's
        plain ``ecrecover`` verification — see :class:`Signer.sign_message`.

        :param message: Message bytes to sign
        :return: 65-byte signature (r ‖ s ‖ v)
        """
        signature = self.crypto.sign_message(message, is_deprecated_mode=True)
        return bytes.fromhex(signature.removeprefix("0x"))
