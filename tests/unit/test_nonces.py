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

"""Tests for the off-chain marketplace nonce allocator."""

import json
import threading
from pathlib import Path
from typing import (
    Any,
    Callable,
    ContextManager,
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
    cast,
)

import pytest

from mech_client import nonces
from mech_client.nonces import (
    NonceAllocator,
    NonceRefused,
    Reservation,
    outcome_of,
    send_with_nonce,
)
from mech_client.services.marketplace_service import (
    MechPriceExceeded,
    OffchainRequestRejected,
    OffchainTopUpFailed,
    RequestIdMismatch,
)

SENDER = "0x" + "22" * 20
MECH_A = "0x" + "a1" * 20
MECH_B = "0x" + "b2" * 20
GAP_RETRIES = 3


class Clock:
    """A clock that only moves when slept on."""

    def __init__(self) -> None:
        """Start at 1000."""
        self.now = 1000.0
        self.slept: List[float] = []

    def __call__(self) -> float:
        """Return the time."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Advance the time."""
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def clock() -> Clock:
    """Return a fake clock."""
    return Clock()


def _allocator(tmp_path: Path, clock: Clock) -> NonceAllocator:
    """Return an allocator on the fake clock, with a 60 s settle timeout."""
    return NonceAllocator(
        tmp_path,
        settle_timeout=60,
        gap_retries=GAP_RETRIES,
        clock=clock,
        sleep=clock.sleep,
    )


@pytest.fixture
def allocator(tmp_path: Path, clock: Clock) -> NonceAllocator:
    """Return an allocator on the fake clock."""
    return _allocator(tmp_path, clock)


def held(allocator: NonceAllocator, nonce: int) -> Optional[Dict[str, Any]]:
    """Return the persisted slot for nonce on the test sender, or None."""
    path = allocator._path  # pylint: disable=protected-access
    queues = json.loads(path.read_text()) if path.exists() else {}
    return queues.get(f"gnosis:{SENDER}", {}).get("slots", {}).get(str(nonce))


def salt_of(allocator: NonceAllocator, nonce: int) -> Optional[str]:
    """Return the salt persisted with a held slot, or None if n is free."""
    slot = held(allocator, nonce)
    return None if slot is None else slot["salt"]


def _sync(allocator: NonceAllocator, map_nonces: int) -> None:
    """Re-read mapNonces for the test sender, as every reserve does."""
    key = allocator.key("gnosis", SENDER)
    # pylint: disable-next=protected-access
    allocator._sync(key, allocator._queue(key), map_nonces)


def reject(status: int, reason: str = "no", nonce: int = 0) -> OffchainRequestRejected:
    """Return mech-client's rejection for one HTTP answer."""
    return OffchainRequestRejected(
        f"HTTP {status}",
        request_id="01",
        nonce=nonce,
        status=status,
        reason=reason,
        unsent=[],
    )


def take(
    allocator: NonceAllocator, map_nonces: int, mech: str = MECH_A, timeout: float = 10
) -> ContextManager[Reservation]:
    """Return a reserve context with a fixed mapNonces."""
    return allocator.reserve(
        "gnosis", SENDER, mech, lambda: map_nonces, timeout=timeout
    )


def _enter(context: ContextManager) -> None:
    """Enter and leave a context, doing nothing inside."""
    with context:
        pass


def _crash_inside(context: ContextManager) -> None:
    """Raise inside a context, as a send that crashed would."""
    with context:
        raise RuntimeError("boom")


def test_nonces_follow_map_nonces_and_held_slots(allocator: NonceAllocator) -> None:
    """Allocate mapNonces + held slots; hold each until mapNonces passes it."""
    with take(allocator, 5) as slot:
        assert slot.nonce == 5
        slot.answered("accepted", mech=MECH_A, salt="s5")
    with take(allocator, 5) as slot:
        assert slot.nonce == 6  # 5 is held: unsettled, never reissued
        slot.answered("accepted", mech=MECH_A, salt="s6")
    assert salt_of(allocator, 6) == "s6"
    with take(allocator, 6) as slot:
        assert slot.nonce == 7  # 5 settled; 6 still held
        slot.answered("not_accepted", mech=MECH_A, salt="")
    with take(allocator, 6) as slot:
        assert slot.nonce == 7  # not accepted: reused
        slot.answered("accepted", mech=MECH_A, salt="")
    assert salt_of(allocator, 99) is None


