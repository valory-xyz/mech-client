# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ✨ Added

- `--max-cost` on `mechx request` (`max_cost` on `MarketplaceService.send_request`): the most to pay per request, in base units of the Mech's payment asset. Off-chain it is the cap signed into the request. On-chain the Mech's advertised `maxDeliveryRate` is the charge, and a `--max-cost` below it refuses the request before it is sent.
- Without `--max-cost`, an off-chain request signs twice the expected cost the Mech's manifest publishes for the tool (`toolMetadata.<tool>.expectedCost`, with `asset` and a decimal-string `amount`), and falls back to the Mech's advertised `maxDeliveryRate`, with a warning, for a tool without one or with one stated in another asset; an unreadable manifest gets one warning of its own. A batch signs the largest cap among its tools. Amounts above a uint256 are refused before any chain read, and a derived cap more than 10x the advertised maximum is signed with a warning. See "Choosing a cap" in the docs.
- `read_expected_costs(manifest)` reads that field, and `mech_report` passes it on under `payment.expected_costs` with `expected_cost_note`.
- `DeliveryResult.failure` (`RunFailure`, with `error` and `fault`): set when an off-chain run failed. The Mech settles a failed run on-chain at the envelope's `delivery_rate`, reported in `actual_delivery_rate`: the full signed cap for a `client` fault; for a `mech` fault the amount depends on the Mech's settings. `mechx request` prints `Request <id> failed: <error>` with `Fault:` and `Charged:` lines. `status: "rejected"` is unchanged.
- `validate_request_shape`: `send_request` refuses a prompt that is not a string, an empty tool, or extra attributes that set `prompt` or `tool`, before any chain read, manifest fetch or request. It reads only its arguments. `extra_attributes["nonce"]` stays allowed: it pins the metadata salt, which the nonce allocator relies on.
- A Mech's HTTP 400 refusing a cap below its minimum charge is reported with the `minimum_cap` it names, and never auto-deposits.
- `DeliveryResult.actual_delivery_rate`: the charge the Mech reports for the request, in the base units of its payment asset, read from the off-chain delivery envelope. `None` when the Mech reports no charge, which is always the case for on-chain delivery. `mechx request` prints it as `Reported charge: <amount>`; the Mech settles it on-chain afterwards.
- `--nonce-mode` on `mechx request` (`nonce_mode` on `MarketplaceService.send_request`): `explicit` (the default) or `sequential`; `send_request` with `nonces=[...]`, as the nonce allocator calls it, is sequential, and `explicit` with `nonces` is refused, and `--deadline-seconds` (`deadline_seconds`), how long an explicit request stays settleable from the latest block (15 minutes by default). See "Offchain Requests" in the docs. Requires a Mech release that knows the option; on an older Mech pass `sequential`.
- The marketplace ABI is the build of autonolas-marketplace `main` at `14f191a`: `getRequestIdWithNonce` with its deadline and signing domain (`getDomainSeparatorWithNonce`), the `deliverMarketplaceWithSignatures` overloads that settle a cap with an actual charge, and the `RateOverCap` and `SignatureExpired` errors.

### 🔧 Changed

- `max_price` is checked against the signed cap times the number of prompts, so an off-chain request is held to the cap it signs rather than to the Mech's advertised `maxDeliveryRate`. The manifest is read before that check, to size the cap.
- With `--auto-deposit`, a 402 whose `required` is above the signed cap is refused instead of deposited. The deposit is `required` less the `currentBalance` the Mech reports, which already excludes what the requester's in-flight requests reserve and may be negative.
- The manifest fetched from the Mech's `ComplementaryServiceMetadata` URI is used only when the gateway answers with it and its bytes hash to the content id that URI names; a gateway error or a mismatch is treated as an unreadable manifest, each with its own log line.
- Buyer docs say cap where they said price: the requester sets the cap signed into an off-chain request, the Mech charges at or below it, and what it does not charge stays in the buyer's balance. The Mech's `maxDeliveryRate` is the on-chain charge and the off-chain fallback cap.

## [0.26.2] - 2026-11-20

### 🔧 Changed

