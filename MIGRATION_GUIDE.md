# CLI Migration Guide - Breaking Changes

## Overview

The `mechx` CLI has been restructured with a cleaner command organization using nested command groups. This is a **breaking change** - all old command names have been removed and replaced with a new hierarchical structure.

## Why These Changes?

The old flat structure had:
- Inconsistent naming (`fetch-mm-mechs-info`, `tools-for-marketplace-mech`)
- Very long command names (up to 38 characters)
- Poor discoverability (12 commands in a flat list)
- No logical grouping

The new structure provides:
- **Logical grouping** by domain (mech, tool, deposit, subscription, ipfs)
- **Shorter commands** (average 7 characters shorter)
- **Self-documenting** through command groups
- **Better discoverability** via `mechx <group> --help`
- **Industry-standard patterns** (follows `gh`, `aws`, `kubectl` conventions)

## Command Mapping

### Setup & Configuration

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `mechx setup-agent-mode` | `mechx setup` | Shorter, clearer name |

### Main Interaction

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `mechx interact` | `mechx request` | More descriptive of action |

### Mech Operations

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `mechx fetch-mm-mechs-info` | `mechx mech list` | Grouped under `mech`, uses standard verb `list` |

### Tool Management

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `mechx tools-for-marketplace-mech` | `mechx tool list` | 18 chars shorter |
| `mechx tool-description-for-marketplace-mech` | `mechx tool describe` | 24 chars shorter |
| `mechx tool-io-schema-for-marketplace-mech` | `mechx tool schema` | 27 chars shorter |

### Deposits & Payments

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `mechx deposit-native` | `mechx deposit native` | Grouped under `deposit` |
| `mechx deposit-token` | `mechx deposit token` | Grouped under `deposit` |
| `mechx purchase-nvm-subscription` | `mechx subscription purchase` | Grouped under `subscription` |

### IPFS Utilities

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `mechx push-to-ipfs` | `mechx ipfs upload` | Grouped under `ipfs`, shorter |
| `mechx prompt-to-ipfs` | `mechx ipfs upload-prompt` | Grouped under `ipfs`, clearer |
| `mechx to-png` | `mechx ipfs to-png` | Grouped under `ipfs` |

## Migration Examples

### Example 1: Setup Agent Mode

**Before:**
```bash
mechx setup-agent-mode --chain-config gnosis
```

**After:**
```bash
mechx setup --chain-config gnosis
```

### Example 2: Send Request to Mech

**Before:**
```bash
mechx interact --prompts "Summarize this" --tools openai-gpt-4 --chain-config gnosis
```

**After:**
```bash
mechx request --prompts "Summarize this" --tools openai-gpt-4 --chain-config gnosis
```

### Example 3: List Available Mechs

**Before:**
```bash
mechx fetch-mm-mechs-info --chain-config gnosis
```

**After:**
```bash
mechx mech list --chain-config gnosis
```

### Example 4: List Tools for a Mech

**Before:**
```bash
mechx tools-for-marketplace-mech 1 --chain-config gnosis
```

**After:**
```bash
mechx tool list 1 --chain-config gnosis
```

### Example 5: Get Tool Description

**Before:**
```bash
mechx tool-description-for-marketplace-mech 1-openai-gpt-4 --chain-config gnosis
```

**After:**
```bash
mechx tool describe 1-openai-gpt-4 --chain-config gnosis
```

### Example 6: Get Tool Schema

**Before:**
```bash
mechx tool-io-schema-for-marketplace-mech 1-openai-gpt-4 --chain-config gnosis
```

**After:**
```bash
mechx tool schema 1-openai-gpt-4 --chain-config gnosis
```

### Example 7: Deposit Native Tokens

**Before:**
```bash
mechx deposit-native 1000000000000000000 --chain-config gnosis
```

**After:**
```bash
mechx deposit native 1000000000000000000 --chain-config gnosis
```

### Example 8: Deposit ERC20 Tokens

