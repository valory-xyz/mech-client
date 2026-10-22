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

"""Tests for the operator claim and its domain check."""

import json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
import requests
from mech_client.domain.operator import (
    IDENTITY_REGISTRY,
    AGENT_ID_MAX_DIGITS,
    NO_AGENT_ID_NOTE,
    PROOF_CHUNK_BYTES,
    PROOF_FETCH_TIMEOUT,
    PROOF_MAX_BYTES,
    PROOF_MISMATCH_NOTE,
    PROOF_NOT_FOUND_NOTE,
    PROOF_REDIRECTED_NOTE,
    PROOF_UNAVAILABLE_NOTE,
    TEXT_MAX_LENGTH,
    DomainVerification,
    ExpectedCost,
    Operator,
    ProofStatus,
    base_units,
    clean_text,
    fetch_domain_proof,
    hostname,
    https_url,
    proof_matches,
    proof_url,
    read_benchmarks,
    read_expected_costs,
    read_operator,
    verify_domain,
)

MODULE = "mech_client.domain.operator"
DOMAIN = "www.valory.xyz"
PROOF_URL = f"https://{DOMAIN}/.well-known/agent-registration.json"
GNOSIS = 100
AGENT_ID = 2182
BENCHMARK_URL = "https://analytics.test/v1/metrics/mech/100/0xabc"
EXPECTED_COST_WEI = 12_000_000_000_000_000
UINT256_MAX = 2**256 - 1


def _registration(chain_id: int = GNOSIS, agent_id: Any = AGENT_ID) -> Dict[str, Any]:
    """Build one proof registration entry."""
    return {
        "agentRegistry": f"eip155:{chain_id}:{IDENTITY_REGISTRY}",
        "agentId": agent_id,
    }


def _response(
    status_code: int,
    body: Any = None,
    bad_json: bool = False,
    raw: Optional[bytes] = None,
) -> MagicMock:
    """Build a stand-in for a streaming requests response."""
    response = MagicMock()
    response.status_code = status_code
    response.__enter__.return_value = response
    if raw is None:
        raw = b"not json" if bad_json else json.dumps(body).encode()
    response.iter_content.return_value = [
        raw[i : i + PROOF_CHUNK_BYTES] for i in range(0, len(raw), PROOF_CHUNK_BYTES)
    ]
    return response


class TestCleanText:
    """A text field is passed on stripped, or not at all."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("Valory", "Valory"),
            ("  Valory AG  ", "Valory AG"),
            ("", None),
            ("   ", None),
            (None, None),
            (12, None),
            (["Valory"], None),
            ("Val\x00ory", None),
            ("Valory\n", "Valory"),
            ("Val\nory", None),
            ("x" * (TEXT_MAX_LENGTH + 1), None),
            ("x" * TEXT_MAX_LENGTH, "x" * TEXT_MAX_LENGTH),
        ],
        ids=[
            "plain",
            "stripped",
            "empty",
            "blank",
            "none",
            "int",
            "list",
            "nul_byte",
            "trailing_newline_stripped",
            "newline_inside",
            "over_cap",
            "at_cap",
        ],
    )
    def test_reads_only_printable_bounded_strings(
        self, value: Any, expected: Optional[str]
    ) -> None:
        """Only a non-blank printable string within the cap is returned."""
        assert clean_text(value) == expected


class TestHttpsUrl:
    """A URL is parsed, not prefix-tested."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (BENCHMARK_URL, BENCHMARK_URL),
            (f"  {BENCHMARK_URL}  ", BENCHMARK_URL),
            ("https://", None),
            ("https:///path", None),
            ("http://analytics.test/x", None),
            ("analytics.test/x", None),
            ("https://analytics.test/a b", None),
            ("https://analytics.test/a\x07", None),
            ("https://[::1", None),
            ("", None),
            (None, None),
            (7, None),
            ("https://h/" + "x" * 2040, None),
        ],
        ids=[
            "plain",
            "stripped",
            "scheme_only",
            "no_host",
            "http",
            "no_scheme",
            "space",
            "control_char",
            "unparseable",
            "empty",
            "none",
            "int",
            "over_cap",
        ],
    )
    def test_requires_https_with_a_host(
        self, value: Any, expected: Optional[str]
    ) -> None:
        """Only an https URL with a host and no whitespace is returned."""
        assert https_url(value) == expected


