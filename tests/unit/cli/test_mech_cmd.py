# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2025-2026 Valory AG
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

"""Tests for mech command."""

import time
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
import requests
from click.testing import CliRunner
from mech_client.cli.commands.mech_cmd import (
    _claimed_operator_labels,
    _fetch_manifest,
    _fetch_manifests,
    _operator_claim_label,
    _render_report,
    _since,
    _valory_operated_labels,
    mech,
)
from mech_client.domain.identification import VALORY_TERMS_NOTICE
from mech_client.domain.tools.manager import (
    DELIVERY_NOTE,
    IDENTIFICATION_NOTE,
    PAYMENT_NOTE,
)
from mech_client.infrastructure.config import get_mech_config
from mech_client.infrastructure.subgraph.queries import MechRecord
from mech_client.utils.errors import SubgraphError
from mech_client.utils.errors.exceptions import ManifestError

MODULE = "mech_client.cli.commands.mech_cmd"
TERMS_URL = "https://www.valory.xyz/terms/mechs"
MECH_ADDRESS = "0xc05e7412439bd7e91730a6880e18d5d5873f632c"
MECH_ADDRESS_CHECKSUMMED = "0xC05e7412439bD7e91730a6880E18d5D5873F632C"
METADATA_HASH = "0x" + "c" * 64
CREATED_AT = datetime(2025, 6, 4, 16, 35, 20, tzinfo=timezone.utc)
VERIFIED_OPERATOR = {
    "name": "Valory",
    "domain": "www.valory.xyz",
    "url": "https://www.valory.xyz",
    "domain_verified": True,
}
UNVERIFIED_OPERATOR = {
    **VERIFIED_OPERATOR,
    "domain_verified": False,
    "verification_note": "The operator's domain publishes no proof for this mech.",
}


_PUBLISHED = [{"metadata": METADATA_HASH}]


def _mech_row(
    service_id: str = "1",
    address: str = "0x" + "a" * 40,
    metadata: Any = _PUBLISHED,
    **counters: str,
) -> Dict[str, Any]:
    """Build one row as query_mm_mechs_info returns it."""
    row: Dict[str, Any] = {
        "id": service_id,
        "address": address,
        "mechFactory": "0x" + "b" * 40,
        "totalDeliveriesTransactions": "1",
        "service": {"id": service_id, "totalDeliveries": "1", "metadata": metadata},
        "mech_type": "Fixed Price Native",
    }
    row.update(counters)
    return row


def _record(metadata_hash: Optional[str] = METADATA_HASH) -> MechRecord:
    """Build a mech record as query_mech_record returns it."""
    return MechRecord(
        service_id=2182,
        received_requests=10,
        self_delivered=8,
        delivered_by_others=1,
        created_at=CREATED_AT,
        payment_type="0xba699a34be8fe0e7725e93dcbce1701b0211a8ca61330aaeb8a05bf2ec7abed1",
        metadata_hash=metadata_hash,
    )


def _report(**extra: Any) -> Dict[str, Any]:
    """Build a report as ToolManager.mech_report returns it."""
    report: Dict[str, Any] = {
        "valory_operated": False,
        "delivery": {
            "received_requests": 10,
            "self_delivered": 8,
            "delivered_by_others": 1,
            "since": CREATED_AT.isoformat(),
            "age_days": 400,
            "note": DELIVERY_NOTE,
        },
        "payment": {"type": "native", "note": PAYMENT_NOTE},
    }
    report.update(extra)
    return report


@pytest.fixture(autouse=True)
def _no_identification_network() -> None:
    """Keep the listing tests off the network for the Operator column too.

    The column asks the identification check per mech. Existing listing tests
    only care about the subgraph shape, so by default every mech is
    unconfirmed and the column renders blank.
    """
    with patch(f"{MODULE}.is_valory_operated", return_value=False):
        yield


@pytest.fixture(autouse=True)
def _no_metadata_network() -> None:
    """Keep the listing tests off the network: manifest fetches fail fast.

    The Terms and Claimed Operator columns read each mech's manifest over
    HTTP. Existing listing tests only care about the subgraph shape, so by
    default every fetch raises and the columns render blank. Tests that
    exercise the columns patch ``requests.get`` themselves.
    """
    with patch(
        f"{MODULE}.requests.get",
        side_effect=requests.ConnectionError("no network in tests"),
    ):
        yield


