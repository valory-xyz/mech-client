# Contributing to Mech Client

Thank you for your interest in contributing to Mech Client! This guide will help you get started.

## Prerequisites

- Python >=3.10, <3.12
- [Poetry](https://python-poetry.org/) for dependency management
- Git

## Getting Started

1. **Fork and clone** the repository:

   ```bash
   git clone https://github.com/<your-username>/mech-client.git
   cd mech-client
   ```

2. **Install dependencies:**

   ```bash
   poetry install
   poetry shell
   ```

3. **Create a feature branch:**

   ```bash
   git checkout -b feat/your-feature
   ```

## Development Workflow

### Running Tests

```bash
poetry run pytest tests/unit/ -k "not trio"
```

### Running Linters

All linters **must pass** before opening a PR. The CI enforces a pylint score of 10.00/10.

```bash
# Run all checks at once
tox -e black-check,isort-check,flake8,mypy,pylint,bandit,darglint,vulture && tox -e liccheck
```

To auto-format your code:

```bash
tox -e black    # Code formatting
tox -e isort    # Import sorting
```

### Testing Documentation Locally

```bash
tox -e mkdocs-serve   # Starts dev server at http://127.0.0.1:8000/
tox -e mkdocs-build   # Builds static site to site/
```

## Code Style and Conventions

- **Type hints** are required on all functions (`mypy --disallow-untyped-defs`).
- **Formatting**: [Black](https://github.com/psf/black) for code style, [isort](https://pycqa.github.io/isort/) for import ordering.
- **Environment variables**: All env var access must go through `EnvironmentConfig` — never use `os.getenv()` directly.
- **Guard clauses**: Prefer early returns to reduce nesting.
- **Docstrings**: Use Google-style docstrings validated by darglint. Complex methods should include parameter descriptions and return types:

  ```python
  def some_method(some_arg: SomeType) -> ReturnType:
      """Do something with the given argument.

      :param some_arg: description of argument.
      :return: description of return value.
      """
  ```

## Creating a Pull Request

- **Target branch**: Ensure the PR is opened against the correct base branch.
- **Branch naming**: Use kebab-case with a prefix, e.g. `feat/some-feature`, `fix/some-bug`, `docs/update-readme`.
- **Link issues**: Reference the relevant ticket or issue in the PR description.
- **Label the PR**: Add appropriate labels such as `enhancement`, `bug`, or `test`.
- **Write a clear description**: Explain the purpose and context of the changes. Note any potential effects on other parts of the codebase.
- **Include tests**: PRs must contain tests for new or modified code. If the PR is submitted early for review, tests can follow before merge.
- **Code review**: Two reviewers will be assigned to each PR.

### PR Checklist

Before pushing, run through this in order:

```bash
# 1. Format code
tox -e black
tox -e isort

# 2. Run all linter checks
tox -e black-check,isort-check,flake8,mypy,pylint,bandit,darglint,vulture && tox -e liccheck

# 3. Run tests
poetry run pytest tests/unit/ -k "not trio"
```

## Project Structure

```
mech_client/
├── cli/             # Click CLI commands
├── services/        # Business logic (service layer)
├── domain/          # Domain models
├── infrastructure/  # Config, contracts, blockchain interaction
│   └── config/
│       └── environment.py  # EnvironmentConfig (single source of truth for env vars)
├── utils/           # Shared utilities and error handlers
└── configs/         # Chain and mech configuration (mechs.json)
```

The project follows a layered architecture (CLI -> Service -> Domain -> Infrastructure). See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) for details.

## Reporting Issues

- Use [GitHub Issues](https://github.com/valory-xyz/mech-client/issues) to report bugs or request features.
- Include steps to reproduce, expected behavior, and actual behavior.
- Mention the chain and RPC provider if the issue is network-related.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](./LICENSE).