class TestHostname:
    """The operator domain is a bare lowercase hostname."""

    @pytest.mark.parametrize(
        "value",
        [
            DOMAIN,
            "valory.xyz",
            "a-b.c-d.example",
            "  valory.xyz  ",
            "x" * 63 + ".example",
            "1.2.3.example",
            "example.xn--p1ai",
        ],
        ids=[
            "www",
            "apex",
            "hyphens",
            "stripped",
            "max_label",
            "digit_labels",
            "punycode_tld",
        ],
    )
    def test_accepts_bare_lowercase_hostnames(self, value: str) -> None:
        """A dotted name of valid labels is accepted, stripped."""
        assert hostname(value) == value.strip()

    @pytest.mark.parametrize(
        "value",
        [
            "https://valory.xyz",
            "valory.xyz/",
            "valory.xyz/path",
            "valory.xyz:443",
            "user@valory.xyz",
            "valory.xyz.",
            ".valory.xyz",
            "Valory.xyz",
            "valory",
            "val ory.xyz",
            "-valory.xyz",
            "valory-.xyz",
            "x" * 64 + ".example",
            "192.168.0.1",
            "0x7f.0x1",
            "0x7f.0x0.0x0.0x1",
            "example.0x1",
            "example.c0m",
            "example.123",
            "example.xn--",
            "valory.xyz?x=1",
            "valory.xyz#frag",
            "ｖalory.xyz",
            "",
            None,
            5,
            ("a." * 127) + "example",
        ],
        ids=[
            "scheme",
            "trailing_slash",
            "path",
            "port",
            "credentials",
            "trailing_dot",
            "leading_dot",
            "uppercase",
            "no_dot",
            "space",
            "leading_hyphen",
            "trailing_hyphen",
            "label_too_long",
            "ipv4",
            "hex_ipv4_short",
            "hex_ipv4",
            "hex_tld",
            "digit_in_tld",
            "numeric_tld",
            "empty_punycode",
            "query",
            "fragment",
            "non_ascii",
            "empty",
            "none",
            "int",
            "too_long",
        ],
    )
    def test_rejects_anything_but_a_bare_hostname(self, value: Any) -> None:
        """A scheme, path, port, case, bad label or IPv4 literal is rejected."""
        assert hostname(value) is None


class TestReadOperator:
    """The operator block needs a usable name and domain, or it is unpublished."""

    def test_reads_name_and_domain(self) -> None:
        """A valid block yields the operator and its https URL."""
        operator = read_operator(
            {"operator": {"name": " Valory ", "domain": DOMAIN, "contact": "x@y"}}
        )
        assert operator == Operator(name="Valory", domain=DOMAIN)
        assert operator is not None and operator.url == f"https://{DOMAIN}"

    @pytest.mark.parametrize(
        "manifest",
        [
            {},
            {"operator": None},
            {"operator": "Valory"},
            {"operator": ["Valory", DOMAIN]},
            {"operator": {"name": "Valory"}},
            {"operator": {"domain": DOMAIN}},
            {"operator": {"name": "", "domain": DOMAIN}},
            {"operator": {"name": "Valory", "domain": "https://valory.xyz"}},
            {"operator": {"name": 1, "domain": DOMAIN}},
        ],
        ids=[
            "absent",
            "null",
            "string",
            "list",
            "no_domain",
            "no_name",
            "blank_name",
            "domain_with_scheme",
            "name_not_string",
        ],
    )
    def test_unusable_block_reads_as_unpublished(
        self, manifest: Dict[str, Any]
    ) -> None:
        """Anything short of a name and a bare domain is None."""
        assert read_operator(manifest) is None