@pytest.fixture(autouse=True)
def _no_creation_query() -> None:
    """Keep the listing tests off the subgraph for the Since column.

    Tests that exercise the column patch ``query_mech_creations`` themselves.
    """
    with patch(f"{MODULE}.query_mech_creations", return_value={}):
        yield


class TestFetchManifest:
    """_fetch_manifest reads a manifest document, or gives None."""

    def test_returns_none_without_a_metadata_link(self) -> None:
        """No link means nothing to fetch; no HTTP call is made."""
        with patch(f"{MODULE}.requests.get") as mock_get:
            assert _fetch_manifest(None) is None
        mock_get.assert_not_called()

    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ({"termsUrl": TERMS_URL}, {"termsUrl": TERMS_URL}),
            ({}, {}),
            (["not", "a", "dict"], None),
            ("text", None),
            (None, None),
        ],
        ids=["object", "empty_object", "list", "string", "null"],
    )
    def test_only_a_json_object_is_a_manifest(self, body: Any, expected: Any) -> None:
        """Any body that is not a JSON object reads as unreadable."""
        response = MagicMock()
        response.json.return_value = body
        with patch(f"{MODULE}.requests.get", return_value=response) as mock_get:
            assert _fetch_manifest("https://gateway/ipfs/abc") == expected
        mock_get.assert_called_once_with("https://gateway/ipfs/abc", timeout=10)

    @pytest.mark.parametrize(
        "error",
        [requests.Timeout("slow"), requests.ConnectionError("down")],
        ids=["timeout", "connection"],
    )
    def test_transport_failure_yields_none(self, error: Exception) -> None:
        """A slow or unreachable gateway must not break the listing."""
        with patch(f"{MODULE}.requests.get", side_effect=error):
            assert _fetch_manifest("https://gateway/ipfs/abc") is None

    def test_invalid_json_body_yields_none(self) -> None:
        """A gateway body that is not JSON must not break the listing."""
        response = MagicMock()
        response.json.side_effect = ValueError("bad json")
        with patch(f"{MODULE}.requests.get", return_value=response):
            assert _fetch_manifest("https://gateway/ipfs/abc") is None


class TestFetchManifests:
    """_fetch_manifests fans the per-mech fetches out and keeps table order."""

    def test_empty_input_makes_no_calls(self) -> None:
        """No mechs, no threads, no HTTP."""
        with patch(f"{MODULE}.requests.get") as mock_get:
            assert _fetch_manifests([]) == []
        mock_get.assert_not_called()

    def test_results_keep_the_input_order_and_nones(self) -> None:
        """Each output slot matches its input link even when fetches interleave."""
        # Slow first, fast second: with unordered collection the fast one would
        # come back first. executor.map must keep table order regardless.

        def fake_get(url: str, timeout: int) -> MagicMock:  # noqa: ARG001
            response = MagicMock()
            if url.endswith("slow"):
                time.sleep(0.05)
                response.json.return_value = {"termsUrl": "https://slow/terms"}
            else:
                response.json.return_value = {"termsUrl": "https://fast/terms"}
            return response

        with patch(f"{MODULE}.requests.get", side_effect=fake_get):
            out = _fetch_manifests(["https://g/slow", None, "https://g/fast"])
        assert out == [
            {"termsUrl": "https://slow/terms"},
            None,
            {"termsUrl": "https://fast/terms"},
        ]


class TestValoryOperatedLabels:
    """The Operator column names only the mechs the check confirms."""

    def test_no_mechs_makes_no_calls(self) -> None:
        """An empty table asks nothing."""
        with patch(f"{MODULE}.is_valory_operated") as check:
            assert _valory_operated_labels([], 100) == []
        check.assert_not_called()

    def test_only_confirmed_mechs_are_labelled(self) -> None:
        """A confirmed mech reads Valory; anything else stays blank."""
        # Blank rather than "independent": the check fails closed, so an
        # unreachable mech and an independent one are indistinguishable here,
        # and labelling both would state something we have not established.
        # Keyed on the address, not positional: the checks run in a thread
        # pool, so a positional side_effect list would hand answers out in
        # whatever order the threads happen to call, not in table order.
        confirmed = {"0xaaa": True, "0xbbb": False, "0xccc": True}
        with patch(
            f"{MODULE}.is_valory_operated",
            side_effect=lambda address, _chain_id: confirmed[address],
        ):
            assert _valory_operated_labels(list(confirmed), 100) == [
                "Valory",
                "",
                "Valory",
            ]

    def test_labels_keep_the_table_order(self) -> None:
        """Each label belongs to its own row even when checks interleave."""

        def slow_first(address: str, _chain_id: int) -> bool:
            if address == "0xslow":
                time.sleep(0.05)
                return True
            return False

        with patch(f"{MODULE}.is_valory_operated", side_effect=slow_first):
            assert _valory_operated_labels(["0xslow", "0xfast"], 100) == ["Valory", ""]

    def test_the_chain_id_reaches_the_check(self) -> None:
        """A mech is identified per chain, so the chain id must be passed on."""
        with patch(f"{MODULE}.is_valory_operated", return_value=False) as check:
            _valory_operated_labels(["0xaaa"], 137)
        check.assert_called_once_with("0xaaa", 137)