- `olas-operate-middleware` floor raised to 0.15.54 (was 0.15.39), the first release that accepts fastapi past 0.120 (valory-xyz/olas-operate-middleware#509). mech-client does not use fastapi itself; the higher floor stops a resolver from settling on an older middleware, which caps fastapi below 0.121.
- That middleware requires `open-aea-ledger-ethereum>=2.2.10` and `open-autonomy>=0.21.30`, so `open-aea-helpers` is pinned to 0.21.31 (was 0.21.29) and the lock moves the open-aea packages to 2.2.10 and open-autonomy to 0.21.31. A project pinning `open-aea-ledger-ethereum==2.2.9` must move to 2.2.10.
- Development toolchain: tomte's `open_autonomy_version` / `open_aea_version`, the lint envs' `open-autonomy[all]` and liccheck's authorized `open-autonomy` follow to 0.21.31 / 2.2.10.

## [0.26.1] - 2026-11-19

### 🐛 Fixed

- A delivery whose inline payload carries `status: "rejected"` frees its nonce, so the next request from that sender reuses that nonce instead of skipping it. The mech discards a rejected request instead of settling it, so `mapNonces[sender]` never passes that nonce; the slot was previously kept held as `accepted`, and every later request from the same sender was answered 503 "wire nonce above sender's next expected slot" until the nonce store was reset by hand.
- `NonceAllocator.rejected(chain, sender, [(nonce, salt), ...])` is the public counterpart of `delivered()` for rejected deliveries, for a payer that collects deliveries itself. It names each slot by its request, not by its nonce: the `salt` is the metadata salt the request was sent with (`extra_attributes["nonce"]`), and a slot holding another request's salt stays held, so a late or repeated call cannot free a slot that reserved the reissued nonce after it. A nonce is freed only while no later slot is held above it, since `reserve()` numbers slots contiguously from `mapNonces` and freeing one below the top would hand the next request a nonce a live slot already holds; such a slot stays held until its settle timeout stalls the queue, and a batch is freed from the top down. A nonce that is not held, is already past `mapNonces`, or is held as `unknown` is a no-op. It never marks the queue stalled and never clears a stall, and every nonce it frees or leaves held is logged. Only the mech's inline envelope counts: a delivery read from a result file (`url` set) carries tool output, whose `status` is not the mech's. Like `delivered()`, it waits for the queue's lock, so it must not be called inside `reserve()`.
- `send_with_nonce` does not call `rejected()`; it answers its reservation with the new `rejected` answer instead, so the slot is decided in one store write while the queue's lock is still held and no waiter can reserve against a slot that is about to be freed. `rejected` is an `Answer`, not an `Outcome`: `outcome_of` never returns it, and it is the one answer `posted` does not gate, because a delivery arrived for it.
- The freed-or-held rule in `mech_client/nonces.py`'s module docstring now names both of its exceptions, a 503 that still stands after `gap_retries` resends and a rejected delivery. The README nonce example routes rejected deliveries to `rejected()`, and `docs/ARCHITECTURE.md` follows.

### 🔧 Changed

- Development toolchain: tomte pinned to 0.7.4 (was 0.7.3), whose security policy carries the advisory ignores the `safety` check needs. No runtime dependency changes.

## [0.26.0] - 2026-11-13

### ✨ Added

- `mech_client.nonces`: the off-chain marketplace nonce allocator. `NonceAllocator(store_path, settle_timeout=..., gap_retries=...)` keeps one queue per requester and chain: one mech in flight (settlement rebuilds every id from one counter per requester, so while one mech holds a slot a request to another mech waits, and is refused as `mech-in-flight` when its wait runs out), requests posted in nonce order, and a slot held until `mapNonces` passes it, never dropped on a timer. Slots are written to `mech_nonces.json` under `store_path` (created if missing), and fsynced, before each POST, so a restart never reissues a held nonce. The store is locked to one allocator, across processes too: a second one is refused as `mech-queue-locked` until the first is closed or its process exits, and a closed allocator refuses as `mech-queue-closed` and writes nothing, logging each change it skips. A lock that fails for any other reason, and an unreadable or unwritable store, refuse requests. `reserve`, `exclusive` (for an on-chain request), `delivered`, `stalled`, `stalled_since` and `hard_cancel`, which yields `mapNonces` for one on-chain request once the queue has been stalled for at least `stalled_for` seconds, refused otherwise with `mech-queue-not-stalled`; leaving it restarts the stall clock, so each cancel needs its own window. A probe that is accepted, or answered `taken` over a slot of ours that is not itself overdue, clears the stall (a `taken` over the overdue slot `mapNonces` is stuck on leaves the stall clock running, so `hard_cancel` becomes allowed); it and a hard cancel restart the settle clocks of the later slots. A stored slot state other than `accepted`/`unknown` makes the store unreadable, and a negative `settle_timeout` or `gap_retries` raises `ValueError`. Refusals raise `NonceRefused` with a `rule`, a `NonceRule` with a `RULE_*` constant for each value. A `Reservation` is answered once with a terminal outcome (`retry` leaves it open for the resend's answer), and its `nonce`, `prior` and `outcome` are read-only. A `taken` answer with no slot of ours keeps the answering mech in flight at that nonce (an optional `taken` field in the store) until `mapNonces` passes it. A probe answered `unknown` leaves the slot it probed as it was, its settle clock and `taken` marker included, and so does a process that dies mid-probe.
- `outcome_of(error)` maps `OffchainRequestRejected` and `OffchainTopUpFailed` to what they mean for the nonce: `retry` (503), `taken` (the 401 "wire nonce below sender's next expected slot"), `not_accepted` (any other 4xx but 401, including 402, or a failed top-up) or `unknown` (any other 401, so a reworded reason holds the nonce rather than freeing it, and other 5xx). A refusal's detail carries the mech's reason. A slot is freed only when nothing left the process for it: once the request was posted, a rejection (any 4xx but 401), a failed top-up after the 402 and an exception listed in `not_sent` all hold the nonce as `unknown` until `mapNonces` passes it. A rejection or a failed top-up is refused as a `NonceRefused` that names the mech's rejection (`mech-request-rejected`) and says the nonce stays held; a `not_sent` exception is logged as held and re-raised unchanged. The one exception is a 503 that still stands after `gap_retries` resends, which frees the nonce, because the mech admitted nothing. `Reservation.answered(outcome, mech=..., salt=..., posted=...)` requires `posted`, whether the request's payload left the process, so a caller driving a `Reservation` itself cannot free a posted slot by leaving it out. `send_with_nonce(...)` sends one request through a reservation, resending the same nonce and id on a 503 up to `gap_retries` times. It sends a new request, never a held one: a stalled queue's probe carries the caller's request, so it cannot resend a held request's id. It calls `send(nonce, hook)`, and `send` passes `hook`, a `PreSignHook`, to `send_request` as `on_request_id`. `send_request` calls its `mark_received()` on entry and `mark_posting()` right before the POST, after signing (its `received`/`posting` are read-only, and posting requires received): a failure in between frees the nonce, since nothing left the process (a signer error included); a failure when `send` never passed the hook on is held as `unknown` and logged. A caller's own pre-sign hook goes in as `send_with_nonce(on_request_id=...)`; an async one is refused as by `send_request`.
- The off-chain request id is derived locally from the marketplace's `domainSeparator()` (`request_digest`). `getRequestId` is still called; if the RPC answers anything else, `RequestIdMismatch` (`expected`, `reported`, `nonce`) is raised before `on_request_id` and before signing. The id that is signed is always the local one.
- `send_request(..., max_price=...)` raises `MechPriceExceeded` (`price`, `max_price`) before any deposit, signature or POST when the mech's `max_delivery_rate` times the number of prompts exceeds it. It also bounds the call's auto-deposits after a 402: together they never exceed `max_price`, counting what earlier `send_with_nonce` resends of the same request deposited (`PreSignHook.deposited`), and a shortfall that would take them past it raises `OffchainTopUpFailed` before that deposit is sent, on top of each auto-deposit's own bound. With `max_price=None` an auto-deposit is bounded only by `_MAX_AUTO_DEPOSIT_RATIO` times the mech's `max_delivery_rate`.
- `MarketplaceService.mech_info(mech)` returns `MechInfo(mech, service_id, payment_type, max_delivery_rate)`, `MarketplaceService.marketplace_contract()` the marketplace contract, and `MarketplaceService.requester()` the requester of record (the Safe in agent mode, else the signer's EOA).
- `payment_token(payment_type, chain)` names the token a mech is paid in (`None` for native), and `balance_tracker(chain, payment_type)` the balance tracker a prepaid top-up pays (`None` for NVM subscriptions). Both use the chain id payments use, `MECHX_LEDGER_CHAIN_ID` included, and raise `ValueError` for an unknown chain or a token or tracker not deployed on it.
- `ToolManager.read_tools_metadata(service_id)` returns `MetadataRead(document, error)` and never raises for an unreadable document, including a gateway error status, a document nested past the JSON decoder's limit and a chain with no metadata hash contract. Causes are redacted, so a keyed RPC URL never reaches them. `MetadataRead` holds exactly one of `document` and `error`, built with `MetadataRead.ok(...)` / `MetadataRead.failed(...)`. A missing or corrupt packaged ABI still raises. `offchain_blocker(read)` says why a mech cannot take off-chain requests, or `None`.
- The chat contract: `is_chat_prompt(prompt)` and `chat_report(delivery)`, which returns a `ChatReport` (`completion`, `usage`) from a delivery, rendering unrequested tool calls as fenced bash blocks. A JSON string is decoded one level, and only where it is the delivery's structure: a whole delivery sent as a string may be a `response`/`result` wrapper or a message, a wrapper's string value only a message (`choices`, `content`/`text`/`completion`, `tool_calls`), and either must yield a completion (an empty `content` included). Anything else, a number or a model's own JSON answer included, is reported as that text; a JSON string literal is decoded. A boolean usage count is left out.
- `rpc_url=` on `MarketplaceService`, `DepositService`, `SubscriptionService`, `ToolService` and `ToolManager` (and `get_mech_config`); a blank one raises `ValueError`, so one process can use several chains without the process-wide `MECHX_CHAIN_RPC`. `None` keeps the existing lookup. The auto-deposit's `DepositService` uses the calling service's `rpc_url`.
- All of the above are exported from `mech_client`, with `send_request`'s return types `OnchainRequestResult`, `OffchainRequestResult` and their union `RequestResult`.

### 🔧 Changed

- Base/Polygon Marketplace and registry commands require `MECHX_MARKETPLACE_BASE_SQUID_URL`, `MECHX_MARKETPLACE_POLYGON_SQUID_URL`, `MECHX_REGISTRY_BASE_SQUID_URL` and `MECHX_REGISTRY_POLYGON_SQUID_URL`. Committed endpoint defaults are blank; configure these before upgrading. Chain config now declares the independent `registry_subgraph_dialect` and endpoint-variable names.
- The private `MarketplaceService._fetch_mech_info` and `_get_marketplace_contract` are replaced by the public `mech_info` and `marketplace_contract`.
- `ToolManager.fetch_tools_metadata` returns `None`, rather than raising, when the contract call for the metadata URI fails with a web3 error, and when the document is not a JSON object.
- A failed request-id derivation, a failed off-chain POST and an unrecoverable signature name only the exception type in their message; the cause is chained and its redacted text logged, with the nonce (and, for a POST, the request id). A derivation that cannot reach the RPC (a `requests` connection error, timeout or HTTP error) raises `RequestIdRpcError`, both a `ValueError` and an `RpcError`, so the CLI still shows its `MECHX_CHAIN_RPC` hint. An auto top-up failure's message is redacted.
- When an off-chain request cannot discover the mech's URL, the error is `offchain_blocker`'s reason, naming the cause of a failed read. `ToolManager.offchain_url_from_metadata(service_id, read)` takes the `MetadataRead` (a bare document is still accepted).
- Fetching the metadata document checks the HTTP status: a gateway error with a JSON body is no longer taken for the document.
- An RPC or transport failure while deriving an off-chain request id, in its `mapNonces`, `domainSeparator` or `getRequestId` read, is a `ValueError` naming the nonce ("the next nonce" when `mapNonces` fails before one is chosen) and the exception type, on the first request of a call as on a later one; in a multi-request off-chain call it also names the requests already accepted.

## [0.25.0] - 2026-11-12

### ✨ Added

- `send_request(..., nonces=[...])` sets the marketplace nonce of each offchain request, instead of `mapNonces(requester) + i`. The nonces must be integers, strictly increasing, one per prompt and none below `mapNonces`; otherwise `ValueError` is raised before anything is signed.
- `send_request(..., on_request_id=fn)` calls `fn(request_id, nonce)` with the raw 32-byte id for each offchain request just before it is signed. If `fn` raises, that request and the rest of the call are neither signed nor sent. An async `fn` is refused.
- Passing `nonces` or `on_request_id` without `use_offchain=True` raises `ValueError`.
- The offchain result lists the `nonces` used, matching `request_ids`.
- `OffchainRequestRejected`, a `ValueError`, raised when the mech answers an offchain request with an HTTP error, including its 402s. It carries `request_id`, `nonce`, `status`, the mech's `reason` as a string, `retryable` (HTTP 503), `unsent` (the later nonces of the call, not sent) and `deposited` (the amount auto-deposited in a confirmed transaction before the mech answered 402 again). Requests accepted earlier in the same call are named in its message and not watched. A transport error stays a plain `ValueError`.
- `OffchainTopUpFailed`, a `ValueError`, raised when the auto top-up after the mech's 402 fails on the requester's side (safety cap, balance, reverted deposit), so the request was not accepted. It carries `request_id`, `nonce` and `unsent`, and its message names requests accepted earlier in the call.

## [0.24.0] - 2026-10-09

### ✨ Added

- `mechx mech info --chain-config <chain> --address <mech>` prints, as JSON, who runs a Mech and how it has behaved, for a buyer deciding whether to pay.
- `ToolManager.mech_report(mech_address, metadata)` returns that report as data, a superset of `terms_report`:
  - `operator`: the domain the manifest claims, as `domain` and `url`, with `domain_verified` true only when `https://<domain>/.well-known/agent-registration.json` lists the Mech's ERC-8004 agent id for the chain's identity registry, and `verification_note` when not. The name is `claimed_name`, with `name_note` saying it is not checked.
  - `benchmarks`: each tool's benchmark link, as the operator's claim, with `benchmark_note`. No figure is reported.
  - `delivery`: `received_requests`, `self_delivered` and `delivered_by_others` from the marketplace subgraph, `since` and `age_days` from the Mech's creation block, and a `note` that the counts cover on-chain and settled off-chain requests, not split by path.
  - `payment`: the payment method, with no price. The contract quotes the charge at request time, and `maxDeliveryRate` is only a ceiling.
- `ToolManager.mech_report_or_terms(mech_address, metadata)` is the report to read before paying: `mech_report` when the manifest and the mech's record can be read, otherwise the terms alone with `report_note` saying why, so an unreadable manifest or indexer never hides the terms or blocks a request. `mech_report` itself stays fail-closed.
- A service registry subgraph endpoint per chain, `registry_subgraph_url`, with the `MECHX_REGISTRY_SUBGRAPH_URL` override. The ERC-8004 agent id is read from it; it is not the Olas service id except by coincidence.
- `ManifestError`, raised when a Mech's manifest cannot be read. The report fails closed: an unreadable manifest gives no report.

### 🔧 Changed

- The domain proof must be served by the exact host the manifest names. Redirects are not followed, and a redirect gets its own note. The body is capped at 64 KB, each read times out after 5 seconds, and a proof that could not be fetched is fetched again next time rather than remembered as a no.
- An operator domain must be a bare lowercase hostname ending in a top-level domain, and a manifest link an `https` URL with a host, parsed rather than prefix-tested; anything else is treated as unpublished. Manifest text is passed on as data and never followed.
- The subgraph reads a report makes time out after 10 seconds each.

## [0.23.3] - 2026-09-21

### ✨ Added

- `mechx request` states the Valory Mech Terms before anything is signed, when the Mech is operated by Valory. Identification is a DNS lookup of the Mech's own name under `mech.valory.xyz`, so the answer does not depend on the Mech being up. It fails closed: a name that does not resolve, a timed-out lookup, or a zone that answers every name all mean the Mech is not identified as Valory operated.
- `mechx mech list` gains an Operator column, marking the Mechs the same check confirms. A Mech that is not confirmed is left blank rather than labelled, since an independent Mech and a lookup that could not complete are indistinguishable to the check.
- `identify()` in `mech_client.domain.identification` returns `VALORY`, `NOT_VALORY` or `UNKNOWN`, so a caller can tell a Mech Valory does not operate from a check that could not complete. `is_valory_operated()` is unchanged.
- `ToolManager.terms_report(mech_address, metadata)` returns, for an already fetched metadata document, `valory_operated`, the Valory terms statement as `terms` for a Valory Mech, an `identification_note` when the check could not tell, and the operator's published link as `terms_url`. The chain comes from the manager, and the rule that only a Valory Mech gets the statement lives here, so integrations do not reimplement it.

### 🔧 Changed

- For a Mech operated by someone else, or one the check could not identify, `mechx request` shows the terms link the operator published in `termsUrl`, as published, instead of stating that sending the request means agreeing to it. Those terms are that operator's to state. The link is also still shown in the Terms column of `mechx mech list`.
- `ToolManager.extract_terms_url()` only returns an `https` link with a host, no whitespace or control characters, and at most 2048 characters. Anything else in an operator's `termsUrl` is dropped, including in the Terms column of `mechx mech list`.
- A lookup that fails or times out now logs a warning; only a name that does not exist stays at debug level. Lookups share one pool capped at 8 threads, and a lookup still queued when its caller gives up is cancelled.

## [0.23.2] - 2026-09-16

### ✨ Added

- `mechx mech list` shows a Terms column, read from the `termsUrl` field of each mech's published metadata.
- `mechx request` logs the mech operator's terms link before anything is signed, on both the on-chain and the off-chain path, or states that the mech publishes none.
- `ToolManager.extract_terms_url()` reads the link from a fetched metadata document, for library users.
- `send_request` reads the mech's metadata once per request; the tool check, the terms notice and the off-chain URL lookup all use that one document.

### 🐛 Fixed

- The off-chain path logged that the prompt would be uploaded to a gateway. It never leaves the requester on that path; only its content CID is signed. The log now says so.

## [0.23.1] - 2026-09-16

### ✨ Added

- **Agent mode on Robinhood Chain (4663)**: `mechx setup --chain-config robinhood` creates the service and its Safe, funded with USDG (the chain's USDC payment type) for requests and ETH for the agent's gas.

### 🔧 Changed

- `olas-operate-middleware>=0.15.39`, the first release whose quickstart tables know Robinhood. 0.15.38 carried the chain in its ledger profiles only, so `mechx setup --chain-config robinhood` exited with a `KeyError` before printing an address.

## [0.23.0] - 2026-09-16

### ✨ Added

- **`mech list` on Robinhood** via the marketplace squid. Every chain in `mechs.json` now names its `subgraph_dialect` (`"graph"` or `"squid"`), and `mech list` sends the matching sort syntax.

### 🔧 Changed

- `olas-operate-middleware>=0.15.38` and `open-aea-helpers==0.21.29` (open-autonomy 0.21.29). These carry Robinhood in the middleware's ledger profiles, though not in its quickstart tables, so `mechx setup` still doesn't support the chain. open-autonomy 0.21.27 made the Solana plugin an optional extra ([valory-xyz/open-autonomy#2541](https://github.com/valory-xyz/open-autonomy/pull/2541)), so it and its transitive dependencies are no longer installed.
- `SubgraphClient` now requires a `dialect` argument (`"graph"` or `"squid"`) and rejects an unknown one when built. A `mechs.json` entry with a missing or unknown `subgraph_dialect` fails when the config loads. `query_mechs` rejects an `order_by` that isn't a field name and an `order_direction` other than `asc`/`desc`.
- `MechConfig` requires `subgraph_dialect`, placed before `priority_mech_address`, so positional construction shifts. `query_mm_mechs_info` returns an empty list instead of `None` when a chain has no delivering mechs, and raises `SubgraphError` instead of `KeyError` or `TypeError` on a record it can't read.

## [0.22.1] - 2026-09-14

### ✨ Added

- **Robinhood Chain (4663)** in client mode: marketplace requests (on-chain and offchain), native and USDC-type deposits (USDG on Robinhood), and `tool` commands. Agent mode (`setup`) and `mech list` are not available on Robinhood yet: the operate middleware does not support the chain, and there is no marketplace subgraph.

## [0.22.0] - 2026-08-12

### ✨ Added

#### NVM Subscription Module Refactoring
- **Layered Architecture Alignment**: Refactored NVM subscription module to follow v0.17.0 layered architecture
  - **Infrastructure Layer** (`infrastructure/nvm/`): Configuration, contract wrappers, and resources
    - `NVMConfig` dataclass with `from_chain()` loader
    - 11 refactored contract wrappers (simplified, no transaction building)
    - `NVMContractFactory` for creating contract instances
    - Chain-specific configuration files (gnosis.env, base.env, networks.json)
  - **Domain Layer** (`domain/subscription/`): Business logic components
    - `SubscriptionManager`: Orchestrates 3-transaction purchase workflow
    - `AgreementBuilder`: Builds agreement data structure
    - `FulfillmentBuilder`: Builds fulfillment parameters
    - `SubscriptionBalanceChecker`: Validates sufficient balance
  - **Service Layer** (`services/subscription_service.py`): Service orchestration
    - Coordinates dependencies and workflow execution
    - Uses `ExecutorFactory` for agent/client mode handling
- **Backward Compatibility**: Deprecated monolithic `nvm_subscription/__init__.py` module
  - Emits `DeprecationWarning` when used
  - Wraps new `SubscriptionService` internally
  - Will be removed in future release
- **Comprehensive Tests**: 14 unit tests for NVM subscription components
  - Infrastructure layer tests (config, contracts)
  - Domain layer tests (builders, manager, balance checker)
  - Service layer tests (subscription service)

#### Documentation Organization
- **docs/ Folder Structure**: Consolidated all documentation in `docs/` folder
  - Moved `ARCHITECTURE.md` → `docs/ARCHITECTURE.md`
  - Moved `TESTING.md` → `docs/TESTING.md`
  - Moved `TOKEN_APPROVAL_AGENT_MODE_ISSUE.md` → `docs/TOKEN_APPROVAL_AGENT_MODE_ISSUE.md`
  - Created `docs/COMMANDS.md` with command dependency diagrams
- **Optimized CLAUDE.md**: Reduced from 1,075 to 323 lines (70% reduction)
  - Extracted command diagrams to `docs/COMMANDS.md`
  - Removed duplicate architecture content
  - Focused on essential development patterns and gotchas
- **Updated Cross-References**: All documentation files reference each other correctly

### 🔧 Changed

- **Delivery results are now the delivered content, in one shape** (breaking, [#250](https://github.com/valory-xyz/mech-client/issues/250))
  - `send_request` now returns a single `deliveries[request_id]` key holding a
    `DeliveryResult`, replacing `delivery_results`. Previously the on-chain flow returned
    a URL string and the off-chain flow returned the mech's raw envelope, so a caller
    could not write one handler.
  - The on-chain URL addressed the delivery *directory*, which serves an HTML listing;
    the result file inside is named after the request ID in decimal. Both watchers now
    build that full path and read the file themselves.
  - `DeliveryResult.data` is the parsed result file, `None` if the gateway could not be
    read. `DeliveryResult.url` is the result-file URL to retry with, `None` for off-chain
    mechs that answer inline. Pairing content with its location in one object keeps the
    two from drifting apart per request.
  - `mechx request` prints the mech's answer (decoding the JSON-encoded `result` field
    when the payload has one, otherwise the payload itself) followed by the result-file
    URL.
- **NVM Subscription Purchase**: Now uses layered architecture with strategy patterns
  - Supports both agent mode (Safe multisig) and client mode (EOA)
  - Chain-specific payment handling (native xDAI for Gnosis, USDC for Base)
  - Improved error handling and validation

## [0.17.2] - 2025-02-06

### ✨ Added

- **Marketplace URL Display**: Setup command now displays marketplace URL for deployed services
  - Shows direct link to service on Olas Marketplace
  - Format: `https://marketplace.olas.network/{chain}/ai-agents/{token}`

### 🔧 Changed

- **ChainType Enum Handling**: Fixed Safe address retrieval to work with ChainType enum keys
  - Iterate over enum keys and match `chain_type.value` against string chain configs
  - Resolves issues with wallet.safes dictionary access

### 🗑️ Removed

- **IPFS to-png Command**: Removed `mechx ipfs to-png` command
  - Command was not widely used and added unnecessary complexity
  - Users can use external tools for image conversion

### 🐛 Fixed

- **Release Workflow**: Set `skip_existing: false` to fail explicitly on duplicate PyPI versions
  - Prevents silent success when version already exists on PyPI
  - Ensures deployment issues are visible

## [0.17.1] - 2025-02-06

### 🐛 Fixed

- **Setup Command**: Fixed agent mode setup and messaging
  - Improved error messages for setup failures
  - Better guidance for users when setup encounters issues
- **Agent Mode Messaging**: Fixed "Agent mode enabled" message display
  - Only shows for wallet commands (request, deposit, subscription)
  - Read-only commands (mech, tool) and utility commands (ipfs) work independently

## [0.17.0] - 2025-02-06

### 🏗️ Major Architectural Refactor

Version 0.17.0 introduces a comprehensive architectural refactoring that separates concerns into distinct layers and introduces modern design patterns. This is a **breaking release** for library users but maintains CLI compatibility where possible.

### ✨ Added

#### Architecture & Design
- **Layered Architecture**: Introduced 4-layer architecture (CLI → Service → Domain → Infrastructure)
- **Service Layer**: New service classes for business logic orchestration
  - `MarketplaceService`: Marketplace request operations
  - `ToolService`: Tool discovery and management
  - `DepositService`: Balance deposit operations
  - `SetupService`: Agent mode setup
  - `SubscriptionService`: NVM subscription management
- **Strategy Pattern**: Flexible payment, execution, and delivery strategies
  - `PaymentStrategyFactory`: Creates payment strategies based on type
  - `ExecutorFactory`: Creates execution strategies (client/agent mode)
  - `DeliveryWatcherFactory`: Creates delivery watchers (onchain/offchain)
- **Domain Layer**: Core business logic and models
  - Payment strategies (Native, Token, NVM)
  - Execution strategies (Client, Agent)
  - Delivery watchers (Onchain, Offchain)
  - Tool models (`ToolInfo`, `ToolSchema`)
- **Infrastructure Layer**: External system adapters
  - Blockchain client (`BlockchainClient`)
  - IPFS client (`IPFSClient`)
  - Subgraph client (`SubgraphClient`)
  - Safe client (`SafeClient`)
  - Configuration loader (`get_mech_config`)

#### CLI Improvements
- **Nested Command Groups**: Reorganized CLI with intuitive command hierarchy
  - `mechx deposit native|token` (was `mechx deposit-native/deposit-token`)
  - `mechx tool list|describe|schema` (was `mechx tools-for-marketplace-mech`, etc.)
  - `mechx mech list` (was `mechx fetch-mm-mechs-info`)
  - `mechx ipfs upload|upload-prompt|to-png` (was separate commands)
  - `mechx subscription purchase` (was `mechx purchase-nvm-subscription`)
  - `mechx setup` (was `mechx setup-agent-mode`)
  - `mechx request` (was `mechx interact`)
- **Improved Help Text**: Better documentation and examples in CLI help messages
- **Consistent Error Handling**: Comprehensive error handling with actionable solutions

#### Testing & Quality
- **Comprehensive Test Suite**: 164 tests with ~40% coverage
  - Unit tests for all service layer components
  - Unit tests for payment strategies
  - Unit tests for execution strategies
  - Unit tests for delivery watchers
  - Unit tests for validators and utilities
- **CI/CD Improvements**: GitHub Actions workflow with Python 3.10 & 3.11 matrix
- **Perfect Linter Scores**: Pylint 10.00/10, all linters passing
- **Type Safety**: Comprehensive type hints throughout codebase

#### Documentation
- **docs/ARCHITECTURE.md**: Comprehensive architecture guide with diagrams
- **docs/TESTING.md**: Testing guide for contributors
- **docs/COMMANDS.md**: Command reference with dependency diagrams
- **Updated CLAUDE.md**: Development guidelines for Claude Code
- **Updated README.md**: New examples and command structure

#### Public API
- **Exposed Public API**: Library users can now easily import services
  ```python
  from mech_client import (
      MarketplaceService,
      ToolService,
      DepositService,
      PaymentType,
      get_mech_config,
      # ... and more
  )
  ```
- **Custom Exceptions**: Specific exception types for better error handling
  - `MechClientError`: Base exception
  - `RpcError`, `SubgraphError`, `ContractError`
  - `ValidationError`, `ConfigurationError`, `TransactionError`
  - `IPFSError`, `ToolError`, `AgentModeError`, `PaymentError`
  - `DeliveryTimeoutError`

### 🔧 Changed

#### Breaking Changes - CLI

**Command Name Changes** (old → new):
- `setup-agent-mode` → `setup`
- `interact` → `request`
- `fetch-mm-mechs-info` → `mech list`
- `deposit-native` → `deposit native`
- `deposit-token` → `deposit token`
- `purchase-nvm-subscription` → `subscription purchase`
- `tools-for-marketplace-mech` → `tool list`
- `tool-description-for-marketplace-mech` → `tool describe`
- `tool-io-schema-for-marketplace-mech` → `tool schema`
- `prompt-to-ipfs` → `ipfs upload-prompt`
- `push-to-ipfs` → `ipfs upload`
- `to-png` → `ipfs to-png`

**Migration**: Update your scripts and aliases to use the new command names. The CLI will not provide backward compatibility for old command names.

#### Breaking Changes - Programmatic API

**Module Relocations**:
- `mech_client.interact` → `mech_client.services.marketplace_service`
- `mech_client.mech_tool` → `mech_client.services.tool_service`
- `mech_client.subgraph` → `mech_client.infrastructure.subgraph`
- `mech_client.ipfs` → `mech_client.infrastructure.ipfs`
- `mech_client.safe_tx` → `mech_client.infrastructure.blockchain.safe_client`

**API Changes**:
- Functions replaced with service classes and methods
- Payment types now use `PaymentType` enum instead of strings
- Delivery watching now uses async/await
- Configuration access via `get_mech_config()` instead of direct dict access

**Migration**: See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for architecture details and code examples.

#### Improved

- **Error Messages**: More descriptive error messages with actionable solutions
- **Validation**: Centralized validation functions with consistent error handling
- **Configuration**: Environment variable overrides with `MECHX_*` prefix
- **Logging**: Structured logging with configurable log levels
- **Code Organization**: Clear separation of concerns across layers
- **Maintainability**: Reduced code duplication and improved modularity

### 🗑️ Removed

#### Deleted Files
- `mech_client/interact.py` (replaced by `services/marketplace_service.py`)
- `mech_client/mech_tool.py` (replaced by `services/tool_service.py`)
- `mech_client/mech_marketplace_tool_management.py` (functionality moved to domain layer)
- `mech_client/mech_marketplace_subgraph.py` (replaced by `infrastructure/subgraph`)
- `mech_client/prompt_to_ipfs.py` (replaced by `infrastructure/ipfs`)
- `mech_client/push_to_ipfs.py` (replaced by `infrastructure/ipfs`)
- `mech_client/to_png.py` (replaced by `infrastructure/ipfs`)
- `mech_client/fetch_ipfs_hash.py` (unused, removed)

**Total**: 6 files deleted, 626 lines removed, replaced with ~1000+ lines of better-organized code.

### 📊 Statistics

- **Lines of code**: Net +400 lines (removed 626, added ~1000)
- **Test coverage**: ~40% (164 tests)
- **Pylint score**: 10.00/10
- **Python versions**: 3.10, 3.11
- **Architecture layers**: 4 (CLI, Service, Domain, Infrastructure)
- **Services**: 5 (Marketplace, Tool, Deposit, Setup, Subscription)
- **Strategies**: 7 (3 payment + 2 execution + 2 delivery)
- **Factories**: 3 (Payment, Executor, DeliveryWatcher)
- **Custom exceptions**: 11 specific exception types
- **Documentation files**: 5 (docs/ARCHITECTURE.md, docs/TESTING.md, docs/COMMANDS.md, CLAUDE.md, README.md)

### 🔗 Documentation

For detailed information about the architecture and development:
- **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - Architecture overview and patterns
- **[docs/TESTING.md](./docs/TESTING.md)** - Testing guide for contributors
- **[docs/COMMANDS.md](./docs/COMMANDS.md)** - Command reference and dependencies

### ⚠️ Important Notes

1. **CLI Commands**: Update all scripts to use new nested command structure
2. **Programmatic API**: Library users must migrate to service-based API
3. **Python Version**: Requires Python >=3.10, <3.12
4. **CI/CD**: Tests exclude trio backend by default (164 asyncio tests)
5. **Linters**: All code must pass pylint 10.00/10 and other linters

### 🙏 Acknowledgments

This refactor was a collaborative effort to modernize the codebase and improve developer experience. Special thanks to all contributors and the Valory AG team.

---

## [0.16.x] and Earlier

For changes in versions prior to 0.17.0, please refer to the git history or contact the maintainers.

[0.17.0]: https://github.com/valory-xyz/mech-client/compare/v0.16.0...v0.17.0

Base/Polygon indexer endpoints are supplied by your deployment operator. Ask the Olas deployment maintainer for the Marketplace and service-registry squid URLs before using these chains; no default endpoints are bundled.