def test_one_mech_in_flight_per_sender(allocator: NonceAllocator, clock: Clock) -> None:
    """A second mech waits for the first's slots to settle, then is refused."""
    with take(allocator, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="")
    with pytest.raises(NonceRefused) as refused:
        _enter(take(allocator, 5, MECH_B, timeout=5))
    assert refused.value.rule == "mech-in-flight"
    assert clock.slept  # it waited, re-reading mapNonces
    with take(allocator, 6, MECH_B) as slot:  # settled now
        assert slot.nonce == 6


def test_an_unanswered_reservation_is_held_as_unknown(
    allocator: NonceAllocator,
) -> None:
    """Leaving without an answer (a crash mid-send) never frees the nonce."""
    with pytest.raises(RuntimeError):
        _crash_inside(take(allocator, 5))
    with take(allocator, 5) as slot:
        assert slot.nonce == 6


def test_a_checksummed_mech_is_the_same_mech(allocator: NonceAllocator) -> None:
    """The mech's address in any case is one mech: its own slot never blocks it."""
    with take(allocator, 5, MECH_A.lower()) as slot:
        slot.answered("accepted", mech=MECH_A.lower(), salt="")
    with take(allocator, 5, MECH_A.upper().replace("0X", "0x"), timeout=0) as slot:
        assert slot.nonce == 6


def test_a_checksummed_sender_is_the_same_sender(allocator: NonceAllocator) -> None:
    """The sender's address in any case is one queue: its slots are counted once."""
    checksummed = "0x" + "aB" * 20
    with allocator.reserve("Gnosis", checksummed, MECH_A, lambda: 5, timeout=1) as slot:
        slot.answered("accepted", mech=MECH_A, salt="")
    with allocator.reserve(
        "gnosis", checksummed.lower(), MECH_A, lambda: 5, timeout=1
    ) as slot:
        assert slot.nonce == 6  # 5 is held by the same queue
    assert allocator.key("Gnosis", checksummed) == allocator.key(
        "gnosis", checksummed.lower()
    )


def _overdue_queue(allocator: NonceAllocator, clock: Clock) -> None:
    """Hold 5 (unknown) and 6 (accepted, delivered long ago), both overdue: stalled."""
    with take(allocator, 5) as slot:
        slot.answered("unknown", mech=MECH_A, salt="s5")
    with take(allocator, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="s6")
    allocator.delivered("gnosis", SENDER, [6])
    clock.now += nonces.RESPONSE_TIMEOUT_SECONDS + 61
    _sync(allocator, 5)
    assert allocator.stalled("gnosis", SENDER)


def test_an_accepted_probe_restarts_the_settle_clock_of_later_slots(
    allocator: NonceAllocator, clock: Clock
) -> None:
    """Unstuck at 5, the queue does not stall again on 6 and re-probe 5."""
    _overdue_queue(allocator, clock)
    with take(allocator, 5) as slot:
        assert slot.nonce == 5
        slot.answered("accepted", mech=MECH_A, salt="s5")
    assert cast(dict, held(allocator, 6))["delivered_at"] is None
    with take(allocator, 5) as slot:
        assert slot.nonce == 7
    assert not allocator.stalled("gnosis", SENDER)


def test_a_store_path_that_does_not_exist_is_created(
    tmp_path: Path, clock: Clock
) -> None:
    """A fresh store directory is created, and the first reserve is saved there."""
    allocator = _allocator(tmp_path / "a" / "b", clock)
    with take(allocator, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="")
    assert (tmp_path / "a" / "b" / nonces.NONCES_FILE).exists()


def test_a_store_path_that_cannot_be_created_is_unwritable(
    tmp_path: Path, clock: Clock
) -> None:
    """A path under a file cannot be created: requests are refused, nothing raises."""
    (tmp_path / "file").write_text("")
    allocator = _allocator(tmp_path / "file" / "store", clock)
    with pytest.raises(NonceRefused) as refused:
        _enter(take(allocator, 5))
    assert refused.value.rule == "mech-queue-unwritable"


def test_a_connect_format_slot_is_held(tmp_path: Path, clock: Clock) -> None:
    """A slot with only state, mech, salt and at, as Connect writes it, is read back."""
    (tmp_path / nonces.NONCES_FILE).write_text(
        json.dumps(
            {
                f"gnosis:{SENDER}": {
                    "stalled": False,
                    "slots": {
                        "5": {
                            "state": "accepted",
                            "mech": MECH_A,
                            "salt": "x",
                            "at": 1000,
                        }
                    },
                }
            }
        )
    )
    allocator = _allocator(tmp_path, clock)
    with take(allocator, 5) as slot:
        assert slot.nonce == 6


