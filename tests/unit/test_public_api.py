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

"""Tests for the names mech_client exports for off-chain payers."""

import mech_client
from mech_client.domain.delivery import chat
from mech_client.domain.payment import addresses
from mech_client.domain.request_id import request_digest
from mech_client.domain.tools import manager, models
from mech_client.services import marketplace_service


def test_the_off_chain_payer_api_is_exported() -> None:
    """Every name an off-chain payer uses is importable from mech_client itself."""
    expected = {
        "NonceAllocator": mech_client.nonces.NonceAllocator,
        "NonceRefused": mech_client.nonces.NonceRefused,
        "Reservation": mech_client.nonces.Reservation,
        "outcome_of": mech_client.nonces.outcome_of,
        "send_with_nonce": mech_client.nonces.send_with_nonce,
        "PreSignHook": marketplace_service.PreSignHook,
        "request_digest": request_digest,
        "RequestIdMismatch": marketplace_service.RequestIdMismatch,
        "MechPriceExceeded": marketplace_service.MechPriceExceeded,
        "MechInfo": marketplace_service.MechInfo,
        "OffchainRequestResult": marketplace_service.OffchainRequestResult,
        "payment_token": addresses.payment_token,
        "balance_tracker": addresses.balance_tracker,
        "ToolManager": manager.ToolManager,
        "MetadataRead": models.MetadataRead,
        "offchain_blocker": manager.offchain_blocker,
        "ChatReport": chat.ChatReport,
        "chat_report": chat.chat_report,
        "is_chat_prompt": chat.is_chat_prompt,
    }
    for name, value in expected.items():
        assert name in mech_client.__all__
        assert getattr(mech_client, name) is value
    assert "Outcome" in mech_client.__all__
    for name in [n for n in vars(mech_client.nonces) if n.startswith("RULE_")]:
        assert getattr(mech_client, name) == getattr(mech_client.nonces, name)
        assert name in mech_client.__all__
    assert "NonceRule" in mech_client.__all__
