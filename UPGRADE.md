# Bump Python 3.10-3.14 Guide

Guide for bumping valory repos from open-aea 2.0.x / open-autonomy 0.21.x to open-aea 2.1.0 / open-autonomy 0.21.12 with Python 3.10-3.14 support.

## Version references

Use local repos for exact version pins:
- `/home/lockhart/work/valory/repos/open-aea/Pipfile`
- `/home/lockhart/work/valory/repos/open-autonomy/pyproject.toml`

## Pipfile vs pyproject.toml

Some repos (e.g. mech-interact) use `Pipfile`/`pipenv` instead of `pyproject.toml`/`poetry`. For these:
- Update `Pipfile` `[dev-packages]` instead of `pyproject.toml`
- Replace all `poetry run` / `poetry lock` / `poetry install` commands with:
  ```bash
  pipenv install --dev --skip-lock   # install deps
  pipenv run <command>               # or just run tox directly (tox manages its own venvs)
  ```
- The `[requires]` section pins `python_version = "3.10"` (the dev/CI Python); this does not restrict which Pythons tox tests against.

## Dependency bumps

### pyproject.toml / Pipfile

| Package | Old | New |
|---------|-----|-----|
| python | `<3.12,>=3.10` | `>=3.10,<3.15` |
| olas-operate-middleware | `0.14.16` | `0.15.0` |
| open-autonomy | 0.21.8 | 0.21.12rc4 |
| open-aea-ledger-ethereum | 2.0.8 | 2.1.0rc6 |
| open-aea-ledger-cosmos | 2.0.8 | 2.1.0rc6 |
| open-aea-cli-ipfs | 2.0.8 | 2.1.0rc6 |
| open-aea-test-autonomy | 0.21.8 | 0.21.12rc4 |
| tomte | 0.4.0 | 0.6.1 |
| pytest | 7.4.4 | 8.4.2 (tomte[tests] pins exact version) |
| pytest-asyncio | 0.18.0 | 1.3.0 (tomte[tests] pins exact version) |
| pytest-cov | 6.2.1 | 7.0.0 (tomte[tests] pins exact version) |
| pytest-randomly | 3.16.0 | 4.0.1 (tomte[tests] pins exact version) |
| protobuf | `<4.25.0,>=4.21.6` | `>=5,<6` |
| grpcio | 1.53.0 | 1.78.0 |
| pycryptodome | 3.18.0 | 3.20.0 |
| requests | `<2.32.5,>=2.28.1` | `>=2.28.1,<2.33.0` |
| openapi-core | 0.15.0 | 0.22.0 |
| openapi-spec-validator | `<0.5.0,>=0.4.0` | `<0.8.0,>=0.7.0` |
| jsonschema | `<4.4.0,>=4.3.0` | `>=4.23.0,<5.0.0` (required by openapi-core 0.22.0) |
| pyinstaller | 6.8.0 | 6.19.0 (6.8.0 doesn't support Python >=3.13) |
| typing_extensions | `<=4.13.2,>=3.10.0.2` | `>=3.10.0.2` (tomte 0.6.1 tox dep needs >=4.15) |
| certifi | pinned | `*` |
| hexbytes | pinned | `*` |
| urllib3 | pinned | remove |

### tox.ini additional deps (not in pyproject.toml)

| Package | Old | New |
|---------|-----|-----|
| click | `==8.1.8` | `>=8.1.0,<9` |
| pywin32 (tox win only) | 304 | ==311 (304 doesn't have wheels for Python 3.12+, 310 doesn't have 3.14 wheel) |
| certifi (tox win only) | pinned | unpinned |

### tox.ini tomte references

Update ALL `tomte[*]==0.4.0` references to `==0.6.1`. These appear in many envs:
- `[deps-tests]` — `tomte[tests]==0.6.1`
- `[testenv:bandit]` — `tomte[bandit]==0.6.1`
- `[testenv:black]` and `[testenv:black-check]` — `tomte[black]==0.6.1`
- `[testenv:isort]` and `[testenv:isort-check]` — `tomte[isort]==0.6.1`
- `[testenv:flake8]` — `tomte[flake8]==0.6.1` and `tomte[flake8-docstrings]==0.6.1`
- `[testenv:mypy]` — `tomte[mypy]==0.6.1`
- `[testenv:pylint]` — `tomte[pylint]==0.6.1`
- `[testenv:safety]` — `tomte[safety]==0.6.1`
- `[testenv:darglint]` — `tomte[darglint]==0.6.1`
- `[testenv:spell-check]` — `tomte[cli]==0.6.1`
- `[testenv:liccheck]` — `tomte[liccheck,cli]==0.6.1`
- `[testenv:check-generate-all-protocols]` — `tomte[isort]==0.6.1` and `tomte[black]==0.6.1`

### tox.ini check-hash env
```ini
[testenv:check-hash]
deps =
    open-autonomy[all]==0.21.12rc4
```

## Tox 4 compatibility (tomte 0.6.1 pulls tox 4)

### `whitelist_externals` -> `allowlist_externals`
Renamed in tox 4. Search-and-replace all occurrences in `tox.ini`.

### Scripts need `allowlist_externals`
Any tox env that runs scripts directly must declare them. Common ones:
```ini
[testenv:check-doc-hashes]
allowlist_externals = {toxinidir}/scripts/check_doc_ipfs_hashes.py

[testenv:fix-doc-hashes]
allowlist_externals = {toxinidir}/scripts/check_doc_ipfs_hashes.py

[testenv:check-dependencies]
allowlist_externals = {toxinidir}/scripts/check_dependencies.py
```

### `extras = all` breaks if no extras defined
Tox 4 is strict -- remove `extras = all` from `[testenv]` if pyproject.toml doesn't define any extras.

### `pkg_resources` removed from setuptools
`liccheck` uses `pkg_resources`. Add `setuptools` as explicit dep:
```ini
[testenv:liccheck]
deps =
    tomte[liccheck,cli]==0.6.1
    setuptools
```

### Verbose `.pkg:` output
Tox 4 shows packaging steps by default. Add `-qq` to tox calls in Makefile:
```makefile
tox -qq -e spell-check
```
Note: `quiet` setting in tox.ini is CLI-only in tox 4, doesn't work in config.

### Test envlist
Update from `py{3.9,3.10,3.11}` to `py{3.10,3.11,3.12,3.13,3.14}`:
```ini
[tox]
envlist = ..., py{3.10,3.11,3.12,3.13,3.14}-{win,linux,darwin}
```

Add individual test envs for each new Python version x platform (3.12, 3.13, 3.14 for linux, win, darwin):
```ini
[testenv:py3.12-linux]
basepython = python3.12
platform=^linux$
deps = {[testenv-multi-ubuntu]deps}
commands = {[commands-packages]commands}

[testenv:py3.12-win]
basepython = python3.12
platform=^win32$
deps = {[testenv-multi-win]deps}
commands = {[commands-packages]commands}

[testenv:py3.12-darwin]
basepython = python3.12
platform=^darwin$
deps = {[testenv-multi-darwin]deps}
commands = {[commands-packages]commands}
```
Repeat pattern for 3.13 and 3.14.

## isort/black conflict

tomte 0.6.1 ships black 26.x which enforces 1 blank line after imports before module-level variables. Change isort config to let black decide:
```ini
[isort]
lines_after_imports=-1
```

Also add `I004` to the flake8 ignore list. flake8-isort raises `I004` (missing blank line after imports) which now conflicts with black 26.x managing that spacing:
```ini
[flake8]
ignore = ...,I004
```

If you don't ignore `I004`, `tox -e flake8` will fail on any file where black added the blank line after imports.

## Test compatibility (open-aea 2.1.0)

### `BaseSkillTestCase` changes
- No longer sets default `path_to_skill` -- must be set explicitly as class attribute
- `setup` renamed to `setup_method` (per-test setup hook)
- `setup_class` signature unchanged but must call `super().setup_class(**kwargs)`

Example:
```python
class TestMyBehaviour(BaseSkillTestCase):
    path_to_skill = PACKAGE_DIR  # must set explicitly

    @classmethod
    def setup_class(cls, **kwargs):
        kwargs["config_overrides"] = {...}
        super().setup_class(**kwargs)

    def setup_method(self, **kwargs):  # was: def setup(self, **kwargs)
        super().setup_method(**kwargs)
        self.behaviour.setup()
```

### `BaseContractTestCase` changes
- No longer sets default `path_to_contract` and `ledger_identifier`
- `setup` renamed to `setup_class`

## Package hash sync

### How it works
Third-party packages in your repo's `packages/packages.json` must match hashes from the source-of-truth repo (open-autonomy). The `dev` packages in open-autonomy become the `third_party` packages in downstream repos.

### Obtaining the source hashes

If you have the open-autonomy repo checked out locally, point `SOURCE_PACKAGES_JSON` at it. Otherwise fetch directly from GitHub:
```bash
curl -s https://raw.githubusercontent.com/valory-xyz/open-autonomy/v0.21.12rc4/packages/packages.json \
  > /tmp/open_autonomy_packages.json
```
Then set `SOURCE_PACKAGES_JSON = Path("/tmp/open_autonomy_packages.json")`.

Alternatively, run the script logic mentally: the `dev` and `third_party` entries in open-autonomy's `packages.json` are the correct hashes for your repo's `third_party` section.

### Step 1: Create `scripts/compare_hashes.py`

```python
#!/usr/bin/env python3
"""Compare package hashes between source-of-truth and target repos."""

import json
from pathlib import Path

# Source of truth: open-autonomy dev packages
SOURCE_PACKAGES_JSON = Path("divyanautiyal/open-autonomy/packages/packages.json")

# Target: this repo's packages.json
TARGET_PACKAGES_JSON = Path("packages/packages.json")

# Alternatives for other repos:
# SOURCE_PACKAGES_JSON = Path("/home/lockhart/work/valory/repos/agent-academy-1/packages/packages.json")
# TARGET_PACKAGES_JSON = Path("/home/lockhart/work/valory/repos/mech/packages/packages.json")


def main() -> None:
    """Compare hashes."""
    with open(SOURCE_PACKAGES_JSON) as f:
        source = json.load(f)
    with open(TARGET_PACKAGES_JSON) as f:
        target = json.load(f)

    # Source dev packages = target third_party packages
    source_dev = source.get("dev", {})
    source_third = source.get("third_party", {})
    # Merge both sections as potential sources
    source_all = {**source_third, **source_dev}

    target_third = target.get("third_party", {})

    mismatches = []
    for pkg, target_hash in target_third.items():
        if pkg in source_all:
            source_hash = source_all[pkg]
            if target_hash != source_hash:
                mismatches.append((pkg, target_hash, source_hash))

    if not mismatches:
        print("All hashes match!")
        return

    print(f"Found {len(mismatches)} mismatched hashes:\n")
    for pkg, old, new in mismatches:
        print(f'  "{pkg}": "{new}",')
    print(f"\nReplace these in {TARGET_PACKAGES_JSON}")


if __name__ == "__main__":
    main()
```

### Step 2: Run the script
```bash
python scripts/compare_hashes.py
```

### Step 3: Update hashes in `packages/packages.json`
Copy the output hashes into packages.json, replacing the old values.

### Step 4: Sync packages
```bash
autonomy packages sync --update-packages
```
This downloads updated package files from IPFS to match the new hashes. For Pipfile repos run directly (tox envs have their own venvs; if system autonomy version is old, run via `tox -e check-hash` which installs the correct version).

### Step 5: Relock dev fingerprints
```bash
autonomy packages lock
```
After syncing, the third-party files on disk have changed. This re-fingerprints the `dev` packages (e.g. `mech_interact_abci`) whose YAML fingerprint lists reference the updated third-party packages.

### Step 6: Verify
```bash
tox -qq -e check-hash
tox -qq -e check-packages
```

## Safety vulnerabilities

Add new ignore IDs as they appear. Known ones for this bump:
```
-i 83159  # marshmallow CVE-2025-68480
```

Full safety command example:
```ini
commands = safety check -i 37524 -i 38038 -i 37776 -i 38039 -i 39621 -i 40291 -i 39706 -i 41002 -i 51358 -i 51499 -i 67599 -i 70612 -i 83159
```

## CI workflow

Update test matrix in the relevant workflow file (e.g. `.github/workflows/main_workflow.yml` or `common_checks.yaml` depending on the repo):
```yaml
python-version: ["3.10", "3.11", "3.12", "3.13", "3.14"]
```

Also update all `tomte[tox*]==0.4.0` → `==0.6.1` in the workflow's install steps, and remove any `pip install setuptools==60.10.0` lines (no longer needed with tox 4 + modern setuptools).

### Lock check failure: tomte[tests] version conflicts

`tomte==0.6.1` pins exact versions for all test deps via its `tests` extra. Any mismatch causes `pipenv lock` (and `pipenv install`) to fail. The full set of exact versions required:

| Package | Old | New (tomte 0.6.1) |
|---------|-----|-----|
| pytest | 7.4.4 | 8.4.2 |
| pytest-asyncio | 0.18.0 | 1.3.0 |
| pytest-cov | 6.2.1 | 7.0.0 |
| pytest-randomly | 3.16.0 | 4.0.1 |
| pytest-rerunfailures | — | 16.1 |

Fix in `tox.ini` `[deps-tests]` and `Pipfile`:
```ini
pytest==8.4.2
pytest-asyncio==1.3.0
pytest-cov==7.0.0
pytest-randomly==4.0.1
```

### Lock check failure: upgrade pipenv in CI

`pipenv==2023.7.23` fails to lock when the dependency tree includes `open-aea-test-autonomy`, which pulls in `open-aea[all]`. The `open-aea[all]` extra pins `packaging==26`, which conflicts with pipenv 2023's own internal use of `packaging<24`.

Fix: upgrade the CI pipenv version:
```yaml
- name: Install dependencies
  run: |
    pip install pipenv==2024.4.1
```

### Copyright headers

Any file you reformat (e.g. via `tox -e black`) will have its modification year updated to the current year. If the file's copyright header still has the old year, `tomte check-copyright` will fail.

Fix: run `tomte format-copyright` with the same `--exclude-part` flags used by `check-copyright` after any reformatting pass.

### liccheck: pkg_resources not found with setuptools>=82

`setuptools>=82` dropped `pkg_resources` as a top-level module. `liccheck` still imports it, so the env fails immediately.

Fix: pin setuptools in `[testenv:liccheck]`:
```ini
deps =
    tomte[liccheck,cli]==0.6.1
    setuptools<=81.0.0
```

### liccheck: PSF-2.0 not authorized

`typing-extensions 4.15.0` reports its license as `PSF-2.0`, which is not in the authorized list (only `PSF` and `Python Software Foundation` were there). Fix: add `PSF-2.0` to `authorized_licenses` in `[liccheck]`:
```ini
PSF-2.0
```

### liccheck: editable install appears as `unknown (0.0.0): UNKNOWN`

When `usedevelop = True`, tox installs the repo itself into the liccheck env. Since there is no `setup.py`/`pyproject.toml` with a license field, `pip freeze` outputs it as `UNKNOWN @ file:///...` and liccheck fails on it.

Fix: change `usedevelop = True` → `skip_install = True` in `[testenv:liccheck]`. liccheck only needs the dep tree frozen, not the local package itself:
```ini
[testenv:liccheck]
skipsdist = True
skip_install = True
```

### check-security: bandit B113

bandit 1.9.x (shipped by tomte 0.6.1) added check B113 (`request_without_timeout`). Any `requests.get()` / `requests.post()` call without a `timeout=` argument will fail the scan.

Fix: add B113 to the skip list for the scripts scan in `[testenv:bandit]`:
```ini
commands = bandit -s B101 -r packages
           bandit -s B101,B113 -r scripts
```
If the call is in `packages/`, either add a timeout or add `# nosec B113` inline.

## Classifiers

Add to pyproject.toml:
```toml
"Programming Language :: Python :: 3.11",
"Programming Language :: Python :: 3.12",
"Programming Language :: Python :: 3.13",
"Programming Language :: Python :: 3.14",
```

## Files to modify (checklist)

1. `pyproject.toml` or `Pipfile` -- deps, python constraint, classifiers
2. `tox.ini` -- deps, envlist, test envs, all tomte versions, tox 4 compat (allowlist, extras, setuptools, scripts), add `I004` to flake8 ignore
3. `.github/workflows/main_workflow.yml` (or `common_checks.yaml`) -- test matrix, tomte version, remove pinned setuptools
4. `packages/packages.json` -- sync third-party hashes from open-autonomy, then run `autonomy packages sync --update-packages && autonomy packages lock`
5. `Makefile` -- add `-qq` to all `tox -e` calls
6. Test files -- `setup` -> `setup_method` / `setup_class` (BaseSkillTestCase / BaseContractTestCase)
7. `scripts/compare_hashes.py` -- create hash comparison script

## Verification order

1. Install deps:
   - pyproject.toml repos: `poetry lock && poetry install`
   - Pipfile repos: `pipenv install --dev --skip-lock`
2. `python scripts/compare_hashes.py` -- check hash alignment against upstream
3. Update hashes in `packages/packages.json`, then:
   ```bash
   autonomy packages sync --update-packages  # download updated package files
   autonomy packages lock                    # re-fingerprint dev packages
   ```
4. `tox -qq -e black` and `tox -qq -e isort` -- auto-format, then run `tomte format-copyright --author valory ...` to fix year in any reformatted file's header
5. `tox -qq -e flake8,mypy` -- linting
6. `tox -qq -e py3.10-linux` -- unit tests (adjust platform suffix for your OS: `-darwin`, `-win`)
7. `tox -qq -e safety` -- add ignore IDs as needed
8. `tox -qq -e liccheck` -- add `setuptools` dep if pkg_resources error
9. `tox -qq -e spell-check` -- should work
10. `tox -qq -e check-hash` -- verify all package fingerprints
11. `tox -qq -e check-packages` -- verify package dependency consistency