def test_reserve_rereads_map_nonces_while_another_mech_settles(
    allocator: NonceAllocator,
) -> None:
    """MECH_B waits for MECH_A's 5 to settle, then gets 6 within its timeout."""
    with take(allocator, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="")
    map_nonces = iter([5, 5, 6])
    with allocator.reserve(
        "gnosis", SENDER, MECH_B, lambda: next(map_nonces), timeout=30
    ) as slot:
        assert slot.nonce == 6
    assert held(allocator, 5) is None


def test_taken_resolves_our_unknown_or_stalls(
    allocator: NonceAllocator, clock: Clock
) -> None:
    """Taken on a probe over our own unknown slot unstalls; otherwise it stalls."""
    with take(allocator, 5) as slot:
        slot.answered("unknown", mech=MECH_A, salt="s5")
    assert allocator.stalled_since("gnosis", SENDER) is None
    with take(allocator, 5) as slot:
        assert slot.nonce == 6
        slot.answered("taken", mech=MECH_A, salt="")  # someone else holds 6
    assert allocator.stalled("gnosis", SENDER)
    assert allocator.stalled_since("gnosis", SENDER) == clock.now
    clock.now += 5
    with take(allocator, 5) as slot:
        assert slot.nonce == 5  # stalled: only the probe at mapNonces
        slot.answered("taken", mech=MECH_A, salt="")  # our own unknown 5
    assert held(allocator, 5) == {
        "state": "accepted",
        "mech": MECH_A,
        "salt": "s5",
        "at": clock.now,
        "delivered_at": None,
    }
    assert allocator.stalled_since("gnosis", SENDER) is None
    with take(allocator, 5) as slot:
        assert slot.nonce == 6  # resumed past 5


def test_taken_on_a_probe_over_our_accepted_slot_unstalls(
    allocator: NonceAllocator, clock: Clock
) -> None:
    """The mech holding our accepted slot proves n is not stuck: no re-probing it."""
    _overdue_queue(allocator, clock)
    with take(allocator, 5) as slot:
        slot.answered("taken", mech=MECH_A, salt="")  # over our unknown 5
    clock.now += nonces.RESPONSE_TIMEOUT_SECONDS + 61  # overdue again
    _sync(allocator, 5)
    assert allocator.stalled("gnosis", SENDER)
    with take(allocator, 5) as slot:
        assert slot.nonce == 5
        slot.answered("taken", mech=MECH_A, salt="")  # over our accepted 5
    assert not allocator.stalled("gnosis", SENDER)
    assert cast(dict, held(allocator, 6))["at"] == clock.now
    with take(allocator, 5) as slot:
        assert slot.nonce == 7


def test_an_overdue_slot_stalls_the_queue(
    allocator: NonceAllocator, clock: Clock
) -> None:
    """Timed out, then not settled within the settle timeout: stop sending.

    The settle clock starts when the request's own response timeout ends, or
    at its delivery if that came first: a mech still working within its time
    stalls nothing.
    """
    with take(allocator, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="")
    clock.now += nonces.RESPONSE_TIMEOUT_SECONDS
    _sync(allocator, 5)
    assert not allocator.stalled("gnosis", SENDER)  # still within the settle time
    clock.now += 61
    _sync(allocator, 5)
    assert allocator.stalled("gnosis", SENDER)
    assert allocator.stalled_since("gnosis", SENDER) == clock.now


def test_a_delivery_starts_the_settle_clock(
    tmp_path: Path, allocator: NonceAllocator, clock: Clock
) -> None:
    """Delivered, then not settled within the settle timeout: stop sending."""
    with take(allocator, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="")
    clock.now += 10
    allocator.delivered("gnosis", SENDER, [5, 9])  # 9 is not held: ignored
    assert cast(dict, held(allocator, 5))["delivered_at"] == clock.now
    clock.now += 50
    allocator.delivered("gnosis", SENDER, [5])  # a second sighting keeps the first
    allocator.delivered("gnosis", SENDER, [9])  # nothing held: nothing written
    clock.now += 11
    _sync(allocator, 5)
    assert allocator.stalled("gnosis", SENDER)
    restarted = _allocator(tmp_path, clock)
    queue = restarted._queue(  # pylint: disable=protected-access
        restarted.key("gnosis", SENDER)
    )
    assert queue.slots[5].delivered_at == 1010.0


