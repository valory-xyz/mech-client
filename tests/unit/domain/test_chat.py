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

"""Tests for the chat contract."""

import json
from typing import Any, Dict

import pytest

from mech_client.domain.delivery import DeliveryResult
from mech_client.domain.delivery import chat as chat_module
from mech_client.domain.delivery.chat import chat_report, is_chat_prompt


def test_a_chat_prompt_is_a_json_list_of_messages() -> None:
    """Only a non-empty list of {role, ...} messages is a chat."""
    assert is_chat_prompt(json.dumps([{"role": "user", "content": "hi"}]))
    assert not is_chat_prompt("Will it rain?")
    assert not is_chat_prompt("[]")
    assert not is_chat_prompt(json.dumps([{"content": "no role"}]))
    assert not is_chat_prompt(json.dumps({"role": "user"}))


def test_the_completion_is_found_in_parse_order() -> None:
    """The delivery itself, response/result, then content/text/completion."""
    assert chat_report("plain words") == {"completion": "plain words", "usage": {}}
    assert chat_report({"text": "a"}) == {"completion": "a", "usage": {}}
    assert chat_report({"response": {"completion": "b"}}) == {
        "completion": "b",
        "usage": {},
    }
    nested = {
        "result": json.dumps(
            {
                "choices": [{"message": {"content": "c"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2, "x": "y"},
            }
        )
    }
    assert chat_report(nested) == {
        "completion": "c",
        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
    }
    assert chat_report(json.dumps({"result": "d"})) == {"completion": "d", "usage": {}}


@pytest.mark.parametrize(
    ("delivery", "completion"),
    [
        ({"content": "c", "text": "t", "completion": "x"}, "c"),
        ({"text": "t", "completion": "x"}, "t"),
        ({"content": 1, "text": "t"}, "t"),  # only a string counts
        ({"response": {"text": "r"}, "result": {"text": "s"}}, "r"),
        ({"result": {"text": "s"}, "response": {"text": "r"}}, "r"),
    ],
)
def test_the_first_candidate_in_parse_order_wins(
    delivery: Any, completion: str
) -> None:
    """content beats text beats completion, and response beats result."""
    report = chat_report(delivery)
    assert report is not None
    assert report["completion"] == completion


@pytest.mark.parametrize("text", ["42", "true", "null", '["a"]', '{"answer": 42}'])
def test_a_completion_that_is_valid_json_is_still_the_completion(text: str) -> None:
    """A model asked for a number answers "42": that text is the completion."""
    assert chat_report({"result": text}) == {"completion": text, "usage": {}}
    assert chat_report(text) == {"completion": text, "usage": {}}


@pytest.mark.parametrize(
    ("usage", "expected"),
    [
        ({"prompt_tokens": "n/a", "completion_tokens": None}, {}),
        ({"prompt_tokens": 4}, {"prompt_tokens": 4}),
        ({"prompt_tokens": True, "completion_tokens": 2}, {"completion_tokens": 2}),
        ([4, 2], {}),
    ],
)
def test_usage_takes_only_integer_counts(usage: Any, expected: Dict[str, int]) -> None:
    """An untrusted usage block never raises; only integer counts are reported."""
    report = chat_report({"content": "c", "usage": usage})
    assert report == {"completion": "c", "usage": expected}


def test_an_empty_content_beside_a_tool_call_adds_no_blank_lead() -> None:
    """The completion is the tool-call block alone."""
    report = chat_report({"content": "", "tool_calls": [{"function": {"name": "t"}}]})
    assert report == {"completion": "```bash\nt\n```", "usage": {}}


BLOCK = "```bash\nt\n```"
# per delivery key: an object using it that yields a completion, and one that does not
YIELDING = {
    "response": ({"response": "r"}, "r"),
    "result": ({"result": "r"}, "r"),
    "content": ({"content": "r"}, "r"),
    "text": ({"text": "r"}, "r"),
    "completion": ({"completion": "r"}, "r"),
    "tool_calls": ({"tool_calls": [{"function": {"name": "t"}}]}, BLOCK),
    "choices": ({"choices": [{"message": {"content": "r"}}]}, "r"),
}
NOT_YIELDING = {
    "response": {"response": 5},
    "result": {"result": None},
    "content": {"content": 1},
    "text": {"text": []},
    "completion": {"completion": {}},
    "tool_calls": {"tool_calls": "x"},
    "choices": {"choices": []},
}
MESSAGE_KEYS = ["content", "text", "completion", "tool_calls", "choices"]


@pytest.mark.parametrize("key", list(YIELDING))
def test_a_delivery_string_with_each_key_is_decoded_when_it_yields(key: str) -> None:
    """A whole delivery sent as a JSON string is read through its structure."""
    obj, completion = YIELDING[key]
    assert chat_report(json.dumps(obj)) == {"completion": completion, "usage": {}}


@pytest.mark.parametrize("key", list(NOT_YIELDING))
def test_a_delivery_string_with_each_key_stays_text_when_it_does_not(key: str) -> None:
    """Without a completion through the structure, the string is the completion."""
    text = json.dumps(NOT_YIELDING[key])
    assert chat_report(text) == {"completion": text, "usage": {}}


@pytest.mark.parametrize("key", MESSAGE_KEYS)
def test_a_result_string_with_each_message_key_is_decoded_when_it_yields(
    key: str,
) -> None:
    """A result JSON-encoded as a string is read as the message it holds."""
    obj, completion = YIELDING[key]
    report = chat_report({"result": json.dumps(obj)})
    assert report == {"completion": completion, "usage": {}}


@pytest.mark.parametrize(
    "obj",
    [NOT_YIELDING[key] for key in MESSAGE_KEYS]
    + [{"result": "yes"}, {"response": "yes"}, {"answer": 42}],
)
def test_a_result_string_that_is_not_a_message_is_the_completion(obj: Any) -> None:
    """One level only: a model's own JSON answer, wrapper keys included, is kept."""
    text = json.dumps(obj)
    assert chat_report({"result": text}) == {"completion": text, "usage": {}}


def test_a_json_string_literal_is_its_text() -> None:
    """A result JSON-encoded as a string, as mechs usually send it, is decoded."""
    assert chat_report({"result": '"hi"'}) == {"completion": "hi", "usage": {}}


def test_only_role_is_required_of_every_message() -> None:
    """An assistant tool-call message may omit content; every message needs a role."""
    tool_call = {"role": "assistant", "tool_calls": [{"function": {"name": "t"}}]}
    assert is_chat_prompt(json.dumps([{"role": "user", "content": "hi"}, tool_call]))
    assert not is_chat_prompt(json.dumps([{"role": "user"}, {"content": "no role"}]))


def test_a_delivery_result_is_read_through_its_data() -> None:
    """send_request's deliveries values are accepted as they come."""
    delivery = DeliveryResult("ab", data={"result": "e"}, url=None)
    assert chat_report(delivery) == {"completion": "e", "usage": {}}
    assert chat_report(DeliveryResult("ab")) is None  # unreadable gateway


def test_an_unrequested_tool_call_comes_back_as_a_bash_block() -> None:
    """Not dropped: the command, or the call itself, in a fenced bash block."""
    report = chat_report(
        {
            "content": "Running it",
            "tool_calls": [
                {
                    "function": {
                        "name": "bash",
                        "arguments": json.dumps({"command": " ls "}),
                    }
                },
                {"function": {"name": "search", "arguments": {"q": "x"}}},
                {"function": {"name": "raw", "arguments": "--flag"}},
                "not a call",
            ],
        }
    )
    assert report is not None
    assert report["completion"] == (
        'Running it\n\n```bash\nls\n```\n\n```bash\nsearch {"q": "x"}\n```'
        "\n\n```bash\nraw --flag\n```\n\n```bash\ntool\n```"
    )
    only_call = chat_report(
        {"choices": [{"message": {"tool_calls": [{"function": {"name": "t"}}]}}]}
    )
    assert only_call == {"completion": "```bash\nt\n```", "usage": {}}


def test_a_delivery_without_a_completion_is_not_a_chat_report() -> None:
    """Nothing to report rather than a guess."""
    assert chat_report({"answer": "42"}) is None
    assert chat_report([1, 2]) is None
    assert chat_report({"choices": []}) is None


def test_a_malformed_choice_from_an_untrusted_delivery_is_no_crash() -> None:
    """A delivery is the mech's to shape: a string message or choice reports nothing."""
    assert chat_report({"choices": [{"message": "hi"}]}) is None
    assert chat_report({"choices": ["hi"]}) is None


def test_a_decoder_overflow_is_no_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A delivery deep enough to overflow json.loads reads as text, never raised.

    How deep that is depends on the interpreter, so the overflow is raised
    directly rather than built.
    """

    def overflow(_text: str) -> Any:
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(chat_module.json, "loads", overflow)
    assert is_chat_prompt("[[[]]]") is False
    report = chat_report({"result": "[[[]]]"})
    assert report is not None
    assert report["completion"] == "[[[]]]"  # undecodable text is the completion
