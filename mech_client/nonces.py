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

"""Off-chain marketplace nonce allocator: one queue per sender and chain.

The marketplace's ``mapNonces(sender)`` only moves when a delivery settles, so
two off-chain requests from one sender would both sign it. The deployed mech
admits only ``nonce == mapNonces + accepted + settling`` (503 on a gap, 401 on
a stale or duplicate nonce), and settlement rebuilds every id from
``mapNonces``. A payer therefore allocates nonces itself and hands each to
``MarketplaceService.send_request(nonces=[n])``:

- one mech is in flight per sender and chain: a request to another mech waits
  until the first mech's slots settle, and is refused as ``mech-in-flight``
  when its wait runs out;
- the queue's lock is held from ``reserve`` until the mech answers, so POSTs
  go out in nonce order and at most one slot is ever reserved but unanswered;
- a slot is held until ``mapNonces > n`` (settlement), never on a timer;
- every held slot, its metadata salt and the stall are persisted in a JSON
  file under the caller's ``store_path``, written before the POST, so a
  restart never reissues a held nonce.
"""

import contextlib
import functools
import json
import logging
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    IO,
    Iterable,
    Iterator,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
)

from mech_client.services.marketplace_service import (
    HTTP_CLIENT_ERRORS,
    HTTP_UNAUTHORIZED,
    OffchainRequestRejected,
    OffchainRequestResult,
    OffchainTopUpFailed,
    PreSignHook,
    RESPONSE_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

NONCES_FILE = "mech_nonces.json"
# how often a waiting reserve re-reads mapNonces
POLL_SECONDS = 2.0
# a 503 is a nonce gap behind a slot still settling: resend the same nonce
# and id this far apart, up to the allocator's gap_retries times
GAP_RETRY_SECONDS = 2.0
# the mech's 401 for a stale or duplicate nonce, verbatim: n is taken
NONCE_TAKEN_REASON = "wire nonce below sender's next expected slot"
_HOOK_NOT_PASSED = (
    "send for nonce %s never passed send_with_nonce's hook to send_request as "
    "on_request_id; a failure is held as unknown"
)

Outcome = Literal["accepted", "retry", "not_accepted", "taken", "unknown"]
# what a held slot can be: the only outcomes that keep a nonce held
SlotState = Literal["accepted", "unknown"]
ACCEPTED: Literal["accepted"] = "accepted"
RETRY: Outcome = "retry"
NOT_ACCEPTED: Outcome = "not_accepted"
TAKEN: Outcome = "taken"
UNKNOWN: Literal["unknown"] = "unknown"
SLOT_STATES = (ACCEPTED, UNKNOWN)

NonceRule = Literal[
    "mech-in-flight",
    "mech-nonce-gap",
    "mech-nonce-taken",
    "mech-request-rejected",
    "mech-answer-unknown",
    "mech-queue-unreadable",
    "mech-queue-unwritable",
    "mech-queue-not-stalled",
    "mech-queue-locked",
]
RULE_IN_FLIGHT: NonceRule = "mech-in-flight"
RULE_NONCE_GAP: NonceRule = "mech-nonce-gap"
RULE_NONCE_TAKEN: NonceRule = "mech-nonce-taken"
RULE_REQUEST_REJECTED: NonceRule = "mech-request-rejected"
RULE_ANSWER_UNKNOWN: NonceRule = "mech-answer-unknown"
RULE_QUEUE_UNREADABLE: NonceRule = "mech-queue-unreadable"
RULE_QUEUE_UNWRITABLE: NonceRule = "mech-queue-unwritable"
RULE_QUEUE_NOT_STALLED: NonceRule = "mech-queue-not-stalled"
RULE_QUEUE_LOCKED: NonceRule = "mech-queue-locked"
REJECTION_RULES: Dict[Outcome, NonceRule] = {
    RETRY: RULE_NONCE_GAP,
    TAKEN: RULE_NONCE_TAKEN,
    NOT_ACCEPTED: RULE_REQUEST_REJECTED,
    UNKNOWN: RULE_ANSWER_UNKNOWN,
}
LOCK_FILE = "mech_nonces.lock"

# One allocator per store: an advisory, non-blocking lock on LOCK_FILE, which
# the operating system drops when the holder's file is closed or it exits.
if sys.platform == "win32":  # pragma: no cover - the branch for this platform runs
    import msvcrt  # pylint: disable=import-error  # Windows-only, imported only there

    def _lock_file(handle: IO[str]) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

else:  # pragma: no cover - the branch for this platform runs
    import fcntl

    def _lock_file(handle: IO[str]) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


class NonceRefused(Exception):
    """The allocator will not hand out a nonce now; ``rule`` names why."""

    def __init__(self, rule: NonceRule, detail: str) -> None:
        """
        Initialize the refusal.

        :param rule: The rule that refused, one of the ``RULE_*`` constants
        :param detail: Human-readable explanation
        """
        super().__init__(rule, detail)
        self.rule = rule
        self.detail = detail

    def __str__(self) -> str:
        """Return the refusal a caller reads.

        :return: The detail
        """
        return self.detail


@dataclass
class _Slot:
    """One held nonce: who it was sent to, its salt, and what the mech said."""

    state: SlotState
    mech: str
    salt: str
    at: float
    delivered_at: Optional[float] = None

    def settle_from(self) -> float:
        """Return when mapNonces should start to pass this slot.

        :return: Its delivery time, else the end of the mech's response timeout
        """
        if self.delivered_at is not None:
            return self.delivered_at
        # past the responseTimeout every request carries, the mech is out of
        # time by the request's own terms, so its delivery timed out
        return self.at + RESPONSE_TIMEOUT_SECONDS


@dataclass
class _Queue:
    """One sender's nonces on one chain."""

    lock: threading.Lock = field(default_factory=threading.Lock)
    slots: Dict[int, _Slot] = field(default_factory=dict)
    stalled_at: Optional[float] = None

    @property
    def stalled(self) -> bool:
        """Whether the queue only probes at mapNonces until one is accepted."""
        return self.stalled_at is not None


class Reservation:
    """A nonce reserved under the queue's lock, until the mech answers."""

    def __init__(
        self,
        nonce: int,
        prior: Optional[_Slot],
        record: Callable[..., None],
    ) -> None:
        """
        Initialize the reservation.

        :param nonce: The reserved nonce
        :param prior: What held this nonce before (only a stalled queue's probe)
        :param record: Applies an answer to the queue; the allocator binds it
        """
        self._record = record
        self._nonce = nonce
        self._prior = prior
        self._outcome: Optional[Outcome] = None

    @property
    def nonce(self) -> int:
        """The reserved nonce."""
        return self._nonce

    @property
    def prior(self) -> Optional[_Slot]:
        """What held this nonce before (only a stalled queue's probe)."""
        return self._prior

    @property
    def outcome(self) -> Optional[Outcome]:
        """The recorded answer, or None until ``answered`` is called."""
        return self._outcome

    def answered(self, outcome: Outcome, *, mech: str, salt: str) -> None:
        """
        Record the mech's answer to this nonce; a reservation is answered once.

        :param outcome: What the answer means for the nonce
        :param mech: The mech the request went to
        :param salt: The request's metadata salt, kept so a resend reuses its id
        :raises RuntimeError: If it was already answered
        """
        if self._outcome is not None:
            raise RuntimeError(
                f"nonce {self._nonce} was already answered {self._outcome!r}"
            )
        self._outcome = outcome
        self._record(self._nonce, outcome, mech=mech, salt=salt, prior=self._prior)


# too-many-instance-attributes: the store's path, locks and failure flags and
# the injected clock and sleep are all state of the one allocator
class NonceAllocator:  # pylint: disable=too-many-instance-attributes
    """Allocates off-chain marketplace nonces, one queue per (chain, sender)."""

    def __init__(
        self,
        store_path: Path,
        *,
        settle_timeout: float,
        gap_retries: int,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """
        Lock ``store_path`` for this allocator and load its persisted queues.

        Only one allocator may use a store at a time, across processes too:
        two would each hand out the same next nonce and overwrite each
        other's held slots. Call ``close`` to release the store.

        :param store_path: Directory holding the queue file (``mech_nonces.json``);
            created if missing, and the store is unwritable if that fails
        :param settle_timeout: Seconds a delivered or timed-out slot may stay
            unsettled before its queue stalls
        :param gap_retries: How many times a 503 resends the same nonce
        :param clock: Time source, in seconds
        :param sleep: Blocking sleep, in seconds
        :raises ValueError: If settle_timeout or gap_retries is negative
        :raises NonceRefused: ``mech-queue-locked`` if another allocator holds
            the store
        """
        if settle_timeout < 0 or gap_retries < 0:
            raise ValueError(
                f"settle_timeout ({settle_timeout}) and gap_retries "
                f"({gap_retries}) must not be negative"
            )
        self._path = Path(store_path) / NONCES_FILE
        self._settle_timeout = settle_timeout
        self._gap_retries = gap_retries
        self._clock = clock
        self.sleep = sleep
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._queues: Dict[str, _Queue] = {}
        self._broken = False
        self._unwritable = False
        self._lock_handle: Optional[IO[str]] = None
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._lock_handle = (
                open(  # pylint: disable=consider-using-with  # held until close()
                    self._path.parent / LOCK_FILE, "a+", encoding="utf-8"
                )
            )
        except OSError as e:
            logger.error(
                "could not open %s (%s); mech requests refused", self._path.parent, e
            )
            self._unwritable = True
            return
        try:
            _lock_file(self._lock_handle)
        except OSError as e:
            self.close()
            raise NonceRefused(
                RULE_QUEUE_LOCKED,
                f"{self._path.parent} is in use by another NonceAllocator "
                f"({type(e).__name__}); use one allocator per store",
            ) from e
        self._load()

    def close(self) -> None:
        """Release the store for another allocator."""
        if self._lock_handle is not None:
            self._lock_handle.close()
            self._lock_handle = None

    @property
    def gap_retries(self) -> int:
        """How many times a 503 resends the same nonce."""
        return self._gap_retries

    @staticmethod
    def key(chain: str, sender: str) -> str:
        """
        Return the queue key for a sender on a chain.

        :param chain: Chain name
        :param sender: Requester address
        :return: The key
        """
        return f"{chain.lower()}:{sender.lower()}"

    def _queue(self, key: str) -> _Queue:
        with self._lock:
            return self._queues.setdefault(key, _Queue())

    def stalled(self, chain: str, sender: str) -> bool:
        """
        Whether the sender's queue on this chain is stalled.

        :param chain: Chain name
        :param sender: Requester address
        :return: True while only a probe at mapNonces is handed out
        """
        return self._queue(self.key(chain, sender)).stalled

    def stalled_since(self, chain: str, sender: str) -> Optional[float]:
        """
        Return when the sender's queue on this chain stalled.

        :param chain: Chain name
        :param sender: Requester address
        :return: The clock time it stalled at, or None if it is not stalled
        """
        return self._queue(self.key(chain, sender)).stalled_at

    def delivered(self, chain: str, sender: str, nonces: Iterable[int]) -> None:
        """
        Start the settle clock of each held nonce whose delivery arrived.

        It waits for the queue's lock, so do not call it inside ``reserve``.

        :param chain: Chain name
        :param sender: Requester address
        :param nonces: Nonces whose deliveries were seen
        """
        queue = self._queue(self.key(chain, sender))
        now = self._clock()
        with queue.lock:
            marked = [n for n in nonces if n in queue.slots]
            for nonce in marked:
                if queue.slots[nonce].delivered_at is None:
                    queue.slots[nonce].delivered_at = now
        if marked:
            self._save()

    def _sync(self, key: str, queue: _Queue, map_nonces: int) -> None:
        """Free every slot below mapNonces (settled), and stall an overdue queue.

        :param key: The queue key
        :param queue: The queue, with its lock held
        :param map_nonces: The marketplace's current mapNonces(sender)
        """
        now = self._clock()
        settled = [n for n in queue.slots if n < map_nonces]
        for nonce in settled:
            del queue.slots[nonce]
        overdue = any(self._overdue(slot, now) for slot in queue.slots.values())
        if overdue and not queue.stalled:
            logger.warning("mech nonce queue %s stalled: a slot never settled", key)
            queue.stalled_at = now
        if settled or overdue:
            self._save()

    def _overdue(self, slot: _Slot, now: float) -> bool:
        """Whether mapNonces should have passed a held slot by now.

        :param slot: The held slot
        :param now: The clock time
        :return: True once the settle timeout has run out
        """
        return now - slot.settle_from() > self._settle_timeout

    # too-many-arguments: the queue key (chain, sender), the mech and the
    # mapNonces reader are all needed to place the slot; timeout and salt are
    # keyword-only
    @contextlib.contextmanager
    def reserve(  # pylint: disable=too-many-arguments
        self,
        chain: str,
        sender: str,
        mech: str,
        read_map_nonces: Callable[[], int],
        *,
        timeout: float,
        salt: str = "",
    ) -> Iterator[Reservation]:
        """
        Reserve n = mapNonces + held slots for ``mech`` (the probe at mapNonces when stalled).

        :param chain: Chain name
        :param sender: Requester address
        :param mech: Mech the request goes to
        :param read_map_nonces: Reads mapNonces(sender) from the marketplace
        :param timeout: Seconds to wait for the lock and for another mech
        :param salt: The request's metadata salt
        :yield: The reservation; call ``answered`` with the mech's answer
        :raises NonceRefused: ``mech-in-flight``, ``mech-queue-unreadable`` or
            ``mech-queue-unwritable``
        """
        self._check_usable()
        key = self.key(chain, sender)
        queue = self._queue(key)
        deadline = self._clock() + timeout
        with self._locked(queue, timeout):
            while True:
                map_nonces = read_map_nonces()
                self._sync(key, queue, map_nonces)
                others = {s.mech for s in queue.slots.values()} - {mech.lower()}
                if not others:
                    break
                if self._clock() >= deadline:
                    raise NonceRefused(
                        RULE_IN_FLIGHT,
                        f"this sender still has requests to {sorted(others)[0]} "
                        "settling on this chain, and a request to another mech "
                        "must wait for them; try again once they settle",
                    )
                self.sleep(POLL_SECONDS)
            if queue.stalled:
                nonce = map_nonces  # the probe that can clear the stall
            else:
                nonce = map_nonces + len(queue.slots)
            # written down before the POST: if the process dies mid-send the
            # mech may hold n, and a restart must not hand it out again
            prior = queue.slots.get(nonce)  # held already only for a probe
            queue.slots[nonce] = _Slot(UNKNOWN, mech.lower(), salt, self._clock())
            self._save()
            if self._unwritable:  # held in memory only: a restart would reissue n
                self._restore(queue, nonce, prior)
                self._check_usable()
            reservation = Reservation(
                nonce, prior, functools.partial(self._answered, key)
            )
            try:
                yield reservation
            finally:
                if reservation.outcome is None:
                    # an exception mid-send: whether the mech stored the
                    # request is unknown, so the slot stays held
                    logger.warning(
                        "mech nonce %s on %s held as unknown: the request may "
                        "have reached the mech",
                        nonce,
                        key,
                    )
                    reservation.answered(UNKNOWN, mech=mech, salt=salt)

    @contextlib.contextmanager
    def exclusive(
        self,
        chain: str,
        sender: str,
        read_map_nonces: Callable[[], int],
        *,
        timeout: float,
    ) -> Iterator[None]:
        """
        Hold the queue for an on-chain request, once no slot is held.

        An on-chain marketplace request takes the nonce at mapNonces itself,
        which a held off-chain slot already claims; so it waits for the queue
        to empty, and is refused as ``mech-in-flight`` past ``timeout``.

        :param chain: Chain name
        :param sender: Requester address
        :param read_map_nonces: Reads mapNonces(sender) from the marketplace
        :param timeout: Seconds to wait for the lock and for an empty queue
        :yield: Nothing; send the on-chain request inside the context
        :raises NonceRefused: ``mech-in-flight``, ``mech-queue-unreadable`` or
            ``mech-queue-unwritable``
        """
        self._check_usable()
        key = self.key(chain, sender)
        queue = self._queue(key)
        deadline = self._clock() + timeout
        with self._locked(queue, timeout):
            while True:
                self._sync(key, queue, read_map_nonces())
                if not queue.slots:
                    break
                if self._clock() >= deadline:
                    raise NonceRefused(
                        RULE_IN_FLIGHT,
                        "this sender still has off-chain requests settling on "
                        "this chain; an on-chain request must wait for them",
                    )
                self.sleep(POLL_SECONDS)
            yield

    @contextlib.contextmanager
    def hard_cancel(
        self,
        chain: str,
        sender: str,
        read_map_nonces: Callable[[], int],
        *,
        stalled_for: float,
    ) -> Iterator[int]:
        """
        Hold a long-stalled queue while one on-chain request consumes mapNonces.

        :param chain: Chain name
        :param sender: Requester address
        :param read_map_nonces: Reads mapNonces(sender) from the marketplace
        :param stalled_for: Seconds the queue must have been stalled
        :yield: n = mapNonces, the nonce the on-chain request consumes
        :raises NonceRefused: ``mech-queue-not-stalled`` unless stalled for at
            least ``stalled_for`` seconds; ``mech-in-flight`` while another
            request from the sender is being sent; ``mech-queue-unreadable``
            or ``mech-queue-unwritable``
        """
        self._check_usable()
        key = self.key(chain, sender)
        queue = self._queue(key)
        with self._locked(queue, 0):
            map_nonces = read_map_nonces()
            self._sync(key, queue, map_nonces)
            now = self._clock()
            if queue.stalled_at is None or now - queue.stalled_at < stalled_for:
                stalled = (
                    "is not stalled"
                    if queue.stalled_at is None
                    else f"has been stalled for {now - queue.stalled_at:.0f}s"
                )
                raise NonceRefused(
                    RULE_QUEUE_NOT_STALLED,
                    f"this sender's queue on {chain} {stalled}; a hard cancel "
                    f"needs it stalled for at least {stalled_for:.0f}s",
                )
            try:
                yield map_nonces
            finally:
                # whatever the on-chain request did, the next cancel needs a
                # fresh stalled_for window: mapNonces may now point at a slot
                # the mech already accepted
                now = self._clock()
                queue.stalled_at = now
                self._restart_settle_clocks(queue, map_nonces, now)
                self._save()

    @staticmethod
    def _restart_settle_clocks(queue: _Queue, nonce: int, now: float) -> None:
        """Restart the settle clock of every held slot above an unstuck ``nonce``.

        :param queue: The queue, with its lock held
        :param nonce: The nonce that was unstuck
        :param now: The clock time to restart from
        """
        for held_nonce, slot in queue.slots.items():
            if held_nonce > nonce:
                slot.at = now
                slot.delivered_at = None

    @staticmethod
    @contextlib.contextmanager
    def _locked(queue: _Queue, timeout: float) -> Iterator[None]:
        """Hold a queue's lock, waiting at most ``timeout`` for it.

        :param queue: The queue
        :param timeout: Seconds to wait
        :yield: Nothing, with the lock held
        :raises NonceRefused: ``mech-in-flight`` if the lock stays taken
        """
        if not queue.lock.acquire(timeout=max(timeout, 0)):
            raise NonceRefused(
                RULE_IN_FLIGHT,
                "another request from this sender is still being sent on this "
                "chain; try again shortly",
            )
        try:
            yield
        finally:
            queue.lock.release()

    def _check_usable(self) -> None:
        """Refuse while the store cannot be read or written.

        :raises NonceRefused: ``mech-queue-unreadable`` or ``mech-queue-unwritable``
        """
        if self._broken:
            raise NonceRefused(
                RULE_QUEUE_UNREADABLE,
                f"{self._path} could not be read, so held nonces cannot be "
                "told from free ones; no mech request is sent until it is "
                "restored or removed",
            )
        if self._unwritable:
            raise NonceRefused(
                RULE_QUEUE_UNWRITABLE,
                f"{self._path} could not be written, so a held nonce would not "
                "survive a restart; no mech request is sent until it is "
                "writable again and the allocator is reloaded",
            )

    # too-many-arguments: the queue key, the nonce and the answer, plus the
    # keyword-only mech, salt and prior slot the answer is recorded with
    def _answered(  # pylint: disable=too-many-arguments
        self,
        key: str,
        nonce: int,
        outcome: Outcome,
        *,
        mech: str,
        salt: str,
        prior: Optional[_Slot],
    ) -> None:
        """Apply the mech's answer to a reserved nonce (the queue lock is held).

        :param key: The queue key
        :param nonce: The reserved nonce
        :param outcome: What the answer means for the nonce
        :param mech: The mech the request went to
        :param salt: The request's metadata salt
        :param prior: The slot that held n before this reservation
        """
        queue = self._queue(key)
        now = self._clock()
        if outcome == ACCEPTED:
            queue.slots[nonce] = _Slot(ACCEPTED, mech.lower(), salt, now)
            if queue.stalled:
                self._restart_settle_clocks(queue, nonce, now)
            queue.stalled_at = None
        elif outcome == TAKEN:
            if prior is not None:
                # a probe over our own slot at mapNonces: the mech holds that
                # request, so it was accepted
                queue.slots[nonce] = _Slot(
                    ACCEPTED, prior.mech, prior.salt, prior.at, prior.delivered_at
                )
                if not self._overdue(prior, now):
                    # not the slot that stalled the queue (mapNonces has moved
                    # on to it, say after a hard cancel): resume from here
                    self._restart_settle_clocks(queue, nonce, now)
                    queue.stalled_at = None
                # else it is the stuck one: the stall, and its clock, stand
            else:
                # another signer took n, or the mech still settles slots we
                # think free: sending more would only gap behind it
                queue.slots.pop(nonce, None)
                if not queue.stalled:
                    queue.stalled_at = now
        elif outcome == UNKNOWN:
            queue.slots[nonce] = _Slot(UNKNOWN, mech.lower(), salt, now)
        elif outcome == NOT_ACCEPTED:
            self._restore(queue, nonce, prior)  # n is reused next
        # RETRY: the caller resends the same nonce, under the placeholder
        self._save()

    @staticmethod
    def _restore(queue: _Queue, nonce: int, prior: Optional[_Slot]) -> None:
        """Put back what held n before the placeholder, or free n.

        :param queue: The queue
        :param nonce: The nonce
        :param prior: What held it before, or None
        """
        if prior is None:
            queue.slots.pop(nonce, None)
        else:
            queue.slots[nonce] = prior

    def _load(self) -> None:
        """Read the persisted queues; an unreadable file refuses every request."""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            queues = {key: self._parse_queue(entry) for key, entry in raw.items()}
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            # held slots cannot be told apart from free ones any more, so stop
            # every queue rather than risk reissuing a nonce the mech holds
            logger.error("unreadable %s (%s); mech requests refused", self._path, e)
            self._broken = True
            return
        self._queues.update(queues)

    def _parse_queue(self, entry: Dict[str, Any]) -> _Queue:
        """Rebuild one persisted queue.

        :param entry: The queue's JSON object
        :return: The queue
        """
        stalled_at = _optional_time(entry.get("stalled_since"))
        if entry.get("stalled") and stalled_at is None:
            # stalled before its time was recorded: count from now
            stalled_at = self._clock()
        return _Queue(
            slots={
                int(n): _Slot(
                    _slot_state(s["state"]),
                    str(s["mech"]).lower(),
                    s["salt"],
                    float(s["at"]),
                    _optional_time(s.get("delivered_at")),
                )
                for n, s in entry.get("slots", {}).items()
            },
            stalled_at=stalled_at,
        )

    def _save(self) -> None:
        """Write every queue down; a failure refuses requests, never an answer."""
        with self._save_lock:
            try:
                self._write()
            except OSError as e:
                logger.error(
                    "could not write %s (%s); mech requests refused", self._path, e
                )
                self._unwritable = True

    def _write(self) -> None:
        with self._lock:
            queues = list(self._queues.items())
        state = {
            key: {
                "stalled": queue.stalled,
                "stalled_since": queue.stalled_at,
                "slots": {
                    str(n): {
                        "state": s.state,
                        "mech": s.mech,
                        "salt": s.salt,
                        "at": s.at,
                        "delivered_at": s.delivered_at,
                    }
                    for n, s in sorted(dict(queue.slots).items())
                },
            }
            for key, queue in queues
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(self._path)


def _slot_state(raw: Any) -> SlotState:
    """Check a persisted slot's state.

    :param raw: The stored value
    :return: The state
    :raises ValueError: If it is not a state a held slot can have
    """
    if raw == ACCEPTED:
        return ACCEPTED
    if raw == UNKNOWN:
        return UNKNOWN
    raise ValueError(f"slot state {raw!r} is not one of {SLOT_STATES}")


def _optional_time(raw: Any) -> Optional[float]:
    return None if raw is None else float(raw)


def outcome_of(error: Union[OffchainRequestRejected, OffchainTopUpFailed]) -> Outcome:
    """
    Map a failed off-chain request to what it means for its nonce.

    :param error: The rejection or top-up failure ``send_request`` raised
    :return: ``not_accepted`` for a top-up failure; for an HTTP answer,
        ``retry`` on 503, ``taken`` on the stale-nonce 401, ``not_accepted``
        on any other 4xx, else ``unknown``
    """
    if isinstance(error, OffchainTopUpFailed):
        return NOT_ACCEPTED
    if error.retryable:
        return RETRY
    if error.status == HTTP_UNAUTHORIZED and error.reason == NONCE_TAKEN_REASON:
        return TAKEN
    if error.status in HTTP_CLIENT_ERRORS:
        return NOT_ACCEPTED
    return UNKNOWN


def _refusal(error: Union[OffchainRequestRejected, OffchainTopUpFailed]) -> str:
    """Describe a failed off-chain request for its NonceRefused.

    :param error: The rejection or top-up failure
    :return: The detail
    """
    if isinstance(error, OffchainTopUpFailed):
        return f"the auto top-up for nonce {error.nonce} failed: {error}"
    return (
        f"the mech answered HTTP {error.status} ({error.reason}) to nonce {error.nonce}"
    )


# too-many-arguments: keyword-only; the allocator plus what identifies,
# sends and bounds one request
def send_with_nonce(  # pylint: disable=too-many-arguments
    allocator: NonceAllocator,
    *,
    chain: str,
    sender: str,
    mech: str,
    salt: str,
    read_map_nonces: Callable[[], int],
    send: Callable[[int, PreSignHook], OffchainRequestResult],
    not_sent: Tuple[Type[Exception], ...],
    timeout: float,
    on_request_id: Optional[Callable[[bytes, int], Any]] = None,
) -> OffchainRequestResult:
    """
    Reserve a nonce, send with it, and record what the mech answered.

    ``send(nonce, hook)`` must pass ``hook`` to ``send_request`` as
    ``on_request_id``; ``hook`` runs the caller's own ``on_request_id``.
    ``send_request`` marks the hook received on entry, and posting just
    before the POST, after signing, so:

    - never received (``send`` did not pass the hook on): nothing tells a
      failure before the POST from one after, so the slot is held as
      ``unknown`` and the misuse is logged;
    - received but not posting: the failure came before the POST (an
      unknown tool, a missing off-chain URL, an RPC error, a refused or
      async hook, a signer error), reached no mech, and the nonce is free
      again;
    - posting: a failure may have reached the mech (a transport error), so
      the slot is held as ``unknown``, unless the exception is in
      ``not_sent``.

    A 503 resends the same nonce (and, the salt being kept, the same id) up
    to the allocator's ``gap_retries`` times, with a fresh hook each time.

    :param allocator: The allocator
    :param chain: Chain name
    :param sender: Requester address
    :param mech: Mech the request goes to
    :param salt: The request's metadata salt (``extra_attributes["nonce"]``)
    :param read_map_nonces: Reads mapNonces(sender) from the marketplace
    :param send: Sends one off-chain request with the given nonce and hook
    :param not_sent: Exceptions ``send`` raises after posting began that
        still reached no mech
    :param timeout: Seconds ``reserve`` may wait
    :param on_request_id: The caller's own pre-sign hook, run by ``hook``
    :return: What ``send`` returned
    :raises NonceRefused: naming the rule, when no nonce could be reserved
        or the mech's answer did not accept the request
    """
    with allocator.reserve(
        chain, sender, mech, read_map_nonces, timeout=timeout, salt=salt
    ) as slot:
        for attempt in range(allocator.gap_retries + 1):
            hook = PreSignHook(on_request_id)
            try:
                result = send(slot.nonce, hook)
            except (OffchainRequestRejected, OffchainTopUpFailed) as e:
                outcome = outcome_of(e)
                if outcome == RETRY and attempt < allocator.gap_retries:
                    allocator.sleep(GAP_RETRY_SECONDS)
                    continue
                slot.answered(
                    NOT_ACCEPTED if outcome == RETRY else outcome,
                    mech=mech,
                    salt=salt,
                )
                raise NonceRefused(REJECTION_RULES[outcome], _refusal(e)) from e
            except not_sent:
                slot.answered(NOT_ACCEPTED, mech=mech, salt=salt)
                raise
            except Exception:
                if not hook.received:
                    logger.error(_HOOK_NOT_PASSED, slot.nonce)
                elif not hook.posting:
                    slot.answered(NOT_ACCEPTED, mech=mech, salt=salt)
                raise
            if not hook.received:
                logger.warning(_HOOK_NOT_PASSED, slot.nonce)
            slot.answered(ACCEPTED, mech=mech, salt=salt)
            return result
    raise AssertionError("unreachable")  # pragma: no cover
