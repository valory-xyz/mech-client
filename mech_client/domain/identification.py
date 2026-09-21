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
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from enum import Enum
from typing import Any, Optional

from mech_client.utils.logger import get_logger

logger = get_logger(__name__)

# Valory creates one DNS record per mech it operates under this zone, and only
# Valory can, so a mech's name resolving is what identifies it. The answer does
# not depend on the mech being up. The lookup goes through the system resolver
# and is not DNSSEC-validated, so it trusts that resolver's answer.
IDENTIFICATION_ZONE = "mech.valory.xyz"
# Kept short: this runs on the request path and must never hold up a request.
IDENTIFICATION_TIMEOUT = 3
# Lookups share one capped pool. A lookup that hangs keeps its thread until the
# resolver gives up, so the cap bounds how many threads hung lookups can hold.
IDENTIFICATION_MAX_WORKERS = 8

# The notice shown to a requester calling a Valory operated mech. Fixed
# wording: a requester agrees by submitting the request, so this states what
# submitting means, it does not ask them to accept anything.
MECH_TERMS_VERSION = "v1.0"
MECH_TERMS_URL = "https://www.valory.xyz/terms/mechs"
VALORY_TERMS_NOTICE = (
    f"By submitting a request to this Mech, you agree to be bound by "
    f"Valory AG's Mech Terms ({MECH_TERMS_VERSION}), available at {MECH_TERMS_URL}."
)

# getaddrinfo errors that mean the name does not exist, as opposed to the
# lookup failing. EAI_NODATA is not defined on every platform.
_NO_SUCH_NAME = frozenset(
    code
    for code in (
        getattr(socket, "EAI_NONAME", None),
        getattr(socket, "EAI_NODATA", None),
    )
    if code is not None
)

_EXECUTOR = ThreadPoolExecutor(
    max_workers=IDENTIFICATION_MAX_WORKERS,
    thread_name_prefix="mech-identification",
)


class Identification(Enum):
    """The outcome of checking who operates a mech."""

    VALORY = "valory"
    """The mech's own name resolves and an arbitrary name does not."""

    NOT_VALORY = "not_valory"
    """The mech's own name does not exist under the zone."""

    UNKNOWN = "unknown"
    """The check could not complete, or the zone answers every name."""


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
    # One label, joined by a hyphen, so a single wildcard certificate on the
    # zone covers every mech on every chain. An address is hex and a chain id
    # is digits, so the hyphen is unambiguous.
    return f"{address}-{chain_id}.{IDENTIFICATION_ZONE}"


def _log_late_lookup(name: str, future: "Future[Any]") -> None:
    """
    Log how a lookup the caller stopped waiting for eventually ended.

    :param name: The DNS name that was looked up
    :param future: The finished lookup
    """
    error = future.exception()
    if error is not None:
        logger.debug(f"Abandoned lookup of {name} failed late: {error}")


def _lookup(name: str) -> Optional[bool]:
    """
    Look up a DNS name, giving up after the timeout.

    :param name: The DNS name to look up
    :return: True if it resolved, False if it does not exist, None if the
        lookup could not complete
    """
    # The lookup has no timeout of its own, so run it on the pool and stop
    # waiting after IDENTIFICATION_TIMEOUT. A running lookup cannot be
    # stopped; a queued one is cancelled so it never takes a thread.
    future = _EXECUTOR.submit(socket.getaddrinfo, name, None)
    try:
        future.result(timeout=IDENTIFICATION_TIMEOUT)
    except FuturesTimeoutError:
        if not future.cancel():
            future.add_done_callback(lambda done: _log_late_lookup(name, done))
        logger.warning(
            f"Looking up {name} took longer than {IDENTIFICATION_TIMEOUT}s; "
            f"could not check whether Valory operates this mech."
        )
        return None
    except socket.gaierror as exc:
        if exc.errno in _NO_SUCH_NAME:
            logger.debug(f"{name} does not exist: {exc}")
            return False
        logger.warning(f"Could not look up {name}: {exc}")
        return None
    except (OSError, UnicodeError) as exc:
        logger.warning(f"Could not look up {name}: {exc}")
        return None
    return True


def identify(mech_address: str, chain_id: int) -> Identification:
    """
    Check who operates a mech.

    A positive answer is also checked against a name that cannot belong to any
    mech. If that resolves too, the zone answers every name, as a wildcard
    record would, and the positive answer proves nothing.

    :param mech_address: The mech contract address, with or without `0x`
    :param chain_id: The chain the mech is deployed on
    :return: VALORY, NOT_VALORY, or UNKNOWN when the check could not tell
    """
    found = _lookup(identification_name(mech_address, chain_id))
    if found is None:
        return Identification.UNKNOWN
    if not found:
        return Identification.NOT_VALORY
    # 32 hex characters, so it can never be a 40-character mech address.
    probe = f"{secrets.token_hex(16)}-{chain_id}.{IDENTIFICATION_ZONE}"
    probe_found = _lookup(probe)
    if probe_found is None:
        return Identification.UNKNOWN
    if probe_found:
        logger.warning(
            f"{IDENTIFICATION_ZONE} resolved an arbitrary name, so a resolving "
            f"name identifies nothing; could not check who operates this mech."
        )
        return Identification.UNKNOWN
    return Identification.VALORY


def is_valory_operated(mech_address: str, chain_id: int) -> bool:
    """
    Check whether a mech is operated by Valory.

    Fails closed. A name that does not resolve, a lookup that cannot complete,
    or a zone that answers every name each mean "not identified as Valory
    operated". Claiming a mech is Valory's when it is not would be the harmful
    direction. Use identify() to tell "not Valory" from "could not check".

    :param mech_address: The mech contract address, with or without `0x`
    :param chain_id: The chain the mech is deployed on
    :return: True only if the mech is identified as Valory operated
    """
    return identify(mech_address, chain_id) is Identification.VALORY