class TestReadBenchmarks:
    """Each tool's benchmark is its https link, passed on as the operator's claim."""

    def test_reads_the_link_of_each_tool(self) -> None:
        """The link is kept; any metric, window or figure beside it is not reported."""
        manifest = {
            "toolMetadata": {
                "tool-a": {
                    "benchmark": {
                        "metric": "accuracy",
                        "value": 0.9,
                        "window": "30d",
                        "url": BENCHMARK_URL,
                    }
                },
                "tool-b": {"benchmark": {"url": f"  {BENCHMARK_URL}/b  "}},
            }
        }
        assert read_benchmarks(manifest) == {
            "tool-a": BENCHMARK_URL,
            "tool-b": f"{BENCHMARK_URL}/b",
        }

    @pytest.mark.parametrize(
        "manifest",
        [
            {},
            {"toolMetadata": None},
            {"toolMetadata": ["t"]},
            {"toolMetadata": {"t": None}},
            {"toolMetadata": {"t": {}}},
            {"toolMetadata": {"t": {"benchmark": BENCHMARK_URL}}},
            {"toolMetadata": {"t": {"benchmark": {}}}},
            {"toolMetadata": {"t": {"benchmark": {"url": "http://x.test"}}}},
            {"toolMetadata": {"t": {"benchmark": {"url": "https://"}}}},
            {"toolMetadata": {"t": {"benchmark": {"url": 7}}}},
            {"toolMetadata": {5: {"benchmark": {"url": BENCHMARK_URL}}}},
        ],
        ids=[
            "no_tool_metadata",
            "null_tool_metadata",
            "list_tool_metadata",
            "null_entry",
            "no_benchmark",
            "benchmark_is_a_bare_string",
            "no_url",
            "http_url",
            "scheme_only_url",
            "url_not_string",
            "tool_not_string",
        ],
    )
    def test_a_tool_without_an_https_link_is_left_out(
        self, manifest: Dict[str, Any]
    ) -> None:
        """No usable link means no entry for that tool."""
        assert read_benchmarks(manifest) == {}


class TestBaseUnits:
    """An amount is a positive decimal integer string; nothing else is read."""

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("1", 1),
            (f"  {EXPECTED_COST_WEI}  ", EXPECTED_COST_WEI),
            (str(UINT256_MAX), UINT256_MAX),
        ],
    )
    def test_reads_a_positive_decimal_string(self, value: str, expected: int) -> None:
        """Surrounding whitespace is stripped; the widest uint256 is accepted."""
        assert base_units(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            None,
            EXPECTED_COST_WEI,
            1.5,
            True,
            "",
            "   ",
            "0",
            "000",
            "-1",
            "+1",
            "1.0",
            "1e18",
            "0x10",
            "1_000",
            "１２",
            str(UINT256_MAX + 1),
            "1" * 79,
        ],
        ids=[
            "none",
            "json_number",
            "float",
            "bool",
            "empty",
            "blank",
            "zero",
            "zeros",
            "negative",
            "plus_sign",
            "decimal_point",
            "exponent",
            "hex",
            "underscore",
            "fullwidth_digits",
            "above_uint256",
            "too_many_digits",
        ],
    )
    def test_anything_else_is_not_an_amount(self, value: Any) -> None:
        """Numbers, signs, fractions, non-ASCII digits and values a contract cannot carry are refused."""
        assert base_units(value) is None


class TestReadExpectedCosts:
    """Each tool's expected cost is its asset and base-unit amount, as published."""

    def test_reads_the_asset_and_amount_of_each_tool(self) -> None:
        """The asset is lowercased; the amount is the decimal string as an integer."""
        manifest = {
            "toolMetadata": {
                "tool-a": {
                    "expectedCost": {"asset": "Native", "amount": str(EXPECTED_COST_WEI)}
                },
                "tool-b": {
                    "benchmark": {"url": BENCHMARK_URL},
                    "expectedCost": {"asset": " usdc ", "amount": " 25000 "},
                },
            }
        }
        assert read_expected_costs(manifest) == {
            "tool-a": ExpectedCost("native", EXPECTED_COST_WEI),
            "tool-b": ExpectedCost("usdc", 25000),
        }

    def test_a_tool_with_a_bad_entry_is_left_out_but_not_its_neighbours(self) -> None:
        """One unusable entry does not hide the usable ones."""
        manifest = {
            "toolMetadata": {
                "good": {"expectedCost": {"asset": "olas", "amount": "7"}},
                "bad": {"expectedCost": {"asset": "olas", "amount": 7}},
            }
        }
        assert read_expected_costs(manifest) == {"good": ExpectedCost("olas", 7)}

    @pytest.mark.parametrize(
        "manifest",
        [
            {},
            {"toolMetadata": None},
            {"toolMetadata": ["t"]},
            {"toolMetadata": {"t": None}},
            {"toolMetadata": {"t": {}}},
            {"toolMetadata": {"t": {"expectedCost": "12"}}},
            {"toolMetadata": {"t": {"expectedCost": {}}}},
            {"toolMetadata": {"t": {"expectedCost": {"amount": "12"}}}},
            {"toolMetadata": {"t": {"expectedCost": {"asset": "native"}}}},
            {"toolMetadata": {"t": {"expectedCost": {"asset": "", "amount": "12"}}}},
            {"toolMetadata": {"t": {"expectedCost": {"asset": 1, "amount": "12"}}}},
            {"toolMetadata": {"t": {"expectedCost": {"asset": "native", "amount": 12}}}},
            {"toolMetadata": {"t": {"expectedCost": {"asset": "native", "amount": "0"}}}},
            {"toolMetadata": {"t": {"expectedCost": {"asset": "native", "amount": "0.012"}}}},
            {"toolMetadata": {5: {"expectedCost": {"asset": "native", "amount": "12"}}}},
        ],
        ids=[
            "no_tool_metadata",
            "null_tool_metadata",
            "list_tool_metadata",
            "null_entry",
            "no_expected_cost",
            "expected_cost_is_a_bare_string",
            "empty_block",
            "no_asset",
            "no_amount",
            "blank_asset",
            "asset_not_string",
            "amount_is_a_number",
            "zero_amount",
            "fractional_amount",
            "tool_not_string",
        ],
    )
    def test_a_tool_without_a_usable_cost_is_left_out(
        self, manifest: Dict[str, Any]
    ) -> None:
        """No asset or no positive decimal-string amount means no entry for that tool."""
        assert read_expected_costs(manifest) == {}