class TestOperatorClaimLabel:
    """The Claimed Operator cell names the claim and whether the domain backs it."""

    @pytest.mark.parametrize(
        ("operator", "expected"),
        [
            (None, ""),
            (VERIFIED_OPERATOR, "Valory (www.valory.xyz, verified)"),
            (UNVERIFIED_OPERATOR, "Valory (www.valory.xyz, unverified)"),
        ],
        ids=["unpublished", "verified", "unverified"],
    )
    def test_label(self, operator: Optional[Dict[str, Any]], expected: str) -> None:
        """A claim reads name, domain and status; no claim reads blank."""
        assert _operator_claim_label(operator) == expected


class TestClaimedOperatorLabels:
    """The Claimed Operator column is built per row, in parallel, order kept."""

    def test_no_rows_makes_no_calls(self) -> None:
        """An empty table checks nothing."""
        with patch(f"{MODULE}.claimed_operator") as claim:
            assert _claimed_operator_labels("gnosis", 100, [], []) == []
        claim.assert_not_called()

    def test_an_unreadable_manifest_is_blank_and_not_checked(self) -> None:
        """A row without a manifest makes no claim, so there is nothing to check."""
        with patch(f"{MODULE}.claimed_operator") as claim:
            assert _claimed_operator_labels("gnosis", 100, [1], [None]) == [""]
        claim.assert_not_called()

    def test_each_row_is_checked_with_its_own_service_id(self) -> None:
        """The check is keyed by service id, and the chain reaches it."""
        manifests: List[Optional[Dict[str, Any]]] = [
            {"operator": "a"},
            {"operator": "b"},
        ]

        def claim(
            chain_config: str, chain_id: int, service_id: int, manifest: Dict[str, Any]
        ) -> Optional[Dict[str, Any]]:
            assert (chain_config, chain_id) == ("gnosis", 100)
            if service_id == 2:
                time.sleep(0.05)
                return VERIFIED_OPERATOR
            assert manifest == {"operator": "a"}
            return None

        with patch(f"{MODULE}.claimed_operator", side_effect=claim):
            assert _claimed_operator_labels("gnosis", 100, [2, 1], manifests[::-1]) == [
                "Valory (www.valory.xyz, verified)",
                "",
            ]


class TestSince:
    """The Since column is a UTC date, or blank."""

    def test_renders_the_utc_date(self) -> None:
        """Only the date part is shown, in ISO 8601."""
        assert _since(CREATED_AT) == "2025-06-04"

    def test_unknown_is_blank(self) -> None:
        """A mech without a creation row shows nothing."""
        assert _since(None) == ""


