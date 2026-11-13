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
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Literal,
    Optional,
    Tuple,
    Type,
    Union,
)

from mech_client.services.marketplace_service import (
    RESPONSE_TIMEOUT_SECONDS,
    MechPriceExceeded,
    OffchainRequestRejected,
    OffchainRequestResult,
    OffchainTopUpFailed,
    RequestIdMismatch,
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

Outcome = Literal["accepted", "retry", "not_accepted", "taken", "unknown"]
ACCEPTED: Outcome = "accepted"
RETRY: Outcome = "retry"
NOT_ACCEPTED: Outcome = "not_accepted"
TAKEN: Outcome = "taken"
UNKNOWN: Outcome = "unknown"

RULE_IN_FLIGHT = "mech-in-flight"
RULE_QUEUE_UNREADABLE = "mech-queue-unreadable"
RULE_QUEUE_UNWRITABLE = "mech-queue-unwritable"
RULE_QUEUE_NOT_STALLED = "mech-queue-not-stalled"
REJECTION_RULES: Dict[Outcome, str] = {
    RETRY: "mech-nonce-gap",
    TAKEN: "mech-nonce-taken",
    NOT_ACCEPTED: "mech-request-rejected",
    UNKNOWN: "mech-answer-unknown",
}
# raised by send_request before the pre-sign hook: nothing reached the mech
NOT_SENT_ERRORS: Tuple[Type[Exception], ...] = (RequestIdMismatch, MechPriceExceeded)


class NonceRefused(Exception):
    """The allocator will not hand out a nonce now; ``rule`` names why."""

    def __init__(self, rule: str, detail: str) -> None:
        """
        Initialize the refusal.

        :param rule: The rule that refused, e.g. ``mech-in-flight``
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

    state: Outcome
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
        allocator: "NonceAllocator",
        key: str,
        nonce: int,
        prior: Optional[_Slot],
    ) -> None:
        """
        Initialize the reservation.

        :param allocator: The allocator that reserved it
        :param key: The queue key
        :param nonce: The reserved nonce
        :param prior: What held this nonce before (only a stalled queue's probe)
        """
        self._allocator = allocator
        self._key = key
        self.nonce = nonce
        self.prior = prior
        self.outcome: Optional[Outcome] = None

    def answered(self, outcome: Outcome, *, mech: str, salt: str) -> None:
        """
        Record the mech's answer to this nonce.

        :param outcome: What the answer means for the nonce
        :param mech: The mech the request went to
        :param salt: The request's metadata salt, kept so a resend reuses its id
        """
        self.outcome = outcome
        self._allocator._answered(  # pylint: disable=protected-access  # the allocator owns the queue
            self._key, self.nonce, outcome, mech=mech, salt=salt, prior=self.prior
        )


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
        Load the persisted queues from ``store_path``.

        :param store_path: Directory holding the queue file (``mech_nonces.json``)
        :param settle_timeout: Seconds a delivered or timed-out slot may stay
            unsettled before its queue stalls
        :param gap_retries: How many times a 503 resends the same nonce
        :param clock: Time source, in seconds
        :param sleep: Blocking sleep, in seconds
        """
        self._path = Path(store_path) / NONCES_FILE
        self._settle_timeout = settle_timeout
        self.gap_retries = gap_retries
        self._clock = clock
        self.sleep = sleep
        self._lock = threading.Lock()
        self._save_lock = threading.Lock()
        self._queues: Dict[str, _Queue] = {}
        self._broken = False
        self._unwritable = False
        self._load()

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

        mapNonces should pass a delivered request soon after; one it has not
        passed within the settle timeout stalls the queue.

        :param chain: Chain name
        :param sender: Requester address
        :param nonces: Nonces whose deliveries were seen
        """
        queue = self._queue(self.key(chain, sender))
        now = self._clock()
        with self._lock:
            marked = [n for n in nonces if n in queue.slots]
            for nonce in marked:
                if queue.slots[nonce].delivered_at is None:
                    queue.slots[nonce].delivered_at = now
        if marked:
            self._save()

    def _sync(self, key: str, queue: _Queue, map_nonces: int) -> None:
        """Free every slot below mapNonces (settled), and stall an overdue queue.

        A held slot whose delivery is done or timed out, and that mapNonces has
        not passed within the settle timeout, was dropped or never settled:
        later nonces would gap behind it, so the queue probes at mapNonces
        until one is accepted again.

        :param key: The queue key
        :param queue: The queue, with its lock held
        :param map_nonces: The marketplace's current mapNonces(sender)
        """
        now = self._clock()
        settled = [n for n in queue.slots if n < map_nonces]
        for nonce in settled:
            del queue.slots[nonce]
        overdue = any(
            now - slot.settle_from() > self._settle_timeout
            for slot in queue.slots.values()
        )
        if overdue and not queue.stalled:
            logger.warning("mech nonce queue %s stalled: a slot never settled", key)
            queue.stalled_at = now
        if settled or overdue:
            self._save()

    @contextlib.contextmanager
    # too-many-arguments: the queue key (chain, sender), the mech and the
    # mapNonces reader are all needed to place the slot; timeout and salt are
    # keyword-only
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
        Reserve the next nonce for ``mech``, holding the queue until it answers.

        n = mapNonces + the sender's own held slots. While another mech holds
        unsettled slots this waits (re-reading mapNonces), and is refused as
        ``mech-in-flight`` once ``timeout`` runs out. While the queue is
        stalled only a probe at n = mapNonces is handed out. Leaving the
        context without an answer holds n as ``unknown``.

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
            reservation = Reservation(self, key, nonce, prior)
            try:
                yield reservation
            finally:
                if reservation.outcome is None:
                    # an exception mid-send: whether the mech stored the
                    # request is unknown, so the slot stays held
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

        The last resort for a slot the mech never settles: an on-chain
        marketplace request from ``sender`` takes n = mapNonces and moves
        mapNonces past it, so the next sync frees n while later accepted
        slots stay held. It pays a mech, so whoever calls this decides who
        confirms it. The queue's lock is held for the whole context, so no
        off-chain request goes out meanwhile; the stall itself clears only
        when a probe is accepted again. Leaving the context restarts the stall
        clock, so each cancel needs its own ``stalled_for`` window.

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
                queue.stalled_at = self._clock()
                self._save()

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
            queue.stalled_at = None
        elif outcome == TAKEN:
            if prior is not None and prior.state == UNKNOWN:
                # our own earlier request holds n: it was accepted after all
                queue.slots[nonce] = _Slot(ACCEPTED, prior.mech, prior.salt, now)
            else:
                # another signer took n, or the mech still settles slots we
                # think free: sending more would only gap behind it
                self._restore(queue, nonce, prior)
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
                    s["state"],
                    s["mech"],
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
    if error.status == 401 and error.reason == NONCE_TAKEN_REASON:
        return TAKEN
    if 400 <= error.status < 500:
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


def send_with_nonce(  # pylint: disable=too-many-arguments
    allocator: NonceAllocator,
    *,
    chain: str,
    sender: str,
    mech: str,
    salt: str,
    read_map_nonces: Callable[[], int],
    send: Callable[[int], OffchainRequestResult],
    not_sent: Tuple[Type[Exception], ...],
    timeout: float,
) -> OffchainRequestResult:
    """
    Reserve a nonce, send with it, and record what the mech answered.

    A 503 resends the same nonce (and, the salt being kept, the same id) up
    to the allocator's ``gap_retries`` times. An exception in ``not_sent``,
    or ``RequestIdMismatch`` / ``MechPriceExceeded``, was raised before
    anything was signed, so the nonce is free again; any other failure (a
    transport error) holds the slot as ``unknown``, since the mech may have
    stored the request.

    :param allocator: The allocator
    :param chain: Chain name
    :param sender: Requester address
    :param mech: Mech the request goes to
    :param salt: The request's metadata salt (``extra_attributes["nonce"]``)
    :param read_map_nonces: Reads mapNonces(sender) from the marketplace
    :param send: Sends one off-chain request with the given nonce
    :param not_sent: Exceptions ``send`` raises only before the pre-sign hook
    :param timeout: Seconds ``reserve`` may wait
    :return: What ``send`` returned
    :raises NonceRefused: naming the rule, when the mech did not accept it
    """
    refused_before_signing = NOT_SENT_ERRORS + tuple(not_sent)
    with allocator.reserve(
        chain, sender, mech, read_map_nonces, timeout=timeout, salt=salt
    ) as slot:
        for attempt in range(allocator.gap_retries + 1):
            try:
                result = send(slot.nonce)
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
            except refused_before_signing:
                slot.answered(NOT_ACCEPTED, mech=mech, salt=salt)
                raise
            slot.answered(ACCEPTED, mech=mech, salt=salt)
            return result
    raise AssertionError("unreachable")  # pragma: no cover