class TestProofUrl:
    """The proof lives at the well-known path on the exact domain."""

    def test_builds_the_well_known_url(self) -> None:
        """The URL is https on the domain, at the ERC-8004 path."""
        assert proof_url(DOMAIN) == PROOF_URL


class TestFetchDomainProof:
    """Fetching the proof tells a verdict from an outage, and follows nothing."""

    def test_a_json_object_is_found(self) -> None:
        """A 2xx JSON object is the proof, fetched without following redirects."""
        proof = {"registrations": [_registration()]}
        with patch(f"{MODULE}.requests.get", return_value=_response(200, proof)) as get:
            outcome = fetch_domain_proof(DOMAIN)
        assert outcome.status is ProofStatus.FOUND
        assert outcome.proof == proof
        get.assert_called_once_with(
            PROOF_URL, timeout=PROOF_FETCH_TIMEOUT, allow_redirects=False, stream=True
        )

    def test_a_proof_at_the_size_cap_is_read_whole(self) -> None:
        """A body of exactly the cap, spread over chunks, is still parsed."""
        padding = PROOF_MAX_BYTES - len(json.dumps({"registrations": [], "pad": ""}))
        proof = {"registrations": [], "pad": "x" * padding}
        raw = json.dumps(proof).encode()
        assert len(raw) == PROOF_MAX_BYTES
        with patch(f"{MODULE}.requests.get", return_value=_response(200, raw=raw)):
            outcome = fetch_domain_proof(DOMAIN)
        assert outcome.status is ProofStatus.FOUND

    @pytest.mark.parametrize(
        "raw",
        [
            b"[" * 100_000,
            b"{" + b"x" * PROOF_MAX_BYTES,
            b'{"registrations": []}' + b" " * PROOF_MAX_BYTES,
        ],
        ids=["deeply_nested", "oversize_garbage", "oversize_valid"],
    )
    def test_a_body_over_the_cap_or_too_deep_is_not_a_proof(self, raw: bytes) -> None:
        """Reading stops at the cap, and a parse that would recurse is not a proof."""
        with (
            patch(f"{MODULE}.requests.get", return_value=_response(200, raw=raw)),
            patch(f"{MODULE}.logger"),
        ):
            outcome = fetch_domain_proof(DOMAIN)
        assert outcome.status is ProofStatus.NOT_FOUND

    @pytest.mark.parametrize(
        "error",
        [
            requests.ConnectionError("reset"),
            requests.exceptions.ChunkedEncodingError("cut"),
            requests.exceptions.ContentDecodingError("bad gzip"),
            requests.exceptions.ReadTimeout("slow"),
        ],
        ids=["connection", "chunked", "decode", "read_timeout"],
    )
    def test_a_read_that_breaks_midway_is_an_outage(self, error: Exception) -> None:
        """A transport failure while streaming the body is not a verdict."""
        response = _response(200, {})
        response.iter_content.side_effect = error
        with (
            patch(f"{MODULE}.requests.get", return_value=response),
            patch(f"{MODULE}.logger"),
        ):
            assert fetch_domain_proof(DOMAIN).status is ProofStatus.UNAVAILABLE

    @pytest.mark.parametrize(
        "response",
        [
            _response(404, {}),
            _response(403, {}),
            _response(200, bad_json=True),
            _response(200, [_registration()]),
            _response(200, "proof"),
            _response(200, None),
        ],
        ids=[
            "not_found",
            "forbidden",
            "not_json",
            "json_list",
            "json_string",
            "json_null",
        ],
    )
    def test_an_answer_without_a_proof_is_a_verdict(self, response: MagicMock) -> None:
        """A redirect, a 4xx, or a non-object body means no proof, not an outage."""
        with (
            patch(f"{MODULE}.requests.get", return_value=response),
            patch(f"{MODULE}.logger"),
        ):
            outcome = fetch_domain_proof(DOMAIN)
        assert outcome.status is ProofStatus.NOT_FOUND
        assert outcome.proof is None

    @pytest.mark.parametrize(
        "status_code",
        [301, 302, 307, 308],
        ids=["moved", "found", "temporary", "permanent"],
    )
    def test_a_redirect_is_its_own_verdict(self, status_code: int) -> None:
        """A 3xx is neither a proof nor an absence: the proof lives on another host."""
        response = _response(status_code, {"registrations": [_registration()]})
        with (
            patch(f"{MODULE}.requests.get", return_value=response),
            patch(f"{MODULE}.logger"),
        ):
            outcome = fetch_domain_proof(DOMAIN)
        assert outcome.status is ProofStatus.REDIRECTED
        assert outcome.proof is None
        response.iter_content.assert_not_called()

    @pytest.mark.parametrize(
        "status_code",
        [500, 502, 503],
        ids=["server_error", "bad_gateway", "unavailable"],
    )
    def test_a_server_error_is_an_outage(self, status_code: int) -> None:
        """A 5xx says nothing about the proof, and is logged as a warning."""
        with (
            patch(f"{MODULE}.requests.get", return_value=_response(status_code, {})),
            patch(f"{MODULE}.logger") as logger,
        ):
            outcome = fetch_domain_proof(DOMAIN)
        assert outcome.status is ProofStatus.UNAVAILABLE
        logger.warning.assert_called_once()

    @pytest.mark.parametrize(
        "error",
        [
            requests.Timeout("slow"),
            requests.ConnectionError("down"),
            requests.TooManyRedirects("loop"),
        ],
        ids=["timeout", "connection", "redirects"],
    )
    def test_a_transport_failure_is_an_outage(self, error: Exception) -> None:
        """A failed fetch says nothing about the proof, and is logged as a warning."""
        with (
            patch(f"{MODULE}.requests.get", side_effect=error),
            patch(f"{MODULE}.logger") as logger,
        ):
            outcome = fetch_domain_proof(DOMAIN)
        assert outcome.status is ProofStatus.UNAVAILABLE
        logger.warning.assert_called_once()


