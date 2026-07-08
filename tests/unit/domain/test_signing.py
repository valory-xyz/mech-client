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

"""Tests for domain.signing (Signer protocol and LocalSigner)."""

from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock

from aea_ledger_ethereum import EthereumCrypto
from eth_account import Account

from mech_client.domain.signing import LocalSigner, Signer


class TestSignerProtocol:
    """Tests for the Signer runtime-checkable protocol."""

    def test_local_signer_satisfies_protocol(self) -> None:
        """Test LocalSigner structurally satisfies Signer."""
        signer = LocalSigner(MagicMock(), MagicMock())

        assert isinstance(signer, Signer)

    def test_custom_implementation_satisfies_protocol(self) -> None:
        """Test an external implementation structurally satisfies Signer."""

        class RemoteSigner:
            """Minimal external signer stub."""

            address = "0x" + "1" * 40

            def send_transaction(self, unsigned_tx: Dict[str, Any]) -> str:
                """Pretend to sign and broadcast."""
                return "0x" + "0" * 64

            def sign_message(self, message: bytes) -> bytes:
                """Pretend to sign a digest."""
                return b"\x00" * 65

        assert isinstance(RemoteSigner(), Signer)


class TestLocalSignerAddress:
    """Tests for LocalSigner.address."""

    def test_address_returns_crypto_address(self) -> None:
        """Test address proxies the wrapped crypto address."""
        mock_crypto = MagicMock()
        mock_crypto.address = "0x" + "a" * 40

        signer = LocalSigner(mock_crypto, MagicMock())

        assert signer.address == "0x" + "a" * 40


class TestLocalSignerSendTransaction:
    """Tests for LocalSigner.send_transaction."""

    def test_sends_prebuilt_transaction_unchanged(self) -> None:
        """Test a fully built tx is signed and sent without refetching fields."""
        mock_crypto = MagicMock()
        mock_crypto.address = "0x" + "a" * 40
        mock_crypto.sign_transaction.return_value = {"signed": True}
        mock_ledger_api = MagicMock()
        mock_ledger_api.send_signed_transaction.return_value = "0xtxhash"

        signer = LocalSigner(mock_crypto, mock_ledger_api)
        unsigned_tx = {
            "from": "0x" + "a" * 40,
            "nonce": 7,
            "gas": 21000,
            "gasPrice": 10**9,
            "to": "0x" + "b" * 40,
            "value": 1,
        }

        tx_hash = signer.send_transaction(unsigned_tx)

        assert tx_hash == "0xtxhash"
        mock_crypto.sign_transaction.assert_called_once_with(unsigned_tx)
        mock_ledger_api.send_signed_transaction.assert_called_once_with(
            {"signed": True}, raise_on_try=True
        )
        # No node lookups needed when the tx is complete
        mock_ledger_api.api.eth.get_transaction_count.assert_not_called()
        mock_ledger_api.api.eth.estimate_gas.assert_not_called()

    def test_fills_missing_fields_from_node(self) -> None:
        """Test nonce, gas price, and gas are filled when absent."""
        mock_crypto = MagicMock()
        mock_crypto.address = "0x" + "a" * 40
        mock_crypto.sign_transaction.return_value = {"signed": True}
        mock_ledger_api = MagicMock()
        mock_ledger_api.api.eth.get_transaction_count.return_value = 5
        mock_ledger_api.api.eth.gas_price = 2 * 10**9
        mock_ledger_api.api.eth.estimate_gas.return_value = 50000
        mock_ledger_api.send_signed_transaction.return_value = "0xtxhash"

        signer = LocalSigner(mock_crypto, mock_ledger_api)

        tx_hash = signer.send_transaction({"to": "0x" + "b" * 40, "value": 1})

        assert tx_hash == "0xtxhash"
        signed_tx = mock_crypto.sign_transaction.call_args[0][0]
        assert signed_tx["from"] == "0x" + "a" * 40
        assert signed_tx["nonce"] == 5
        assert signed_tx["gasPrice"] == 2 * 10**9
        assert signed_tx["gas"] == 50000
        mock_ledger_api.api.eth.get_transaction_count.assert_called_once_with(
            "0x" + "a" * 40
        )

    def test_does_not_override_eip1559_fees(self) -> None:
        """Test gasPrice is not added when maxFeePerGas is present."""
        mock_crypto = MagicMock()
        mock_crypto.address = "0x" + "a" * 40
        mock_ledger_api = MagicMock()
        mock_ledger_api.send_signed_transaction.return_value = "0xtxhash"

        signer = LocalSigner(mock_crypto, mock_ledger_api)

        signer.send_transaction(
            {"to": "0x" + "b" * 40, "nonce": 1, "gas": 21000, "maxFeePerGas": 10**9}
        )

        signed_tx = mock_crypto.sign_transaction.call_args[0][0]
        assert "gasPrice" not in signed_tx

    def test_preserves_explicit_zero_gas(self) -> None:
        """Test an explicit gas=0 is kept, not silently re-estimated."""
        mock_crypto = MagicMock()
        mock_crypto.address = "0x" + "a" * 40
        mock_ledger_api = MagicMock()
        mock_ledger_api.send_signed_transaction.return_value = "0xtxhash"

        signer = LocalSigner(mock_crypto, mock_ledger_api)

        signer.send_transaction(
            {"to": "0x" + "b" * 40, "nonce": 1, "gas": 0, "gasPrice": 1}
        )

        signed_tx = mock_crypto.sign_transaction.call_args[0][0]
        assert signed_tx["gas"] == 0
        mock_ledger_api.api.eth.estimate_gas.assert_not_called()

    def test_does_not_mutate_input_dict(self) -> None:
        """Test the caller's unsigned tx dict is left untouched."""
        mock_crypto = MagicMock()
        mock_crypto.address = "0x" + "a" * 40
        mock_ledger_api = MagicMock()
        mock_ledger_api.api.eth.get_transaction_count.return_value = 5
        mock_ledger_api.send_signed_transaction.return_value = "0xtxhash"

        signer = LocalSigner(mock_crypto, mock_ledger_api)
        unsigned_tx = {"to": "0x" + "b" * 40, "gas": 21000, "gasPrice": 1}

        signer.send_transaction(unsigned_tx)

        assert unsigned_tx == {"to": "0x" + "b" * 40, "gas": 21000, "gasPrice": 1}


