# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2023 Valory AG
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

"""ACN helpers."""

import asyncio
from enum import Enum
from pathlib import Path
from typing import Any, Tuple, Type, cast

from aea.components.base import load_aea_package
from aea.configurations.base import ConnectionConfig
from aea.configurations.constants import DEFAULT_CONNECTION_CONFIG_FILE
from aea.configurations.data_types import ComponentType
from aea.configurations.loader import load_component_configuration
from aea.connections.base import Connection
from aea.crypto.base import Crypto
from aea.crypto.wallet import CryptoStore
from aea.helpers.base import CertRequest
from aea.helpers.yaml_utils import yaml_load
from aea.identity.base import Identity
from aea.mail.base import Envelope
from aea.protocols.base import Message, Protocol
from aea.protocols.dialogue.base import Dialogue, DialogueLabel, Dialogues
from aea_ledger_ethereum import EthereumCrypto

from mech_client.helpers import (
    ACN_PROTOCOL_PACKAGE,
    MECH_ACN_CALLBACK_PROTOCOL_PACKAGE,
    P2P_CLIENT_PACKAGE,
)

CONNECTION_CONFIG = {
    "connect_retries": 3,
    "ledger_id": "cosmos",
    "nodes": [
        {
            "uri": "acn.staging.autonolas.tech:9005",
            "public_key": "02d3a830c9d6ea1ae91936951430dee11f4662f33118b02190693be835359a9d77",
        }
    ],
}


CERT_REQUESTS = [
    {
        "identifier": "acn",
        "ledger_id": "ethereum",
        "message_format": "{public_key}",
        "not_after": "2024-01-01",
        "not_before": "2023-01-01",
        "public_key": "02d3a830c9d6ea1ae91936951430dee11f4662f33118b02190693be835359a9d77",
        "save_path": "acn_cert.txt",
    }
]


def issue_certificate(cert_request: CertRequest, crypto: Crypto) -> None:
    """Issue ACN certificate."""
    public_key = cast(str, cert_request.public_key)
    message = cert_request.get_message(public_key)
    signature = crypto.sign_message(message).encode("ascii").hex()
    Path(cert_request.save_path).write_bytes(signature.encode("ascii"))


def load_protocol(
    address: str,
) -> Tuple[Type[Message], Type[Dialogue], Type[Dialogues], Type[Enum]]:
    """Load message class."""
    configuration = load_component_configuration(
        component_type=ComponentType.PROTOCOL,
        directory=MECH_ACN_CALLBACK_PROTOCOL_PACKAGE,
    )
    configuration.directory = MECH_ACN_CALLBACK_PROTOCOL_PACKAGE
    load_aea_package(configuration=configuration)

    from packages.valory.protocols.mech_acn.custom_types import (
        StatusEnum as RequestStatus,
    )
    from packages.valory.protocols.mech_acn.dialogues import MechAcnDialogue
    from packages.valory.protocols.mech_acn.dialogues import (
        MechAcnDialogues as BaseMechAcnDialogues,
    )
    from packages.valory.protocols.mech_acn.message import MechAcnMessage

    class MechAcnDialogues(BaseMechAcnDialogues):
        """The dialogues class keeps track of all dialogues."""

        def __init__(self, **kwargs: Any) -> None:
            """
            Initialize dialogues.
            :param kwargs: keyword arguments
            """

            def role_from_first_message(  # pylint: disable=unused-argument
                message: Message, receiver_address: str
            ) -> Dialogue.Role:
                """Infer the role of the agent from an incoming/outgoing first message
                :param message: an incoming/outgoing first message
                :param receiver_address: the address of the receiving agent
                :return: The role of the agent
                """
                return MechAcnDialogue.Role.AGENT

            BaseMechAcnDialogues.__init__(
                self,
                self_address=str(address),
                role_from_first_message=role_from_first_message,
            )

    return MechAcnMessage, MechAcnDialogue, MechAcnDialogues, RequestStatus


def load_acn_protocol() -> None:
    """Load ACN protocol."""
    configuration = load_component_configuration(
        component_type=ComponentType.PROTOCOL, directory=ACN_PROTOCOL_PACKAGE
    )
    configuration.directory = ACN_PROTOCOL_PACKAGE
    load_aea_package(configuration=configuration)


def load_libp2p_client(
    crypto: Crypto,
) -> Connection:
    """Load `p2p_libp2p_client` connection"""
    config_data = yaml_load(
        (P2P_CLIENT_PACKAGE / DEFAULT_CONNECTION_CONFIG_FILE).open(
            "r", encoding="utf-8"
        )
    )
    config_data["config"] = CONNECTION_CONFIG
    config_data["cert_requests"] = CERT_REQUESTS
    configuration: ConnectionConfig = ConnectionConfig.from_json(config_data)
    configuration.directory = P2P_CLIENT_PACKAGE

    (cert_requet,) = configuration.cert_requests
    issue_certificate(cert_request=cert_requet, crypto=crypto)
    load_acn_protocol()
    return Connection.from_config(
        configuration=configuration,
        identity=Identity(
            name="mech_client", address=crypto.address, public_key=crypto.public_key
        ),
        crypto_store=CryptoStore(),
        data_dir=".",
    )


async def request_mech_for_data(
    request_id: int,
    agent_address: str,
    crypto: Crypto,
    sleep: float = 3.0,
) -> Any:
    """Request and wait for data from agent."""
    MechAcnMessage, _, MechAcnDialogues, RequestStatus = load_protocol(
        address=crypto.address
    )
    connection = load_libp2p_client(crypto=crypto)
    dialogues = MechAcnDialogues()
    try:
        await connection.connect()
        while True:
            message, _ = dialogues.create(
                counterparty=agent_address,
                performative=MechAcnMessage.Performative.REQUEST,
                request_id=request_id,
            )
            envelope = Envelope(
                to=message.to,
                sender=message.sender,
                message=message,
            )
            await connection.send(envelope=envelope)
            response = await connection.receive()
            response_message = MechAcnMessage.decode(response.message)
            if response_message.status.status == RequestStatus.READY:
                return response_message.data

            print(f"{response_message.data}")
            print(f"Will retry in {sleep}...")
            await asyncio.sleep(sleep)
    finally:
        await connection.disconnect()