class TestProofMatches:
    """A proof matches on this chain's registry and this agent id, nothing less."""

    @pytest.mark.parametrize(
        "entry",
        [
            _registration(),
            _registration(agent_id=str(AGENT_ID)),
            {
                "agentRegistry": f"eip155:{GNOSIS}:{IDENTITY_REGISTRY.lower()}",
                "agentId": AGENT_ID,
            },
            {
                "agentRegistry": f"EIP155:{GNOSIS}:{IDENTITY_REGISTRY.upper()}",
                "agentId": AGENT_ID,
            },
        ],
        ids=["int_id", "digit_string_id", "lowercase_registry", "uppercase_registry"],
    )
    def test_matches_registry_case_insensitively_and_numeric_ids(
        self, entry: Dict[str, Any]
    ) -> None:
        """Registry case and the id's spelling do not matter; the values do."""
        proof = {"registrations": [_registration(agent_id=1), entry]}
        assert proof_matches(proof, GNOSIS, AGENT_ID) is True

    @pytest.mark.parametrize(
        "proof",
        [
            {},
            {"registrations": None},
            {"registrations": {}},
            {"registrations": []},
            {"registrations": [None]},
            {"registrations": ["eip155:100:x"]},
            {"registrations": [_registration(agent_id=AGENT_ID + 1)]},
            {"registrations": [_registration(chain_id=137)]},
            {"registrations": [_registration(agent_id=True)]},
            {"registrations": [_registration(agent_id=float(AGENT_ID))]},
            {"registrations": [_registration(agent_id=f"{AGENT_ID}x")]},
            {"registrations": [_registration(agent_id="²")]},
            {"registrations": [_registration(agent_id="١")]},
            {
                "registrations": [
                    _registration(agent_id="1" * (AGENT_ID_MAX_DIGITS + 1))
                ]
            },
            {"registrations": [_registration(agent_id=None)]},
            {"registrations": [{"agentId": AGENT_ID}]},
            {"registrations": [{"agentId": AGENT_ID, "agentRegistry": 5}]},
            {
                "registrations": [
                    {
                        "agentId": AGENT_ID,
                        "agentRegistry": f"eip155:{GNOSIS}:0x{'1' * 40}",
                    }
                ]
            },
        ],
        ids=[
            "no_registrations",
            "null_registrations",
            "dict_registrations",
            "empty",
            "null_entry",
            "string_entry",
            "other_agent",
            "other_chain",
            "bool_id",
            "float_id",
            "non_digit_id",
            "superscript_id",
            "arabic_indic_id",
            "overlong_id",
            "null_id",
            "no_registry",
            "registry_not_string",
            "other_registry",
        ],
    )
    def test_anything_else_does_not_match(self, proof: Dict[str, Any]) -> None:
        """A missing, mistyped or different entry is no match."""
        assert proof_matches(proof, GNOSIS, AGENT_ID) is False