class TestMechListCommand:
    """Tests for mech list command."""

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_marks_a_valory_operated_mech(
        self, mock_query: MagicMock
    ) -> None:
        """The Operator column shows Valory for a mech the check confirms."""
        mock_query.return_value = [_mech_row()]
        with patch(f"{MODULE}.is_valory_operated", return_value=True) as check:
            result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])
        assert result.exit_code == 0
        assert "Operator" in result.output
        assert "Valory" in result.output
        # Gnosis is chain 100; the listing must identify per chain.
        check.assert_called_once_with("0x" + "a" * 40, 100)

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_shows_terms_column(self, mock_query: MagicMock) -> None:
        """The Terms column carries the termsUrl read from each mech's manifest."""
        mock_query.return_value = [_mech_row()]
        response = MagicMock()
        response.json.return_value = {"termsUrl": TERMS_URL}
        with patch(f"{MODULE}.requests.get", return_value=response) as mock_get:
            result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])
        assert result.exit_code == 0
        assert "Terms" in result.output
        assert TERMS_URL in result.output
        # The fetch targets the same gateway link shown in the Metadata Link column.
        fetched_url = mock_get.call_args[0][0]
        assert "c" * 64 in fetched_url

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_shows_the_delivery_record_and_age(
        self, mock_query: MagicMock
    ) -> None:
        """The counters come from the listing query; the age from the creation rows."""
        mock_query.return_value = [
            _mech_row(
                receivedRequests="1020284",
                selfDeliveredFromReceived="896660",
                deliveredByOthersFromReceived="123617",
            )
        ]
        with patch(
            f"{MODULE}.query_mech_creations", return_value={"0x" + "a" * 40: CREATED_AT}
        ) as creations:
            result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])
        assert result.exit_code == 0
        for column in ("Received", "Self-delivered", "By others", "Since"):
            assert column in result.output
        for value in ("1020284", "896660", "123617", "2025-06-04"):
            assert value in result.output
        assert "settled on-chain" in result.output
        creations.assert_called_once_with("gnosis", ["0x" + "a" * 40])

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_shows_the_claimed_operator(
        self, mock_query: MagicMock
    ) -> None:
        """The Claimed Operator column reads the manifest and checks the domain."""
        mock_query.return_value = [_mech_row(service_id="2182")]
        response = MagicMock()
        response.json.return_value = {"operator": {"name": "Valory", "domain": "x"}}
        with (
            patch(f"{MODULE}.requests.get", return_value=response),
            patch(
                f"{MODULE}.claimed_operator", return_value=UNVERIFIED_OPERATOR
            ) as claim,
        ):
            result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])
        assert result.exit_code == 0
        assert "Claimed Operator" in result.output
        assert "Valory (www.valory.xyz, unverified)" in result.output
        claim.assert_called_once_with(
            "gnosis", 100, 2182, {"operator": {"name": "Valory", "domain": "x"}}
        )

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_without_counters_leaves_the_cells_blank(
        self, mock_query: MagicMock
    ) -> None:
        """An indexer that does not return the counters does not break the table."""
        mock_query.return_value = [_mech_row()]
        result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])
        assert result.exit_code == 0
        assert "Received" in result.output

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_with_realistic_metadata_structure(
        self, mock_query: MagicMock
    ) -> None:
        """Test mech list handles actual GraphQL response structure.

        The actual subgraph returns metadata as a LIST of dicts:
        metadata: [{'metadata': '0x...'}]

        This test verifies the command correctly accesses metadata[0]["metadata"]
        instead of metadata["metadata"].
        """
        mock_query.return_value = [
            _mech_row(
                service_id="2182",
                address=MECH_ADDRESS,
                metadata=[
                    {
                        "metadata": "0x4d82a931d803e2b46b0dcd53f558f8de8305fd44b36288b42287ef1450a6611f"
                    }
                ],
            )
        ]
        mock_query.return_value[0]["totalDeliveriesTransactions"] = "781673"
        mock_query.return_value[0]["service"]["totalDeliveries"] = "781673"

        result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])

        assert result.exit_code == 0
        assert "2182" in result.output
        assert "Fixed Price Native" in result.output
        assert "781673" in result.output
        assert (
            "4d82a931d803e2b46b0dcd53f558f8de8305fd44b36288b42287ef1450a6611f"
            in result.output
        )

    @pytest.mark.parametrize("metadata", [None, []], ids=["null", "empty_list"])
    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_with_empty_metadata(
        self, mock_query: MagicMock, metadata: Any
    ) -> None:
        """A mech without metadata lists with blank metadata-derived columns."""
        mock_query.return_value = [_mech_row(service_id="1841", metadata=metadata)]
        mock_query.return_value[0]["service"]["totalDeliveries"] = "253"

        with patch(f"{MODULE}.requests.get") as mock_get:
            result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])

        assert result.exit_code == 0
        assert "1841" in result.output
        assert "253" in result.output
        mock_get.assert_not_called()

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_with_multiple_mechs(self, mock_query: MagicMock) -> None:
        """Test mech list displays multiple mechs correctly."""
        first = _mech_row(service_id="2182", address=MECH_ADDRESS)
        second = _mech_row(service_id="2469", address="0x" + "d" * 40)
        second["mech_type"] = "NvmSubscription Native"
        second["service"]["totalDeliveries"] = "1425"
        mock_query.return_value = [first, second]

        result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])

        assert result.exit_code == 0
        assert "2182" in result.output
        assert "2469" in result.output
        assert "Fixed Price Native" in result.output
        assert "NvmSubscription Native" in result.output
        assert "1425" in result.output

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_with_no_mechs(self, mock_query: MagicMock) -> None:
        """Test mech list displays message when no mechs found."""
        mock_query.return_value = []

        result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])

        assert result.exit_code == 0
        assert "No mechs found" in result.output

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_list_command_for_base_chain(self, mock_query: MagicMock) -> None:
        """Test mech list works for base chain."""
        mock_query.return_value = [_mech_row(service_id="100")]
        mock_query.return_value[0]["service"]["totalDeliveries"] = "500"

        result = CliRunner().invoke(mech, ["list", "--chain-config", "base"])

        assert result.exit_code == 0
        assert "100" in result.output
        assert "500" in result.output

    @patch(f"{MODULE}.query_mm_mechs_info")
    def test_metadata_with_multiple_entries(self, mock_query: MagicMock) -> None:
        """Test metadata list with multiple entries (uses first one)."""
        mock_query.return_value = [
            _mech_row(
                metadata=[{"metadata": "0xfirst_hash"}, {"metadata": "0xsecond_hash"}]
            )
        ]

        result = CliRunner().invoke(mech, ["list", "--chain-config", "gnosis"])

        assert result.exit_code == 0
        assert "first_hash" in result.output


