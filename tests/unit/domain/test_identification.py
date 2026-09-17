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

from unittest.mock import MagicMock, patch

import pytest
import requests

from mech_client.domain.identification import (
    IDENTIFICATION_TIMEOUT,
    identification_url,
    is_valory_operated,
)

MODULE = "mech_client.domain.identification"
GNOSIS_MECH = "0xC05e7412439bD7e91730a6880E18d5D5873F632C"
GNOSIS_NAME = (
    "https://c05e7412439bd7e91730a6880e18d5d5873f632c.100.mechs.valory.xyz/healthcheck"
)


class TestIdentificationUrl:
    """The name is the address without 0x, lowercased, then the chain id."""

    @pytest.mark.parametrize(
        "address",
        [GNOSIS_MECH, GNOSIS_MECH.lower(), GNOSIS_MECH[2:], GNOSIS_MECH[2:].upper()],
        ids=["checksummed", "lowercase", "no_prefix", "no_prefix_upper"],
    )
    def test_address_form_does_not_change_the_name(self, address: str) -> None:
        """Every way of writing the same address yields one name."""
        assert identification_url(address, 100) == GNOSIS_NAME

    @pytest.mark.parametrize("chain_id", [100, 137, 8453, 10, 4663])
    def test_chain_id_is_a_label_of_its_own(self, chain_id: int) -> None:
        """The chain id sits between the address and the zone."""
        url = identification_url(GNOSIS_MECH, chain_id)
        assert f".{chain_id}.mechs.valory.xyz" in url


class TestIsValoryOperated:
    """A mech is Valory operated only when the check clearly succeeds."""

    @staticmethod
    def _response(status_code: int) -> MagicMock:
        """Build a response whose ``ok`` follows the status code."""
        response = MagicMock()
        response.ok = 200 <= status_code < 300
        response.status_code = status_code
        return response

    def test_a_successful_response_identifies_the_mech(self) -> None:
        """A 200 on the mech's own name is what proves it."""
        with patch(f"{MODULE}.requests.get", return_value=self._response(200)) as get:
            assert is_valory_operated(GNOSIS_MECH, 100) is True
        get.assert_called_once_with(GNOSIS_NAME, timeout=IDENTIFICATION_TIMEOUT)

    @pytest.mark.parametrize(
        "status_code", [301, 400, 401, 403, 404, 500, 502], ids=str
    )
    def test_any_non_success_status_is_not_identified(self, status_code: int) -> None:
        """The zone is a wildcard, so a name answering 404 is someone else's."""
        # Resolution alone proves nothing: every name under the zone resolves.
        # Only a route that exists answers 2xx.
        with patch(f"{MODULE}.requests.get", return_value=self._response(status_code)):
            assert is_valory_operated(GNOSIS_MECH, 100) is False

    @pytest.mark.parametrize(
        "error",
        [
            requests.Timeout("slow"),
            requests.ConnectionError("no route"),
            requests.TooManyRedirects("loop"),
            requests.RequestException("other"),
        ],
        ids=["timeout", "connection", "redirects", "generic"],
    )
    def test_a_failed_check_is_not_identified(self, error: Exception) -> None:
        """Fails closed: claiming a mech is Valory's when it is not is the harm."""
        # A check that cannot complete must never produce the Valory notice.
        with patch(f"{MODULE}.requests.get", side_effect=error):
            assert is_valory_operated(GNOSIS_MECH, 100) is False

    def test_the_check_cannot_hold_up_a_request(self) -> None:
        """The timeout is short, since this runs before every request."""
        assert 0 < IDENTIFICATION_TIMEOUT <= 5