class TestVerifyDomain:
    """The domain check fails closed, and says why."""

    def test_no_agent_id_is_unverified_without_a_fetch(self) -> None:
        """Without an identity there is nothing to match, so nothing is fetched."""
        with patch(f"{MODULE}.requests.get") as get:
            result = verify_domain(DOMAIN, GNOSIS, None)
        assert result == DomainVerification(False, NO_AGENT_ID_NOTE)
        get.assert_not_called()

    def test_a_matching_proof_verifies(self) -> None:
        """A fetched proof listing this chain and agent id verifies the domain."""
        proof = {"registrations": [_registration()]}
        with patch(f"{MODULE}.requests.get", return_value=_response(200, proof)):
            assert verify_domain(DOMAIN, GNOSIS, AGENT_ID) == DomainVerification(True)

    @pytest.mark.parametrize(
        ("get", "note"),
        [
            ({"side_effect": requests.ConnectionError("down")}, PROOF_UNAVAILABLE_NOTE),
            ({"return_value": _response(503, {})}, PROOF_UNAVAILABLE_NOTE),
            ({"return_value": _response(404, {})}, PROOF_NOT_FOUND_NOTE),
            ({"return_value": _response(308, {})}, PROOF_REDIRECTED_NOTE),
            (
                {
                    "return_value": _response(
                        200, {"registrations": [_registration(137)]}
                    )
                },
                PROOF_MISMATCH_NOTE,
            ),
            ({"return_value": _response(200, {})}, PROOF_MISMATCH_NOTE),
        ],
        ids=[
            "unreachable",
            "server_error",
            "missing",
            "redirect",
            "other_chain",
            "no_list",
        ],
    )
    def test_everything_short_of_a_match_is_unverified_with_the_reason(
        self, get: Dict[str, Any], note: str
    ) -> None:
        """Outage, absence and mismatch are each unverified, each with its own note."""
        with patch(f"{MODULE}.requests.get", **get), patch(f"{MODULE}.logger"):
            assert verify_domain(DOMAIN, GNOSIS, AGENT_ID) == DomainVerification(
                False, note
            )

    def test_an_outage_is_not_remembered(self) -> None:
        """The next call fetches again; nothing caches a failed proof as a no."""
        proof = {"registrations": [_registration()]}
        with (
            patch(
                f"{MODULE}.requests.get",
                side_effect=[requests.Timeout("slow"), _response(200, proof)],
            ) as get,
            patch(f"{MODULE}.logger"),
        ):
            first = verify_domain(DOMAIN, GNOSIS, AGENT_ID)
            second = verify_domain(DOMAIN, GNOSIS, AGENT_ID)
        assert first.verified is False
        assert second.verified is True
        assert get.call_count == 2
