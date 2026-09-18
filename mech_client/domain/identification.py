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

import secrets
import socket
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from mech_client.utils.logger import get_logger

logger = get_logger(__name__)

# Valory creates one DNS record per mech it operates under this zone, and only
# Valory can, so a mech's name resolving is what identifies it. The answer does
# not depend on the mech being up.
IDENTIFICATION_ZONE = "mech.valory.xyz"
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


def identification_name(mech_address: str, chain_id: int) -> str:
    """
    Build the DNS name that identifies a mech as Valory operated.

    :param mech_address: The mech contract address, with or without `0x`
    :param chain_id: The chain the mech is deployed on, e.g. 100 for Gnosis
    :return: The name the identification check resolves
    """
    address = mech_address.lower()
    if address.startswith("0x"):
        address = address[2:]
    return f"{address}.{chain_id}.{IDENTIFICATION_ZONE}"


def _resolves(name: str) -> bool:
    """
    Report whether a DNS name resolves, giving up after the timeout.

    :param name: The DNS name to look up
    :return: True if the name resolved within the timeout
    """
    # The lookup has no timeout of its own, so run it in a thread and stop
    # waiting after IDENTIFICATION_TIMEOUT. The pool is not used as a context
    # manager: that would wait for a hung lookup, defeating the timeout.
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        executor.submit(socket.getaddrinfo, name, None).result(
            timeout=IDENTIFICATION_TIMEOUT
        )
    except (OSError, UnicodeError, FuturesTimeoutError) as exc:
        logger.debug(f"{name} did not resolve: {exc}")
        return False
    finally:
        executor.shutdown(wait=False)
    return True


def is_valory_operated(mech_address: str, chain_id: int) -> bool:
    """
    Check whether a mech is operated by Valory.

    Fails closed. A name that does not resolve, a lookup that times out, or no
    network at all each mean "not identified as Valory operated". Claiming a
    mech is Valory's when it is not would be the harmful direction.

    A positive answer is also checked against a name that cannot belong to any
    mech. If that resolves too, the zone answers every name, as a wildcard
    record would, and the positive answer proves nothing, so the check says no.

    :param mech_address: The mech contract address, with or without `0x`
    :param chain_id: The chain the mech is deployed on
    :return: True only if the mech's own name resolves and an arbitrary one does not
    """
    if not _resolves(identification_name(mech_address, chain_id)):
        return False
    # 32 hex characters, so it can never be a 40-character mech address.
    probe = f"{secrets.token_hex(16)}.{chain_id}.{IDENTIFICATION_ZONE}"
    return not _resolves(probe)
