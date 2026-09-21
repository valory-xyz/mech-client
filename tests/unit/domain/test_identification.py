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

"""Tests for the Valory operated mech check."""

import re
import socket
import threading
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, List
from unittest.mock import patch

import pytest
from mech_client.domain import identification
from mech_client.domain.identification import (
    IDENTIFICATION_MAX_WORKERS,
    IDENTIFICATION_TIMEOUT,
    Identification,
    identification_name,
    identify,
    is_valory_operated,
)

MODULE = "mech_client.domain.identification"
GNOSIS_MECH = "0xC05e7412439bD7e91730a6880E18d5D5873F632C"
GNOSIS_NAME = "c05e7412439bd7e91730a6880e18d5d5873f632c-100.mech.valory.xyz"


def _dns(resolving: set) -> Any:
    """Build a getaddrinfo stand-in that resolves only the given names."""
    looked_up: List[str] = []

    def getaddrinfo(name: str, _port: Any) -> list:
        looked_up.append(name)
        if name in resolving:
            return [("ok",)]
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    getaddrinfo.looked_up = looked_up  # type: ignore[attr-defined]
    return getaddrinfo


class TestIdentificationName:
    """The name is the address without 0x, lowercased, then the chain id."""

    @pytest.mark.parametrize(
        "address",
        [GNOSIS_MECH, GNOSIS_MECH.lower(), GNOSIS_MECH[2:], GNOSIS_MECH[2:].upper()],
        ids=["checksummed", "lowercase", "no_prefix", "no_prefix_upper"],
    )
    def test_address_form_does_not_change_the_name(self, address: str) -> None:
        """Every way of writing the same address yields one name."""
        assert identification_name(address, 100) == GNOSIS_NAME

    @pytest.mark.parametrize("chain_id", [100, 137, 8453, 10, 4663, 11155111])
    def test_address_and_chain_share_one_label(self, chain_id: int) -> None:
        """One label, so a single wildcard certificate covers every mech."""
        name = identification_name(GNOSIS_MECH, chain_id)
        label, zone = name.split(".", 1)
        assert zone == "mech.valory.xyz"
        assert label == f"c05e7412439bd7e91730a6880e18d5d5873f632c-{chain_id}"
        # DNS caps a label at 63 characters.
        assert len(label) <= 63


