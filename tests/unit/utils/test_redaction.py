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

"""Tests for mech_client.utils.redaction."""

import pytest

from mech_client.utils.redaction import redacted, redacted_cause


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "403 for url: https://rpc.example/v3/SECRET?x=1",
            "403 for url: https://rpc.example/...",
        ),
        ("at https://user:SECRET@rpc.example/x", "at https://rpc.example/..."),
        ("with url: /v2/SECRET (Caused by", "with url: /... (Caused by"),
        ("bad query ?apikey=SECRET here", "bad query ?... here"),
        ("connection refused", "connection refused"),
    ],
)
def test_redacted_cuts_every_secret_bearing_token(text: str, expected: str) -> None:
    """A URL keeps its scheme and host; any other path or query is cut."""
    assert redacted(text) == expected


def test_redacted_caps_the_length_unless_told_not_to() -> None:
    """A cause is short by default; ``limit=None`` keeps the whole message."""
    long = "x" * 300
    assert redacted(long) == "x" * 200 + "..."
    assert redacted(long, limit=None) == long


def test_redacted_cause_names_the_type() -> None:
    """The type survives; the secret does not."""
    error = ConnectionError("https://rpc.example/v3/SECRET")
    assert redacted_cause(error) == "ConnectionError: https://rpc.example/..."
