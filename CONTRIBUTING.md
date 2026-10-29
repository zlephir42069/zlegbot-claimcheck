# Contributing

Thanks for looking at claimcheck. Keep changes small, and cover them with tests.

## Setup

Python 3.10 or newer. The runtime dependencies are the standard library and PyYAML.

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

Tests are offline. HTTP is monkeypatched, and a fixture fails the test if one opens a socket. `url_status` reaches the network only when someone runs `claimcheck run`.

## Guidelines

- Do not add secrets, tokens, or personal data to the repo, tests, fixtures, or examples.
- URLs and command strings belong in environment variables referenced as `${NAME}` when they carry a secret. Anything new that prints a result has to pass through the redactor.
- A claims file is trusted. `command_exit` runs the shell command. Do not turn that into a sandbox story, and do not execute commands while validating.
- `claimcheck run` exits 0 only when every claim is PASS. FAIL and ERROR are both non-zero. Keep evaluating the rest of the file.
- Prefer a clear claim field over a new feature. The summary counts claims that were actually checked.