def test_queues_survive_a_restart(tmp_path: Path, clock: Clock) -> None:
    """Held slots, salts and the stall are read back, so nothing is reissued."""
    first = _allocator(tmp_path, clock)
    with take(first, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="salt")
    second = _allocator(tmp_path, clock)
    assert salt_of(second, 5) == "salt"
    with take(second, 5) as slot:
        assert slot.nonce == 6


def test_an_unknown_slot_survives_a_restart_as_unknown(
    tmp_path: Path, clock: Clock
) -> None:
    """A lost answer stays unknown, so a later taken still recognises it as ours."""
    first = _allocator(tmp_path, clock)
    with take(first, 5) as slot:
        slot.answered("unknown", mech=MECH_A, salt="s")
    second = _allocator(tmp_path, clock)
    queue = second._queue(  # pylint: disable=protected-access
        second.key("gnosis", SENDER)
    )
    assert queue.slots[5].state == "unknown"


def test_an_unreadable_queue_file_refuses_every_request(
    tmp_path: Path, clock: Clock
) -> None:
    """Held nonces cannot be told from free ones: nothing is sent."""
    (tmp_path / nonces.NONCES_FILE).write_text("{not json")
    allocator = _allocator(tmp_path, clock)
    for context in (
        take(allocator, 5),
        allocator.exclusive("gnosis", SENDER, lambda: 5, timeout=1),
        allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=0),
    ):
        with pytest.raises(NonceRefused) as refused:
            _enter(context)
        assert refused.value.rule == "mech-queue-unreadable"
        assert "could not be read" in str(refused.value)


def test_on_chain_requests_wait_for_an_empty_queue(
    allocator: NonceAllocator, clock: Clock
) -> None:
    """An on-chain request takes mapNonces itself, so no slot may be held."""
    with allocator.exclusive("gnosis", SENDER, lambda: 5, timeout=1):
        pass
    with take(allocator, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="")
    start = clock.now
    with pytest.raises(NonceRefused, match="on-chain request must wait"):
        _enter(allocator.exclusive("gnosis", SENDER, lambda: 5, timeout=3))
    assert clock.now - start >= 3  # it waited out its timeout first
    map_nonces = iter([5, 5, 6])
    with allocator.exclusive("gnosis", SENDER, lambda: next(map_nonces), timeout=30):
        pass  # the slot settled during the wait
    assert held(allocator, 5) is None


def test_outcomes_follow_the_mechs_answers() -> None:
    """503 retries; the stale-nonce 401 is taken; 4xx not accepted; else unknown."""
    assert outcome_of(reject(503)) == "retry"
    assert outcome_of(reject(401, nonces.NONCE_TAKEN_REASON)) == "taken"
    assert outcome_of(reject(401, "bad signature")) == "not_accepted"
    assert outcome_of(reject(402)) == "not_accepted"
    deposited = OffchainRequestRejected(
        "x", request_id="01", nonce=0, status=402, reason="r", unsent=[], deposited=9
    )
    assert outcome_of(deposited) == "not_accepted"
    assert outcome_of(reject(400)) == "not_accepted"  # the bound
    assert outcome_of(reject(499)) == "not_accepted"
    assert outcome_of(reject(399)) == "unknown"
    assert outcome_of(reject(500)) == "unknown"
    top_up = OffchainTopUpFailed("cap", request_id="01", nonce=0, unsent=[])
    assert outcome_of(top_up) == "not_accepted"


class BeforeHook(NamedTuple):
    """An exception send_request raises before its pre-sign hook runs."""

    error: Exception