class TestLocalSignerSignMessage:
    """Tests for LocalSigner.sign_message."""

    def test_signs_digest_in_deprecated_mode(self) -> None:
        """Test sign_message delegates to crypto with is_deprecated_mode."""
        mock_crypto = MagicMock()
        mock_crypto.sign_message.return_value = "0x" + "ab" * 65
        signer = LocalSigner(mock_crypto, MagicMock())
        digest = b"\x11" * 32

        signature = signer.sign_message(digest)

        assert signature == b"\xab" * 65
        mock_crypto.sign_message.assert_called_once_with(
            digest, is_deprecated_mode=True
        )

    def test_handles_unprefixed_signature(self) -> None:
        """Test sign_message accepts a signature without 0x prefix."""
        mock_crypto = MagicMock()
        mock_crypto.sign_message.return_value = "cd" * 65
        signer = LocalSigner(mock_crypto, MagicMock())

        signature = signer.sign_message(b"\x11" * 32)

        assert signature == b"\xcd" * 65

    def test_real_key_signature_recovers_via_raw_ecrecover(
        self, tmp_path: Path
    ) -> None:
        """Test a real-key signature is a raw digest signature (no EIP-191).

        Everything else in this module mocks ``crypto.sign_message``, so an
        AEA-side change to ``is_deprecated_mode`` semantics would go
        unnoticed while the marketplace contract's plain
        ``ecrecover(digest, v, r, s)`` started rejecting offchain requests.
        This is the one test exercising the real signing primitive: recovery
        over the *unprefixed* digest must yield the key's address.
        """
        key_file = tmp_path / "key.txt"
        key_file.write_text("0x" + "1" * 64)  # synthetic test key
        crypto = EthereumCrypto(private_key_path=str(key_file))
        signer = LocalSigner(crypto, MagicMock())
        digest = b"\x11" * 32

        signature = signer.sign_message(digest)

        assert len(signature) == 65
        # Raw-hash recovery, mirroring the on-chain ecrecover (no EIP-191
        # prefix). pylint: disable applies to eth_account's private-but-stable
        # classmethod.
        recovered = Account._recover_hash(  # pylint: disable=protected-access
            digest, signature=signature
        )
        assert recovered == crypto.address
