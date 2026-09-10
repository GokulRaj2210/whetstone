# Finding the signal in an unfamiliar repo

Gate 2 says run the covering test before you edit. This is how to find it, and
what to do when there is not one.

## Locating the runner

Look for the declaration before guessing at a command:

| File | Command it implies |
|---|---|
| `pyproject.toml` with `[tool.pytest.ini_options]` | `python -m pytest` (or `uv run pytest` if `uv.lock` is present) |
| `tox.ini`, `pytest.ini`, `setup.cfg` `[tool:pytest]` | `python -m pytest` |
| `package.json` with a `scripts.test` | `npm test` — read what it actually runs first |
| `Makefile` with a `test:` or `check:` target | `make test` |
| `go.mod` | `go test ./...` |
| `Cargo.toml` | `cargo test` |

If a lockfile names an environment manager (`uv.lock`, `poetry.lock`), run
through it. Invoking a bare `pytest` that resolves to a different interpreter
produces import errors that look like code bugs and are not.

## Narrowing it

Run the smallest thing that covers the change, then widen:

```
python -m pytest tests/test_store.py::test_open_takes_the_lock   # the one
python -m pytest tests/test_store.py                             # the file
python -m pytest                                                 # the suite
```

The narrow run is for the edit loop, because it is fast enough to run after
every change. The wide run is for before you report, because that is where you
find out what else you broke.

## Finding the covering test

In order of reliability:

1. `Grep` the test tree for the symbol you are changing.
2. `Grep` for the filename's stem — `store.py` is usually `test_store.py`.
3. `Grep` for a distinctive string from the bug report or error message.
4. Read the test directory listing and look for the module by name.

If all four come up empty, there probably is no covering test — which is a fact
worth reporting, not a reason to skip the gate.

## When there is no test

Write the smallest one that fails for the right reason. It does not need to be
committed or beautiful; it needs to tell you whether your change worked.

```python
# scratch_check.py — delete before reporting, or offer it as a real test
from store import GraphStore


def test_open_does_not_deadlock():
    store = GraphStore.open(":memory:")
    store.open(":memory:")  # the second open used to hang
```

Run it. **Confirm it fails, and confirm it fails for the reason you expect.** A
test that errors on import is not yet evidence of the bug — fix the test until
its failure is the bug, then edit the code.

## When you genuinely cannot run anything

It happens: no runner, no interpreter, a service that is not up. Then say so
explicitly and precisely, in the report:

> Could not verify. `pyproject.toml` declares pytest but the environment has no
> `pytest` installed and no network to install it. The change is in
> `store.py:88`; to check it, run `python -m pytest tests/test_store.py -k lock`.

That is a useful report. "Fixed the deadlock" with no verification behind it is
not, and the two are indistinguishable to whoever reads them next.
