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

"""The chat contract: messages in, completion and token usage out.

The prompt is an OpenAI-style ``messages`` list as JSON, and the delivery
carries the completion text plus token usage. A native tool call the model
returns unrequested comes back as a fenced bash block in the completion
rather than being dropped.
"""

import json
from typing import Callable, Dict, Optional, TypedDict, Union

from mech_client.domain.delivery.models import DeliveryResult
from mech_client.utils.types import JSONValue

TEXT_KEYS = ("content", "text", "completion")
WRAPPER_KEYS = ("response", "result")
USAGE_KEYS = ("prompt_tokens", "completion_tokens")


class ChatReport(TypedDict):
    """A chat delivery's completion, and the token usage the mech reported."""

    completion: str
    usage: Dict[str, int]


def is_chat_prompt(prompt: str) -> bool:
    """
    Whether a prompt is a chat: a non-empty JSON list of ``{role, ...}`` messages.

    Only ``role`` is required: an assistant message carrying ``tool_calls``
    may omit ``content``, as the OpenAI message format allows.

    :param prompt: The prompt string
    :return: True for a chat prompt
    """
    try:
        messages = json.loads(prompt)
    except (ValueError, RecursionError):  # deep nesting overflows the decoder
        return False
    return (
        isinstance(messages, list)
        and bool(messages)
        and all(isinstance(m, dict) and "role" in m for m in messages)
    )


def _parse(value: JSONValue) -> JSONValue:
    """Decode a JSON string, leaving anything else as it is.

    :param value: A delivery field
    :return: The decoded value, or the value itself
    """
    if isinstance(value, str):
        try:
            decoded: JSONValue = json.loads(value)
            return decoded
        except (ValueError, RecursionError):  # an untrusted delivery: any depth
            return value
    return value


def _with_choice(message: Dict[str, JSONValue]) -> Dict[str, JSONValue]:
    """Merge an OpenAI ``choices[0].message`` over the message, if there is one.

    :param message: The message holding the completion
    :return: The merged message, or the message itself
    """
    choices = message.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    inner = first.get("message") if isinstance(first, dict) else None
    if isinstance(inner, dict):  # an untrusted delivery: any shape
        return {**message, **inner}
    return message


def _completion(message: JSONValue) -> Optional[str]:
    """Read the completion out of a message, decoding nothing.

    :param message: The message: a string, or an object with ``choices``,
        ``content``/``text``/``completion`` or ``tool_calls``
    :return: The completion, or None when the message holds none
    """
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return None
    message = _with_choice(message)
    text = _text(message)
    calls = message.get("tool_calls")
    blocks = [_tool_call_block(c) for c in calls] if isinstance(calls, list) else []
    if text is None and not blocks:
        return None
    return "\n\n".join(([text] if text else []) + blocks)


def _delivery_completion(data: Dict[str, JSONValue]) -> Optional[str]:
    """Read the completion out of a delivery object, decoding nothing.

    :param data: The delivery: a ``response``/``result`` wrapper, or a message
    :return: The completion, or None when the delivery holds none
    """
    for key in WRAPPER_KEYS:
        if key in data:
            return _completion(data[key])
    return _completion(data)


def _decode(
    value: JSONValue, completion_of: Callable[[Dict[str, JSONValue]], Optional[str]]
) -> JSONValue:
    """Decode one level of a JSON string, only where it is the structure.

    A string decoding to a JSON string is that text. A string decoding to an
    object is replaced only when the object has the structure the parser
    reads at this level and yields a non-empty completion through it;
    anything else (a number, ``true``, a list, a model's own JSON answer) is
    the completion itself, so the string stays as is.

    :param value: A delivery field
    :param completion_of: Reads the completion out of an object at this level
    :return: The decoded string or object, or the value itself
    """
    decoded = _parse(value)
    if isinstance(decoded, str):
        return decoded
    if isinstance(decoded, dict) and completion_of(decoded):
        return decoded
    return value


def _message(data: JSONValue) -> JSONValue:
    """Descend to the message: decode the delivery, then response/result.

    :param data: The delivered content
    :return: The message holding the completion
    """
    data = _decode(data, _delivery_completion)
    if isinstance(data, dict):
        for key in WRAPPER_KEYS:
            if key in data:
                return _decode(data[key], _completion)
    return data


def _tool_call_block(call: JSONValue) -> str:
    """Render one native tool call as a fenced bash block.

    :param call: One entry of the message's ``tool_calls``
    :return: The fenced block
    """
    function = call.get("function") if isinstance(call, dict) else None
    function = function if isinstance(function, dict) else {}
    arguments = _parse(function.get("arguments", ""))
    if isinstance(arguments, dict) and isinstance(arguments.get("command"), str):
        body = str(arguments["command"])
    else:
        name = str(function.get("name") or "tool")
        rendered = arguments if isinstance(arguments, str) else json.dumps(arguments)
        body = f"{name} {rendered}"
    return f"```bash\n{body.strip()}\n```"


def _text(message: Dict[str, JSONValue]) -> Optional[str]:
    """Return the first string among the message's text keys.

    :param message: The message holding the completion
    :return: The text, or None
    """
    for key in TEXT_KEYS:
        value = message.get(key)
        if isinstance(value, str):
            return value
    return None


def _usage(raw: JSONValue) -> Dict[str, int]:
    """Read the integer token counts out of an untrusted usage block.

    :param raw: The message's ``usage``
    :return: Each count the mech reported as an integer (not a boolean)
    """
    usage = raw if isinstance(raw, dict) else {}
    counts: Dict[str, int] = {}
    for key in USAGE_KEYS:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            counts[key] = value
    return counts


def chat_report(delivery: Union[DeliveryResult, JSONValue]) -> Optional[ChatReport]:
    """
    Read the completion and usage out of a chat delivery.

    None means either that the delivery holds no completion or that it could
    not be fetched (``DeliveryResult.data`` is None); check ``delivery.data``
    first to tell the two apart.

    :param delivery: A :class:`DeliveryResult` from ``send_request``'s
        ``deliveries``, or its content
    :return: The report, or None (see above)
    """
    data = delivery.data if isinstance(delivery, DeliveryResult) else delivery
    message = _message(data)
    completion = _completion(message)
    if completion is None:
        return None
    usage = _with_choice(message).get("usage") if isinstance(message, dict) else None
    return {"completion": completion, "usage": _usage(usage)}
