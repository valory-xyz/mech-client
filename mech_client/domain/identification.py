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

"""Tell whether a mech is operated by Valory."""

import requests
from mech_client.utils.logger import get_logger

logger = get_logger(__name__)

# A Valory operated mech answers on a name under this zone. The zone is a
# wildcard record, so the name resolving proves nothing: only a successful
# HTTP response does, because the route exists per mech.
IDENTIFICATION_ZONE = "mech.valory.xyz"
# Path requested on that name. The mech root replies 400, so ask for the
# endpoint that answers 200 on a healthy mech.
IDENTIFICATION_PATH = "/healthcheck"
# Kept short: this runs on the request path and must never hold up a request.
IDENTIFICATION_TIMEOUT = 3

# The notice shown to a requester calling a Valory operated mech. Fixed
# wording: a requester agrees by submitting the request, so this states what
# submitting means, it does not ask them to accept anything.
MECH_TERMS_VERSION = "v1.0"
MECH_TERMS_URL = "https://www.valory.xyz/terms/mechs"
VALORY_TERMS_NOTICE = (
    f"By submitting a request to this Mech, you agree to be bound by "
    f"Valory AG's Mech Terms ({MECH_TERMS_VERSION}), available at {MECH_TERMS_URL}."
)


def identification_url(mech_address: str, chain_id: int) -> str:
    """
    Build the name that identifies a mech as Valory operated.

    :param mech_address: The mech contract address, with or without `0x`
    :param chain_id: The chain the mech is deployed on, e.g. 100 for Gnosis
    :return: The full URL the identification check requests
    """
    address = mech_address.lower()
    if address.startswith("0x"):
        address = address[2:]
    return f"https://{address}.{chain_id}.{IDENTIFICATION_ZONE}{IDENTIFICATION_PATH}"


def is_valory_operated(mech_address: str, chain_id: int) -> bool:
    """
    Check whether a mech is operated by Valory.

    Fails closed: a timeout, a connection error, a 404 or any other non-2xx
    answer all mean "not identified as Valory operated". Claiming a mech is
    Valory's when it is not would be the harmful direction, so a check that
    cannot complete is treated as a "no".

    :param mech_address: The mech contract address, with or without `0x`
    :param chain_id: The chain the mech is deployed on
    :return: True only on a successful response from the identification URL
    """
    url = identification_url(mech_address, chain_id)
    try:
        response = requests.get(url, timeout=IDENTIFICATION_TIMEOUT)
    except requests.RequestException as exc:
        logger.debug(f"Identification check failed for {url}: {exc}")
        return False
    return response.ok
