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

from pathlib import Path
from typing import Optional, Type, cast

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
from aea.protocols.base import Message

from mech_client.helpers import (
    ACN_DATA_SHARE_PROTOCOL_PACKAGE,
    ACN_PROTOCOL_PACKAGE,
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
    """
    Issue ACN certificate.

    :param cert_request: certificate request object
    :type cert_request: CertRequest
    :param crypto: instance of Crypto
    :type crypto: Crypto
    :raises: None
    """
    public_key = cast(str, cert_request.public_key)
    message = cert_request.get_message(public_key)
    signature = crypto.sign_message(message).encode("ascii").hex()
    Path(cert_request.save_path).write_bytes(signature.encode("ascii"))


def load_protocol() -> Type[Message]:
    """
    Load message class.

    :return: message class
    :rtype: Type[Message]
    :raises: None
    """
    configuration = load_component_configuration(
        component_type=ComponentType.PROTOCOL,
        directory=ACN_DATA_SHARE_PROTOCOL_PACKAGE,
    )
    configuration.directory = ACN_DATA_SHARE_PROTOCOL_PACKAGE
    load_aea_package(configuration=configuration)

    from packages.valory.protocols.acn_data_share.message import (  # pylint: disable=import-outside-toplevel,import-error,no-name-in-module
        AcnDataShareMessage,
    )

    return AcnDataShareMessage


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
    """
    Load `p2p_libp2p_client` connection.

    :param crypto: instance of Crypto
    :type crypto: Crypto
    :return: instance of libp2p2 client connection
    :rtype: Connection
    :raises: None
    """
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


async def watch_for_data_url_from_mech(crypto: Crypto) -> Optional[str]:
    """
    Wait for data from mech

    :param crypto: instance of Crypto
    :type crypto: Crypto
    :return: Data URL
    :rtype: str
    :raises: None
    """
    AcnDataShareMessage = load_protocol()
    connection = load_libp2p_client(crypto=crypto)
    try:
        await connection.connect()
        response = await connection.receive()
        response_message = AcnDataShareMessage.decode(response.message)
        return f"https://gateway.autonolas.tech/ipfs/{response_message.content}"
    except AttributeError:
        return None
    finally:
        await connection.disconnect()