class TestMechListWithoutSubgraph:
    """Tests for mech list on a marketplace chain whose subgraph URL is blank."""

    def test_chain_without_subgraph_gets_the_subgraph_error_not_the_catch_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test mech list on a chain with no subgraph shows the subgraph error."""
        monkeypatch.delenv("MECHX_SUBGRAPH_URL", raising=False)
        blank = replace(get_mech_config("robinhood"), subgraph_url="")

        runner = CliRunner()
        with patch(
            "mech_client.infrastructure.subgraph.queries.get_mech_config",
            return_value=blank,
        ):
            result = runner.invoke(mech, ["list", "--chain-config", "robinhood"])

        assert result.exit_code == 1
        assert (
            "Subgraph endpoint error: Subgraph URL not set for chain config: robinhood"
            in result.output
        )
        assert "Unexpected error" not in result.output


class TestRenderReport:
    """The report prints every section, saying what is unknown."""

    def test_full_report(self) -> None:
        """Operator, terms, record, payment and benchmarks each get their lines."""
        report = _report(
            valory_operated=True,
            terms=VALORY_TERMS_NOTICE,
            terms_url=TERMS_URL,
            operator=VERIFIED_OPERATOR,
            benchmarks={
                "tool-a": {"metric": "accuracy", "window": "30d", "url": "https://b/a"}
            },
            benchmark_note="claim only",
        )
        lines = _render_report(MECH_ADDRESS, report)
        assert lines[0] == f"Mech {MECH_ADDRESS}"
        assert "Operator: Valory (https://www.valory.xyz), domain verified" in lines
        assert f"Terms: {VALORY_TERMS_NOTICE}" in lines
        assert f"Terms link: {TERMS_URL}" in lines
        assert (
            "Delivery record: 10 received, 8 self-delivered, 1 delivered by others, "
            f"since {CREATED_AT.isoformat()} (400 days)" in lines
        )
        assert f"  {DELIVERY_NOTE}" in lines
        assert f"Payment: native. {PAYMENT_NOTE}" in lines
        assert "Benchmarks: claim only" in lines
        assert "  tool-a: accuracy over 30d, https://b/a" in lines

    def test_unverified_operator_shows_the_reason(self) -> None:
        """An unverified claim carries its note on the same line."""
        lines = _render_report(MECH_ADDRESS, _report(operator=UNVERIFIED_OPERATOR))
        assert (
            "Operator: Valory (https://www.valory.xyz), domain unverified: "
            "The operator's domain publishes no proof for this mech." in lines
        )

    def test_absent_sections_say_so(self) -> None:
        """No operator, no benchmarks and an unfinished check are each stated."""
        lines = _render_report(
            MECH_ADDRESS, _report(identification_note=IDENTIFICATION_NOTE)
        )
        assert "Operator: not published in the mech's manifest" in lines
        assert f"Terms: {IDENTIFICATION_NOTE}" in lines
        assert "Benchmarks: none published in the mech's manifest" in lines
        assert not any(line.startswith("Terms link") for line in lines)

    def test_a_mech_without_terms_lines_prints_none(self) -> None:
        """A non-Valory mech with no link and a finished check shows no terms line."""
        lines = _render_report(MECH_ADDRESS, _report())
        assert not any(line.startswith("Terms") for line in lines)


class TestMechInfoCommand:
    """mech info reports on one mech, failing closed."""

    @patch(f"{MODULE}.ToolManager")
    @patch(f"{MODULE}.query_mech_record", return_value=_record())
    def test_reports_from_the_record_and_the_manifest(
        self, mock_record: MagicMock, mock_manager: MagicMock
    ) -> None:
        """The record is read once and handed to the report with the manifest."""
        manifest = {"operator": {"name": "Valory", "domain": "www.valory.xyz"}}
        response = MagicMock()
        response.json.return_value = manifest
        mock_manager.return_value.mech_report.return_value = _report(
            operator=VERIFIED_OPERATOR
        )
        with patch(f"{MODULE}.requests.get", return_value=response) as mock_get:
            result = CliRunner().invoke(
                mech, ["info", "--chain-config", "gnosis", "--address", MECH_ADDRESS]
            )
        assert result.exit_code == 0, result.output
        assert f"Mech {MECH_ADDRESS_CHECKSUMMED}" in result.output
        assert "domain verified" in result.output
        assert "10 received" in result.output
        mock_record.assert_called_once_with("gnosis", MECH_ADDRESS_CHECKSUMMED)
        assert "c" * 64 in mock_get.call_args[0][0]
        mock_manager.assert_called_once_with("gnosis")
        mock_manager.return_value.mech_report.assert_called_once_with(
            MECH_ADDRESS_CHECKSUMMED, manifest, _record()
        )

    @patch(f"{MODULE}.query_mech_record", return_value=_record(metadata_hash=None))
    def test_a_mech_without_a_manifest_gets_no_report(
        self, _mock_record: MagicMock
    ) -> None:
        """No manifest hash means no report, named as a manifest error."""
        result = CliRunner().invoke(
            mech, ["info", "--chain-config", "gnosis", "--address", MECH_ADDRESS]
        )
        assert result.exit_code == 1
        assert "Manifest error" in result.output
        assert "publishes no manifest" in result.output

    @patch(f"{MODULE}.ToolManager")
    @patch(f"{MODULE}.query_mech_record", return_value=_record())
    def test_an_unreadable_manifest_gets_no_report(
        self, _mock_record: MagicMock, mock_manager: MagicMock
    ) -> None:
        """A manifest that cannot be fetched is passed as None and the report refuses."""
        mock_manager.return_value.mech_report.side_effect = ManifestError(
            "could not be read"
        )
        result = CliRunner().invoke(
            mech, ["info", "--chain-config", "gnosis", "--address", MECH_ADDRESS]
        )
        assert result.exit_code == 1
        assert "Manifest error: could not be read" in result.output
        mock_manager.return_value.mech_report.assert_called_once_with(
            MECH_ADDRESS_CHECKSUMMED, None, _record()
        )

    @patch(f"{MODULE}.query_mech_record", side_effect=SubgraphError("not indexed"))
    def test_an_unknown_mech_gets_the_subgraph_error(
        self, _mock_record: MagicMock
    ) -> None:
        """A mech the indexer does not know is a subgraph error, not a crash."""
        result = CliRunner().invoke(
            mech, ["info", "--chain-config", "gnosis", "--address", MECH_ADDRESS]
        )
        assert result.exit_code == 1
        assert "Subgraph endpoint error" in result.output
        assert "not indexed" in result.output

    def test_an_invalid_address_is_rejected_before_any_query(self) -> None:
        """The address is validated first; nothing is fetched for a bad one."""
        with patch(f"{MODULE}.query_mech_record") as mock_record:
            result = CliRunner().invoke(
                mech, ["info", "--chain-config", "gnosis", "--address", "0xnope"]
            )
        assert result.exit_code == 1
        assert "Invalid Mech address" in result.output
        mock_record.assert_not_called()

    def test_an_unknown_chain_is_rejected(self) -> None:
        """The chain is validated like every other command's."""
        result = CliRunner().invoke(
            mech, ["info", "--chain-config", "nowhere", "--address", MECH_ADDRESS]
        )
        assert result.exit_code == 1
        assert "nowhere" in result.output