**Before:**
```bash
mechx deposit-token 1000000000000000000 --chain-config gnosis
```

**After:**
```bash
mechx deposit token 1000000000000000000 --chain-config gnosis
```

### Example 9: Purchase NVM Subscription

**Before:**
```bash
mechx purchase-nvm-subscription --chain-config gnosis
```

**After:**
```bash
mechx subscription purchase --chain-config gnosis
```

### Example 10: Upload File to IPFS

**Before:**
```bash
mechx push-to-ipfs ./myfile.json
```

**After:**
```bash
mechx ipfs upload ./myfile.json
```

### Example 11: Upload Prompt to IPFS

**Before:**
```bash
mechx prompt-to-ipfs "Summarize this text" "openai-gpt-4"
```

**After:**
```bash
mechx ipfs upload-prompt "Summarize this text" "openai-gpt-4"
```

### Example 12: Convert to PNG

**Before:**
```bash
mechx to-png Qm... ./output.png 12345
```

**After:**
```bash
mechx ipfs to-png Qm... ./output.png 12345
```

## New Command Structure

```
mechx
├── setup                      # Setup agent mode
├── request                    # Send AI request to mech
├── mech                       # Mech operations group
│   └── list                   # List mechs
├── tool                       # Tool operations group
│   ├── list                   # List tools
│   ├── describe               # Get tool description
│   └── schema                 # Get tool I/O schema
├── deposit                    # Deposit operations group
│   ├── native                 # Deposit native tokens
│   └── token                  # Deposit ERC20 tokens
├── subscription               # Subscription operations group
│   └── purchase               # Purchase NVM subscription
└── ipfs                       # IPFS utilities group
    ├── upload                 # Upload file to IPFS
    ├── upload-prompt          # Upload prompt metadata
    └── to-png                 # Convert to PNG
```

## Discovering Commands

The new structure makes it easy to explore available commands:

```bash
# See all top-level commands
mechx --help

# See all mech operations
mechx mech --help

# See all tool operations
mechx tool --help

# See all deposit operations
mechx deposit --help

# See all subscription operations
mechx subscription --help

# See all IPFS operations
mechx ipfs --help
```

## Migration Strategy

### For Scripts and Automation

1. **Search and replace** old command names with new ones
2. **Test** all scripts with the new commands
3. **Update documentation** and README files

### For CI/CD Pipelines

1. **Update** all `mechx` commands in CI/CD workflows
2. **Pin** to the new version (v0.17.0+) to avoid breakage
3. **Test** pipelines before deploying

### For Users

1. **Update** any aliases or wrapper scripts
2. **Re-learn** command names (they're shorter and more intuitive!)
3. **Use** `mechx <group> --help` to discover commands

## Benefits of New Structure

1. **Consistency**: All commands follow `mechx <group> <verb>` pattern
2. **Brevity**: Commands are significantly shorter
3. **Discoverability**: `mechx tool --help` shows all tool commands
4. **Scalability**: Easy to add new commands to existing groups
5. **Standards**: Follows patterns from popular CLIs (gh, aws, kubectl)
6. **Self-documenting**: Command structure makes purpose clear

## Common Issues

### "Command not found" Error

**Problem:**
```bash
$ mechx setup-agent-mode --chain-config gnosis
Error: No such command 'setup-agent-mode'.
```

**Solution:**
Use the new command name:
```bash
$ mechx setup --chain-config gnosis
```

### "Agent mode not set up" Error

**Problem:**
The error message might reference the old command name in some places.

**Solution:**
Use `mechx setup` (not `mechx setup-agent-mode`) to set up agent mode.

## Getting Help

- **Main help**: `mechx --help`
- **Command group help**: `mechx <group> --help`
- **Specific command help**: `mechx <group> <command> --help`
- **Issues**: https://github.com/valory-xyz/mech-client/issues

## Feedback

We believe this new structure is a significant improvement. If you have feedback or suggestions, please open an issue on GitHub.
