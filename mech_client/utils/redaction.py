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

"""Redaction of exception text that may carry RPC keys or credentials."""

import re
from typing import Optional

# An exception's text may carry an API key or credentials wherever a URL or a
# path appears: requests puts the full URL there, urllib3 the bare path
# ("... with url: /v3/<KEY>?..."). Fail closed: a URL keeps only its scheme
# and host, and any other path-like or query-like token is cut at its first
# "/" or "?".
_SECRET_BEARING = re.compile(
    r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)(?:[^\s/@'\"]*@)?"
    r"(?P<host>[^\s/'\"?#]*)[^\s'\"]*"
    r"|(?P<cut>[/?])[^\s'\"]*"
)
# a cause is a short description, not a dump of the exception
_CAUSE_MAX_LENGTH = 200


def _redact(match: "re.Match[str]") -> str:
    """Replace one URL-, path- or query-like token by what is safe to keep.

    :param match: The token
    :return: ``scheme://host/...`` for a URL, else ``/...`` or ``?...``
    """
    if match.group("scheme"):
        return f"{match.group('scheme')}{match.group('host')}/..."
    return f"{match.group('cut')}..."


def redacted_cause(error: BaseException) -> str:
    """
    Describe a failure without the secrets its text may carry.

    :param error: The exception
    :return: Its type and its message, redacted
    """
    return f"{type(error).__name__}: {redacted(str(error))}"


def redacted(text: str, limit: Optional[int] = _CAUSE_MAX_LENGTH) -> str:
    """
    Cut a message down to what is safe to pass on.

    :param text: The message
    :param limit: The most characters kept, or None to keep the length
    :return: It with every secret-bearing token cut
    """
    message = _SECRET_BEARING.sub(_redact, text)
    if limit is not None and len(message) > limit:
        message = message[:limit] + "..."
    return message