def _send(
    allocator: NonceAllocator, answers: List[Any], **kwargs: Any
) -> Tuple[List[int], Any]:
    """Run send_with_nonce once; ``send`` pops its answers in order.

    Every answer but a ``BeforeHook`` comes after the hook ran, as a POST's
    answer does.
    """
    sent: List[int] = []

    def send(nonce: int, hook: Callable[[bytes, int], None]) -> Any:
        sent.append(nonce)
        answer = answers.pop(0)
        if isinstance(answer, BeforeHook):
            raise answer.error
        hook(b"id", nonce)
        if isinstance(answer, Exception):
            raise answer
        return answer

    try:
        result = send_with_nonce(
            allocator,
            chain="gnosis",
            sender=SENDER,
            mech=MECH_A,
            salt="s",
            read_map_nonces=lambda: 5,
            send=send,
            not_sent=kwargs.get("not_sent", (KeyError,)),
            timeout=1,
            on_request_id=kwargs.get("on_request_id"),
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        return sent, e
    return sent, result


def test_send_with_nonce_retries_a_gap_then_succeeds(
    allocator: NonceAllocator, clock: Clock
) -> None:
    """A 503 resends the same nonce after a pause; a later 200 holds it."""
    sent, result = _send(allocator, [reject(503), {"ok": 1}])
    assert sent == [5, 5]
    assert result == {"ok": 1}
    assert salt_of(allocator, 5) == "s"
    assert clock.slept == [nonces.GAP_RETRY_SECONDS]


def test_send_with_nonce_refuses_a_persistent_gap(allocator: NonceAllocator) -> None:
    """After gap_retries resends the request is refused as mech-nonce-gap; n is free."""
    sent, error = _send(allocator, [reject(503)] * (GAP_RETRIES + 1))
    assert len(sent) == GAP_RETRIES + 1
    assert isinstance(error, NonceRefused)
    assert error.rule == "mech-nonce-gap"
    assert salt_of(allocator, 5) is None


@pytest.mark.parametrize(
    ("answer", "rule", "is_held", "detail"),
    [
        (
            reject(401, nonces.NONCE_TAKEN_REASON, 5),
            "mech-nonce-taken",
            False,
            "HTTP 401",
        ),
        (reject(402, "payment required", 5), "mech-request-rejected", False, "402"),
        (reject(500, "boom", 5), "mech-answer-unknown", True, "HTTP 500 (boom)"),
        (
            OffchainTopUpFailed("over the cap", request_id="01", nonce=5, unsent=[]),
            "mech-request-rejected",
            False,
            "top-up for nonce 5 failed: over the cap",
        ),
    ],
)
def test_send_with_nonce_names_each_rejection(
    allocator: NonceAllocator, answer: Exception, rule: str, is_held: bool, detail: str
) -> None:
    """Each answer names its rule, and holds the slot only when it may be stored."""
    _, error = _send(allocator, [answer])
    assert isinstance(error, NonceRefused)
    assert error.rule == rule
    assert detail in str(error)
    assert error.__cause__ is answer
    assert (salt_of(allocator, 5) is not None) is is_held


@pytest.mark.parametrize(
    "refusal",
    [
        KeyError("refused"),
        RequestIdMismatch("lying rpc", expected="aa", reported="bb", nonce=5),
        MechPriceExceeded("too much", price=2, max_price=1),
    ],
)
def test_send_with_nonce_frees_a_nonce_never_sent(
    allocator: NonceAllocator, refusal: Exception
) -> None:
    """Refused before signing (the caller's not_sent, or mech-client's own): n is free."""
    sent, error = _send(allocator, [refusal])
    assert error is refusal
    sent, _ = _send(allocator, [{"ok": 1}])
    assert sent == [5]  # the freed 5 was reused


@pytest.mark.parametrize(
    "error",
    [ValueError("Tool 'x' not available"), RuntimeError("rpc down")],
)
def test_send_with_nonce_frees_a_nonce_that_failed_before_the_hook(
    allocator: NonceAllocator, error: Exception
) -> None:
    """Any failure before the hook returned reached no mech, whatever not_sent says."""
    _, raised = _send(allocator, [BeforeHook(error)], not_sent=())
    assert raised is error
    assert held(allocator, 5) is None


def test_send_with_nonce_runs_the_callers_hook_and_frees_on_its_refusal(
    allocator: NonceAllocator,
) -> None:
    """The caller's hook sees the id; if it raises, nothing was signed."""
    seen: List[Tuple[bytes, int]] = []
    sent, result = _send(
        allocator, [{"ok": 1}], on_request_id=lambda *a: seen.append(a)
    )
    assert (sent, result, seen) == ([5], {"ok": 1}, [(b"id", 5)])

    def refuse(request_id: bytes, nonce: int) -> None:
        raise PermissionError("not this one")

    _, raised = _send(allocator, [{"ok": 1}], on_request_id=refuse, not_sent=())
    assert isinstance(raised, PermissionError)
    assert held(allocator, 6) is None


def test_send_with_nonce_warns_when_send_skips_the_hook(
    allocator: NonceAllocator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A send that never runs the hook still records the answer, but says so."""
    warnings: List[str] = []
    monkeypatch.setattr(
        nonces.logger, "warning", lambda msg, *args: warnings.append(msg % args)
    )
    result = send_with_nonce(
        allocator,
        chain="gnosis",
        sender=SENDER,
        mech=MECH_A,
        salt="s",
        read_map_nonces=lambda: 5,
        send=lambda nonce, hook: {"ok": nonce},  # type: ignore[arg-type,return-value]
        not_sent=(),
        timeout=1,
    )
    assert result == {"ok": 5}
    assert any("never ran the hook" in w for w in warnings)
    assert cast(dict, held(allocator, 5))["state"] == "accepted"


def test_send_with_nonce_holds_a_lost_answer(allocator: NonceAllocator) -> None:
    """A transport error after the POST may have reached the mech: n is held."""
    sent, error = _send(allocator, [ConnectionError("lost")])
    assert sent == [5]
    assert isinstance(error, ConnectionError)
    assert cast(dict, held(allocator, 5))["state"] == "unknown"
    with take(allocator, 5) as slot:
        assert slot.nonce == 6


def test_the_slot_is_on_disk_before_the_post(allocator: NonceAllocator) -> None:
    """A crash mid-send leaves n held: it was written down before sending."""
    with take(allocator, 5) as slot:
        assert cast(dict, held(allocator, 5))["state"] == "unknown"
        slot.answered("accepted", mech=MECH_A, salt="")
    assert cast(dict, held(allocator, 5))["state"] == "accepted"


def test_a_restart_keeps_the_stall_and_its_time(tmp_path: Path, clock: Clock) -> None:
    """A stalled queue is still stalled after a restart, since the same time."""
    first = _allocator(tmp_path, clock)
    with take(first, 5) as slot:
        slot.answered("taken", mech=MECH_A, salt="")
    stalled_at = clock.now
    clock.now += 100
    second = _allocator(tmp_path, clock)
    assert second.stalled_since("gnosis", SENDER) == stalled_at
    with take(second, 5) as slot:
        assert slot.nonce == 5


def test_a_stall_saved_without_its_time_counts_from_the_load(
    tmp_path: Path, clock: Clock
) -> None:
    """A store written before stalled_since existed restarts the stall clock."""
    (tmp_path / nonces.NONCES_FILE).write_text(
        json.dumps({f"gnosis:{SENDER}": {"stalled": True, "slots": {}}})
    )
    allocator = _allocator(tmp_path, clock)
    assert allocator.stalled_since("gnosis", SENDER) == clock.now


def test_the_settle_timeout_boundary_and_an_overdue_unknown(
    allocator: NonceAllocator, clock: Clock
) -> None:
    """Exactly at the timeout is not overdue; past it, accepted or unknown stalls."""
    with take(allocator, 5) as slot:
        slot.answered("unknown", mech=MECH_A, salt="")
    clock.now += nonces.RESPONSE_TIMEOUT_SECONDS + 60
    _sync(allocator, 5)
    assert not allocator.stalled("gnosis", SENDER)
    clock.now += 1
    _sync(allocator, 5)
    assert allocator.stalled("gnosis", SENDER)  # a lost POST stalls, not wedges


def test_a_rejected_probe_puts_back_what_it_replaced(allocator: NonceAllocator) -> None:
    """A stalled queue probes at mapNonces over a held slot; a refusal restores it."""
    with take(allocator, 5) as slot:
        slot.answered("accepted", mech=MECH_A, salt="kept")
    with take(allocator, 5) as slot:
        assert slot.nonce == 6
        slot.answered("taken", mech=MECH_A, salt="")
    with take(allocator, 5) as slot:
        assert slot.nonce == 5  # the probe, over our accepted 5
        slot.answered("not_accepted", mech=MECH_A, salt="")
    assert cast(dict, held(allocator, 5))["salt"] == "kept"
    with take(allocator, 5) as slot:
        slot.answered("retry", mech=MECH_A, salt="")  # resent under the placeholder
    assert cast(dict, held(allocator, 5))["state"] == "unknown"


def _hold_lock(allocator: NonceAllocator) -> Tuple[threading.Event, threading.Thread]:
    """Hold the test sender's queue lock in a thread until the event is set."""
    entered, release = threading.Event(), threading.Event()

    def hold() -> None:
        with take(allocator, 5) as slot:
            entered.set()
            release.wait(5)
            slot.answered("accepted", mech=MECH_A, salt="")

    worker = threading.Thread(target=hold)
    worker.start()
    entered.wait(5)
    return release, worker


def test_the_lock_wait_is_bounded(allocator: NonceAllocator) -> None:
    """A second request on the same sender waits for the lock, then is refused."""
    release, worker = _hold_lock(allocator)
    with pytest.raises(NonceRefused, match="still being sent"):
        _enter(take(allocator, 5, timeout=0.05))
    release.set()
    worker.join(5)


def test_an_unwritable_store_refuses_requests_not_answers(
    allocator: NonceAllocator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed write never fails an accepted request; it stops the next one."""
    real_write = Path.write_text
    writes: List[int] = []

    def full_after_one(self: Path, *args: Any, **kwargs: Any) -> int:
        writes.append(1)
        if len(writes) > 1:
            raise OSError(28, "No space left on device")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", full_after_one)
    with take(allocator, 5) as slot:  # the placeholder is on disk
        slot.answered("accepted", mech=MECH_A, salt="")  # does not raise
    for context in (
        take(allocator, 6),
        allocator.exclusive("gnosis", SENDER, lambda: 5, timeout=1),
        allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=0),
    ):
        with pytest.raises(NonceRefused) as refused:
            _enter(context)
        assert refused.value.rule == "mech-queue-unwritable"


def test_a_placeholder_that_cannot_be_saved_is_never_sent(
    allocator: NonceAllocator, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Held only in memory, n would be reissued after a restart: refuse first."""

    def full(*_args: Any, **_kwargs: Any) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "write_text", full)
    with pytest.raises(NonceRefused) as refused:  # before the body would run
        _enter(take(allocator, 5))
    assert refused.value.rule == "mech-queue-unwritable"
    queue = allocator._queue(  # pylint: disable=protected-access
        allocator.key("gnosis", SENDER)
    )
    assert queue.slots == {}


@pytest.mark.parametrize(
    "content",
    [
        "[1, 2]",
        '{"gnosis:0x": {"slots": {"5": {"state": "accepted"}}}}',
        '{"gnosis:0x": {"slots": {"5": {"state": "pending", "mech": "m",'
        ' "salt": "", "at": 1}}}}',
    ],
)
def test_a_wrong_shaped_queue_file_is_unreadable(
    tmp_path: Path, clock: Clock, content: str
) -> None:
    """Valid JSON in the wrong shape is as unreadable as broken JSON."""
    (tmp_path / nonces.NONCES_FILE).write_text(content)
    allocator = _allocator(tmp_path, clock)
    with pytest.raises(NonceRefused) as refused:
        _enter(take(allocator, 5))
    assert refused.value.rule == "mech-queue-unreadable"


@pytest.mark.parametrize("kwargs", [{"gap_retries": -1}, {"settle_timeout": -1}])
def test_negative_limits_are_refused(tmp_path: Path, kwargs: Dict[str, int]) -> None:
    """A negative gap_retries would never send; a negative settle timeout makes no sense."""
    with pytest.raises(ValueError, match="must not be negative"):
        NonceAllocator(tmp_path, **{"settle_timeout": 1, "gap_retries": 1, **kwargs})


def test_gap_retries_is_read_only(allocator: NonceAllocator) -> None:
    """It is fixed at construction, where it was checked."""
    assert allocator.gap_retries == GAP_RETRIES
    with pytest.raises(AttributeError):
        allocator.gap_retries = -1  # type: ignore[misc]


def test_a_refusal_reads_as_its_detail() -> None:
    """str() is the detail; rule and detail are kept apart."""
    refused = NonceRefused("mech-in-flight", "wait")
    assert (str(refused), refused.rule, refused.detail) == (
        "wait",
        "mech-in-flight",
        "wait",
    )


class TestHardCancel:
    """The last resort: consume a stuck mapNonces on-chain once stalled long enough."""

    @staticmethod
    def _stall(allocator: NonceAllocator) -> None:
        """Hold 5 (stuck) and 6 (accepted), then stall on a taken 7."""
        for nonce in (5, 6):
            with take(allocator, 5) as slot:
                assert slot.nonce == nonce
                slot.answered("accepted", mech=MECH_A, salt=f"s{nonce}")
        with take(allocator, 5) as slot:
            slot.answered("taken", mech=MECH_A, salt="")

    def test_a_queue_that_is_not_stalled_is_refused(
        self, allocator: NonceAllocator
    ) -> None:
        """Nothing to recover: refused without yielding."""
        with pytest.raises(NonceRefused) as refused:
            _enter(allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=0))
        assert refused.value.rule == "mech-queue-not-stalled"
        assert "is not stalled" in str(refused.value)

    def test_a_stall_younger_than_the_threshold_is_refused(
        self, allocator: NonceAllocator, clock: Clock
    ) -> None:
        """Stalled, but not for long enough yet."""
        self._stall(allocator)
        clock.now += 599
        with pytest.raises(NonceRefused) as refused:
            _enter(allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=600))
        assert refused.value.rule == "mech-queue-not-stalled"
        assert "stalled for 599s" in str(refused.value)

    def test_a_probe_taken_again_keeps_the_stall_clock(
        self, allocator: NonceAllocator, clock: Clock
    ) -> None:
        """Probes another signer keeps taking do not restart the hard-cancel wait."""
        with take(allocator, 5) as slot:
            slot.answered("taken", mech=MECH_A, salt="")  # not ours
        stalled_at = clock.now
        clock.now += 300
        with take(allocator, 5) as slot:
            assert slot.nonce == 5
            slot.answered("taken", mech=MECH_A, salt="")
        assert allocator.stalled_since("gnosis", SENDER) == stalled_at
        assert held(allocator, 5) is None

    def test_it_yields_map_nonces_and_the_next_sync_frees_only_that_slot(
        self, allocator: NonceAllocator, clock: Clock
    ) -> None:
        """n = mapNonces is consumed; later accepted slots stay held."""
        self._stall(allocator)
        clock.now += 600
        with allocator.hard_cancel(
            "gnosis", SENDER, lambda: 5, stalled_for=600
        ) as nonce:
            assert nonce == 5
        # the on-chain request moved mapNonces past 5
        with take(allocator, 6) as slot:
            assert slot.nonce == 6  # still stalled: the probe at mapNonces
            # the mech already holds our 6, so it answers as the deployed one does
            slot.answered("taken", mech=MECH_A, salt="")
        assert held(allocator, 5) is None
        assert salt_of(allocator, 6) == "s6"
        assert not allocator.stalled("gnosis", SENDER)

    def test_each_cancel_needs_its_own_stall_window(
        self, allocator: NonceAllocator, clock: Clock
    ) -> None:
        """A second cancel straight after the first is refused, then allowed later."""
        self._stall(allocator)
        clock.now += 600
        with allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=600):
            clock.now += 30  # the on-chain request takes a while
        assert allocator.stalled_since("gnosis", SENDER) == clock.now
        with pytest.raises(NonceRefused) as refused:
            _enter(allocator.hard_cancel("gnosis", SENDER, lambda: 6, stalled_for=600))
        assert refused.value.rule == "mech-queue-not-stalled"
        clock.now += 600
        with allocator.hard_cancel(
            "gnosis", SENDER, lambda: 6, stalled_for=600
        ) as nonce:
            assert nonce == 6

    def test_a_failed_cancel_also_restarts_the_window(
        self, tmp_path: Path, allocator: NonceAllocator, clock: Clock
    ) -> None:
        """The on-chain request may have landed even if the body raised."""
        self._stall(allocator)
        clock.now += 600
        with pytest.raises(RuntimeError):
            _crash_inside(
                allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=600)
            )
        assert allocator.stalled_since("gnosis", SENDER) == clock.now
        assert _allocator(tmp_path, clock).stalled_since("gnosis", SENDER) == clock.now

    def test_it_restarts_the_settle_clock_of_later_slots(
        self, allocator: NonceAllocator, clock: Clock
    ) -> None:
        """After consuming 5 on-chain, 6 is not overdue at once."""
        _overdue_queue(allocator, clock)
        with allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=0):
            pass
        _sync(allocator, 6)  # the on-chain request moved mapNonces past 5
        assert held(allocator, 5) is None
        assert cast(dict, held(allocator, 6))["at"] == clock.now
        assert cast(dict, held(allocator, 6))["delivered_at"] is None
        with take(allocator, 6) as slot:  # still stalled from the cancel: probe 6
            assert slot.nonce == 6
            slot.answered("taken", mech=MECH_A, salt="")  # the mech holds our 6
        with take(allocator, 6) as slot:
            assert slot.nonce == 7

    def test_it_holds_the_queue_while_the_on_chain_request_is_sent(
        self, allocator: NonceAllocator, clock: Clock
    ) -> None:
        """No off-chain request goes out meanwhile, and a send in flight refuses it."""
        self._stall(allocator)
        clock.now += 600
        with allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=600):
            with pytest.raises(NonceRefused, match="still being sent"):
                _enter(take(allocator, 5, timeout=0))
        release, worker = _hold_lock(allocator)
        with pytest.raises(NonceRefused) as refused:
            _enter(allocator.hard_cancel("gnosis", SENDER, lambda: 5, stalled_for=0))
        assert refused.value.rule == "mech-in-flight"
        release.set()
        worker.join(5)
