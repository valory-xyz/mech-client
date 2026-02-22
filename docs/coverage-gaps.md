# Test Coverage Gaps

Overall coverage: **80%** (523 lines uncovered across 2652 total)

Last run: 2026-02-22

## Critical Gaps (< 50% coverage)

| File | Coverage | Missing Lines | Notes |
|------|----------|---------------|-------|
| `infrastructure/ipfs/metadata.py` | **23%** | 51-71, 92-109 | IPFS upload/hash logic |
| `domain/delivery/onchain_watcher.py` | **26%** | 79-85, 96-132, 148-171, 179-188, 209-251 | Entire watcher loop |
| `infrastructure/operate/key_manager.py` | **25%** | 42-76 | Keyfile decryption |
| `infrastructure/operate/manager.py` | **36%** | 49-53, 61-63, 73-94, 102 | Operate service management |
| `utils/errors/handlers.py` | **37%** | 67-69, 71-73, 77, 81, 83, 85-90, 92, 94, 96, 98, 100-102, 107-109, 113-115, 117, 119, 143-167, 180-189, 202-223 | Most error handlers |
| `domain/payment/nvm.py` | **37%** | 94-104, 112-124, 142-179, 195 | NVM payment flows |
| `infrastructure/nvm/contracts/did_registry.py` | **35%** | 45-75 | DID registry calls |

## Moderate Gaps (50–70% coverage)

| File | Coverage | Missing Lines | Notes |
|------|----------|---------------|-------|
| `services/marketplace_service.py` | **46%** | 122-223, 258-340, 361, 366-373, 378-382, 403, 426, 477-478 | Core request sending |
| `cli/common.py` | **47%** | 58-77, 99-130 | Wallet command setup |
| `infrastructure/nvm/contracts/base.py` | **57%** | 69, 74, 87, 96-109, 117-124, 133 | NVM contract call wrappers |
| `infrastructure/nvm/contracts/agreement_manager.py` | **60%** | 43-48 | Agreement management |
| `infrastructure/nvm/contracts/escrow_payment.py` | **56%** | 63-75, 85-88 | Escrow payment calls |
| `infrastructure/nvm/contracts/lock_payment.py` | **56%** | 57-62, 72-75 | Lock payment calls |
| `infrastructure/nvm/contracts/transfer_nft.py` | **56%** | 61-72, 82-85 | NFT transfer calls |
| `domain/payment/token.py` | **70%** | 82, 114, 138-146, 156-158, 162-164, 180-188 | Token payment execution |
| `domain/payment/native.py` | **71%** | 82, 90, 104-112 | Native payment execution |
| `cli/main.py` | **68%** | 69-82, 99 | CLI entrypoint agent mode logic |
| `utils/logger.py` | **67%** | 73-86, 122, 149-151, 160-163, 179, 190, 201, 212, 223, 233, 243, 253 | Log formatting paths |

## Smaller Gaps (70–95% coverage)

| File | Coverage | Missing Lines | Notes |
|------|----------|---------------|-------|
| `domain/payment/base.py` | **79%** | 124, 140-145 | Edge cases in base payment |
| `infrastructure/nvm/contracts/nft.py` | **69%** | 49-53 | NFT contract calls |
| `infrastructure/nvm/contracts/token.py` | **69%** | 51-55 | Token contract calls |
| `infrastructure/nvm/contracts/nevermined_config.py` | **78%** | 41, 51 | Config contract calls |
| `infrastructure/config/payment_config.py` | **87%** | 61, 65, 77 | Payment config branches |
| `infrastructure/config/environment.py` | **90%** | 95, 100, 105, 110, 142 | Optional env var branches |
| `infrastructure/config/chain_config.py` | **96%** | 226, 229, 232 | Chain config edge cases |
| `infrastructure/nvm/contracts/factory.py` | **90%** | 114-116 | Factory error path |
| `infrastructure/nvm/config.py` | **94%** | 93, 99, 108, 120 | NVM config branches |
| `cli/validators.py` | **92%** | 54, 79, 83 | Validator edge cases |
| `utils/validators.py` | **95%** | 126, 208-210 | Validator edge cases |
| `domain/execution/client_executor.py` | **73%** | 66-78, 115, 123 | Client executor paths |
| `domain/execution/agent_executor.py` | **91%** | 104, 141, 149 | Agent executor edge cases |
| `services/subscription_service.py` | **96%** | 98, 161 | Subscription edge cases |
| `services/setup_service.py` | **97%** | 180-182 | Setup edge case |
| `domain/subscription/manager.py` | **97%** | 179, 270 | Subscription manager edge cases |
| `domain/subscription/agreement.py` | **98%** | 125 | Agreement edge case |
| `domain/delivery/offchain_watcher.py` | **98%** | 87 | Offchain watcher edge case |
| `infrastructure/config/loader.py` | **93%** | 49 | Loader edge case |

## Priority Order for Test Writing

1. **`utils/errors/handlers.py`** (37%, 69 lines) — Used everywhere; validates all error formatting
2. **`services/marketplace_service.py`** (46%, 77 lines) — Core request flow
3. **`domain/delivery/onchain_watcher.py`** (26%, 71 lines) — Critical async delivery logic
4. **`cli/common.py`** (47%, 27 lines) — Shared wallet command setup
5. **`infrastructure/ipfs/metadata.py`** (23%, 27 lines) — IPFS upload/hash
6. **`infrastructure/operate/key_manager.py`** (25%, 18 lines) — Keyfile decryption
7. **`infrastructure/operate/manager.py`** (36%, 25 lines) — Operate service management
8. **`domain/payment/nvm.py`** (37%, 29 lines) — NVM payment flows
9. **`infrastructure/nvm/contracts/did_registry.py`** (35%, 15 lines) — DID registry
10. **`domain/payment/native.py`** (71%, 6 lines) — Native payment execution
11. **`domain/payment/token.py`** (70%, 16 lines) — Token payment execution