class TestIsValoryOperated:
    """A mech is Valory operated when its own name resolves and a random one does not."""

    def test_a_resolving_name_identifies_the_mech(self) -> None:
        """Only Valory can create a record under the zone, so resolving proves it."""
        dns = _dns({GNOSIS_NAME})
        with patch(f"{MODULE}.socket.getaddrinfo", side_effect=dns):
            assert is_valory_operated(GNOSIS_MECH, 100) is True
        assert dns.looked_up[0] == GNOSIS_NAME

    def test_a_name_that_does_not_resolve_is_not_identified(self) -> None:
        """No record means Valory does not operate it; no probe is needed."""
        dns = _dns(set())
        with patch(f"{MODULE}.socket.getaddrinfo", side_effect=dns):
            assert is_valory_operated(GNOSIS_MECH, 100) is False
        assert dns.looked_up == [GNOSIS_NAME]

    def test_a_wildcard_zone_identifies_nothing(self) -> None:
        """If an arbitrary name resolves too, a positive answer proves nothing."""
        # A wildcard record answers every name under the zone, including other
        # operators' mechs. The check must say no rather than claim them all.
        with patch(f"{MODULE}.socket.getaddrinfo", return_value=[("ok",)]):
            assert identify(GNOSIS_MECH, 100) is Identification.UNKNOWN
            assert is_valory_operated(GNOSIS_MECH, 100) is False

    def test_a_probe_that_cannot_complete_confirms_nothing(self) -> None:
        """The mech's name resolving is not enough if the probe lookup fails."""

        def getaddrinfo(name: str, _port: Any) -> list:
            if name == GNOSIS_NAME:
                return [("ok",)]
            raise socket.gaierror(socket.EAI_AGAIN, "temporary failure")

        with patch(f"{MODULE}.socket.getaddrinfo", side_effect=getaddrinfo):
            assert identify(GNOSIS_MECH, 100) is Identification.UNKNOWN
            assert is_valory_operated(GNOSIS_MECH, 100) is False

    def test_a_confirmed_mech_is_identified_as_valory(self) -> None:
        """Own name resolves, probe does not exist: the mech is Valory's."""
        with patch(f"{MODULE}.socket.getaddrinfo", side_effect=_dns({GNOSIS_NAME})):
            assert identify(GNOSIS_MECH, 100) is Identification.VALORY

    def test_a_missing_name_is_identified_as_not_valory(self) -> None:
        """A name that does not exist is a real answer, not a failed check."""
        with patch(f"{MODULE}.socket.getaddrinfo", side_effect=_dns(set())):
            assert identify(GNOSIS_MECH, 100) is Identification.NOT_VALORY

    def test_the_probe_can_never_be_a_mech_and_stays_in_the_same_chain(self) -> None:
        """The probe name is not 40 hex characters and sits beside the real name."""
        dns = _dns({GNOSIS_NAME})
        with patch(f"{MODULE}.socket.getaddrinfo", side_effect=dns):
            is_valory_operated(GNOSIS_MECH, 100)
        probe = dns.looked_up[1]
        label, zone = probe.split(".", 1)
        assert re.fullmatch(r"[0-9a-f]{32}-100", label)
        assert zone == "mech.valory.xyz"

    def test_each_check_uses_a_fresh_probe(self) -> None:
        """A fixed probe name could be registered to defeat the wildcard guard."""
        dns = _dns({GNOSIS_NAME})
        with patch(f"{MODULE}.socket.getaddrinfo", side_effect=dns):
            is_valory_operated(GNOSIS_MECH, 100)
            is_valory_operated(GNOSIS_MECH, 100)
        assert dns.looked_up[1] != dns.looked_up[3]

    @pytest.mark.parametrize(
        ("error", "expected", "level"),
        [
            (
                socket.gaierror(socket.EAI_NONAME, "not known"),
                Identification.NOT_VALORY,
                "DEBUG",
            ),
            (
                socket.gaierror(socket.EAI_AGAIN, "temporary failure"),
                Identification.UNKNOWN,
                "WARNING",
            ),
            (OSError("network unreachable"), Identification.UNKNOWN, "WARNING"),
            (UnicodeError("label too long"), Identification.UNKNOWN, "WARNING"),
        ],
        ids=["no_such_name", "resolver_unavailable", "no_network", "bad_label"],
    )
    def test_a_failed_lookup_is_not_identified(
        self,
        error: Exception,
        expected: Identification,
        level: str,
    ) -> None:
        """Fails closed, and only a missing name is quiet; a broken check warns."""
        with (
            patch(f"{MODULE}.socket.getaddrinfo", side_effect=error),
            patch(f"{MODULE}.logger") as logger,
        ):
            assert identify(GNOSIS_MECH, 100) is expected
            assert is_valory_operated(GNOSIS_MECH, 100) is False
        quiet, loud = logger.debug.called, logger.warning.called
        assert (quiet, loud) == ((True, False) if level == "DEBUG" else (False, True))

    def test_a_slow_lookup_gives_up_rather_than_holding_the_request(self) -> None:
        """A hung resolver must not stall the request; it times out, warning."""
        with (
            patch.object(identification._EXECUTOR, "submit") as submit,  # pylint: disable=protected-access
            patch(f"{MODULE}.logger") as logger,
        ):
            submit.return_value.result.side_effect = FuturesTimeoutError()
            assert identify(GNOSIS_MECH, 100) is Identification.UNKNOWN
        submit.return_value.result.assert_called_once_with(
            timeout=IDENTIFICATION_TIMEOUT
        )
        assert "took longer than" in logger.warning.call_args.args[0]

    def test_the_timeout_does_not_wait_for_a_hung_lookup(self) -> None:
        """Giving up must return straight away, not block on the stuck thread."""
        release = threading.Event()

        def hang(_name: str, _port: Any) -> list:
            release.wait(5)
            return [("ok",)]

        with (
            patch(f"{MODULE}.IDENTIFICATION_TIMEOUT", 0.05),
            patch(f"{MODULE}.socket.getaddrinfo", side_effect=hang),
        ):
            assert (
                identification._lookup(GNOSIS_NAME) is None
            )  # pylint: disable=protected-access
        release.set()

    def test_hung_lookups_cannot_take_more_than_the_capped_threads(self) -> None:
        """Lookups queued behind hung ones are cancelled, not left to pile up."""
        release = threading.Event()
        started: List[str] = []

        def hang(name: str, _port: Any) -> list:
            started.append(name)
            release.wait(5)
            return [("ok",)]

        executor = identification.ThreadPoolExecutor(max_workers=2)
        try:
            with (
                patch.object(identification, "_EXECUTOR", executor),
                patch(f"{MODULE}.IDENTIFICATION_TIMEOUT", 0.05),
                patch(f"{MODULE}.socket.getaddrinfo", side_effect=hang),
                patch(f"{MODULE}.logger"),
            ):
                for index in range(5):
                    assert identification._lookup(f"n{index}") is None  # pylint: disable=protected-access
            release.set()
            executor.shutdown(wait=True)
            # Only the two lookups that got a thread ever ran; the three queued
            # behind them were cancelled and never took a thread.
            assert started == ["n0", "n1"]
        finally:
            release.set()
            executor.shutdown(wait=True)

    def test_a_lookup_that_fails_after_the_timeout_is_logged(self) -> None:
        """An abandoned lookup's late error is recorded, not lost."""
        release = threading.Event()

        def fail_late(_name: str, _port: Any) -> list:
            release.wait(5)
            raise socket.gaierror(socket.EAI_AGAIN, "late failure")

        executor = identification.ThreadPoolExecutor(max_workers=1)
        try:
            with (
                patch.object(identification, "_EXECUTOR", executor),
                patch(f"{MODULE}.IDENTIFICATION_TIMEOUT", 0.05),
                patch(f"{MODULE}.socket.getaddrinfo", side_effect=fail_late),
                patch(f"{MODULE}.logger") as logger,
            ):
                assert identification._lookup(GNOSIS_NAME) is None  # pylint: disable=protected-access
                release.set()
                executor.shutdown(wait=True)
            assert "failed late" in logger.debug.call_args.args[0]
        finally:
            release.set()

    def test_the_pool_is_capped(self) -> None:
        """A fixed cap bounds the threads hung lookups can hold."""
        assert 1 <= IDENTIFICATION_MAX_WORKERS <= 16
        assert (
            identification._EXECUTOR._max_workers  # pylint: disable=protected-access
            == IDENTIFICATION_MAX_WORKERS
        )

    def test_the_check_cannot_hold_up_a_request(self) -> None:
        """The timeout is short, since this runs before every request."""
        assert 0 < IDENTIFICATION_TIMEOUT <= 5
