# claimcheck

An agent can say the work is done and be wrong. Checking that report with another model spends another turn on a question a program can answer. claimcheck reads a claims file and compares each claim to the filesystem, a command's exit code, or one HTTP status. It prints PASS, FAIL, or ERROR. It does not call a model.

The claims file is the input you trust. `claimcheck validate` checks the file shape and does not open paths, run commands, or use the network. `claimcheck run` does the checks. `claimcheck extract` only turns a plain-text report into a starter file for you to review.

claimcheck is one of the tools at [github.com/zlephir42069](https://github.com/zlephir42069). [wakegate](https://github.com/zlephir42069/zlegbot-wakegate) decides whether to start an agent. claimcheck runs after the agent says it is finished.

## 60-second quickstart

Requires Python 3.10+.

```bash
python -m pip install -e .
printf 'hello\n' > note.txt
cat > claims.yaml << 'EOF'
claims:
  - name: note
    type: file_exists
    path: note.txt
  - name: greeting
    type: file_contains
    path: note.txt
    pattern: hello
EOF
claimcheck validate claims.yaml
claimcheck run claims.yaml
claimcheck run claims.yaml --json
claimcheck extract examples/report.txt -o starter.yaml
```

`python -m claimcheck` is the same entry point. `claimcheck validate claims.example.yaml` checks the checked-in example. That example's hash and URL are placeholders, so `run` on it is not a demo that passes.

## Config reference

A claims file is YAML or JSON. `.json` is parsed as JSON. `.yaml` and `.yml` are YAML. Any other suffix is JSON when the first non-space character is `{` or `[`, and YAML otherwise. A top-level list is treated as `claims`.

Paths inside claims are relative to `root`. `root` is relative to the claims file's directory. The default root is that directory. `--root` overrides it and is relative to the current working directory. Absolute claim paths stay absolute. `command_exit` uses `root` as its working directory.

| Setting | Default | Meaning |
| --- | --- | --- |
| `root` | the claims file's directory | Base for relative paths and for `command_exit`. |
| `timeout` | `30` | Seconds for `url_status` and `command_exit` when a claim does not set its own. A duration such as `30s` or `1m` is also accepted. |
| `claims` | required | List of claims. At least one. |

Every claim needs `name` and `type`. `name` matches `[A-Za-z0-9][A-Za-z0-9_.-]{0,63}`. Names are unique.

`${NAME}` anywhere in a string is replaced from the environment when the file loads. A referenced variable that is unset is a file error. `$${NAME}` becomes a literal `${NAME}` so a shell command can keep its own variable. Values taken from variables whose names look like URLs, tokens, or passwords are redacted from the table and from `--json`. Incoming-webhook URLs are redacted even when they were written out in full. Do not commit secrets. Put them in the environment.

Quote patterns, hashes you do not want YAML to rewrite, and timestamps. YAML 1.1 may turn `yes`, `no`, and some bare timestamps into booleans or datetimes. A timestamp used as `equals` must be quoted or it is rejected.

`claimcheck validate` exits non-zero with one message per problem. It does not contact the network and it does not run commands.

Exit codes:

| Command | 0 | 1 | 2 |
| --- | --- | --- | --- |
| `run` | every claim is PASS | any FAIL or ERROR | bad claims file or bad usage |
| `validate` | the file is valid | — | bad claims file or bad usage |
| `extract` | the report was read | — | the report or the output could not be used |

`run` exits 0 only when every claim passes. One FAIL does not skip the rest.

## Claims

Each check lives in its own module under `claimcheck/checks/`. A missing file is FAIL for every path check: the claim is not true. A permission error, a timeout, a directory where a file was required, invalid text, or a network failure is ERROR. The detail is one line. Command stdout is not printed.

Text, JSON, and line-count reads stop at 20 MB and return ERROR past that. `file_md5` hashes the file in chunks and has no size cap.

### `file_exists`

PASS when `path` exists. A directory passes. The detail says `file` or `directory`.

### `file_md5`

PASS when the MD5 of the file bytes equals `md5`. The expected value is 32 hex characters. Comparison ignores case. A directory is ERROR.

### `file_contains`

PASS when `pattern` matches the file somewhere. The pattern is a Python regular expression. `(?s)` makes `.` match newlines. `(?m)` makes `^` match line starts. The file must be UTF-8. A directory or a binary file is ERROR.

### `json_path_equals`

PASS when the value at `json_path` equals `equals`. `equals` is a JSON value: string, number, boolean, null, array, or object. `1` and `1.0` match. The string `"1"` does not match the number `1`. `true` does not match `1`.

`json_path` is either a JSON Pointer or a small dot path:

- `/version`, `/items/0/name`, `/a~1b` (the pointer encoding of the key `a/b`), `/` for the whole document
- `$.items[0].name`, `items[0].name`, `items.0.name`

A missing path is FAIL. A file that is not JSON is ERROR. Object key order does not matter.

### `line_count`

PASS when the file has at least `min_rows` lines. `splitlines` is the count, so a trailing newline does not add a line. Blank lines count unless `skip_blank` is true. A header line counts. `min_rows: 0` passes for an existing file, including an empty one. The type name `min_rows` is accepted and stored as `line_count`.

### `url_status`

PASS when a GET returns `status` (100 through 599). Redirects are not followed, so a `301` stays `301`. The body is not saved. This is the only check that uses the network, and only during `run`. Tests mock it. `timeout` overrides the file default. A timeout or a connection failure is ERROR. The URL has to be `http` or `https`.

### `command_exit`

PASS when `run` exits with `exit` (default `0`). Optional `stdout` is a Python regular expression that must match stdout. Stdout and stderr are not stored or printed. The claims file is trusted: the command runs through the shell, in `root`, so a command can change the machine. `validate` does not run it. A timeout is ERROR. `timeout` overrides the file default.

### `mtime_after`

PASS when the path's modification time is strictly later than `after`. `after` is an ISO-8601 timestamp with a timezone. A trailing `Z` is UTC. A naive timestamp is a file error. Equal timestamps FAIL.

## Output

`claimcheck run` prints a table. `result` is `PASS`, `FAIL`, or `ERROR`.

```
name      type          result  detail
--------  ------------  ------  ----------------------
note      file_exists   PASS    note.txt file exists
missing   file_exists   FAIL    missing.txt not found

2 claims: 1 passed, 1 failed, 0 errors
```

`claimcheck run claims.yaml --json` prints one object and no table. `ok` is true only when every claim is PASS.

```json
{
  "ok": false,
  "summary": {"total": 2, "passed": 1, "failed": 1, "errors": 0},
  "claims": [
    {"name": "note", "type": "file_exists", "result": "PASS", "detail": "note.txt file exists"},
    {"name": "missing", "type": "file_exists", "result": "FAIL", "detail": "missing.txt not found"}
  ]
}
```

The summary counts claims in this run. It is not a sample and it is not a cost.

## `claimcheck extract`

```bash
claimcheck extract report.txt
claimcheck extract report.txt -o starter.yaml
claimcheck extract - < report.txt
```

Extract reads a plain-text report and writes YAML. It does not open the paths and it does not decide PASS or FAIL. Review the file before you run it. With no `-o`, the YAML goes to stdout and the count goes to stderr. `-o` prints `wrote N claims to <path>`. Zero matches still exit 0 and write `claims: []`. A line whose first non-space character is `#` is ignored.

An MD5 is 32 hex digits. These lines become `file_exists` plus `file_md5`:

```
0123456789abcdef0123456789abcdef  notes/today.txt
0123456789abcdef0123456789abcdef *notes/today.txt
MD5 (README.md) = abcdef0123456789abcdef0123456789
md5 of src/app.py is 0123456789abcdef0123456789abcdef
checksum of data/out.csv is 0123456789abcdef0123456789abcdef
src/app.py md5: 0123456789abcdef0123456789abcdef
md5 0123456789abcdef0123456789abcdef for src/app.py
```

These become `file_exists` only:

- a path in backticks
- a path after `created`, `wrote`, `written`, `updated`, `added`, `modified`, `generated`, `saved`, `edited`, or `produced`
- `file:`, `path:`, or `output:` followed by a path
- a bare token with a common source or data extension, or an extensionless name such as `Makefile`, `Dockerfile`, `LICENSE`, or `README`

The extension list is `_EXTENSIONS` in `claimcheck/extract.py`. `http` and `https` URLs are masked first, so a link is not turned into a path. An address like `name@example.com` and a version like `1.2.3` are not paths. The same path is not emitted twice. `examples/report.txt` is a short report in this shape.

## CI

`examples/github-actions.yml` is a workflow you can copy. It validates the claims file, then runs it. Put tokens in the CI secret store. `actions/checkout` and `actions/setup-python` in that example are v7, matching this repo's own CI.

This repo's CI runs `pytest` on Python 3.10 and 3.13. The tests do not open a socket.

## How it saves credits

A follow-up model turn that re-reads the diff, re-hashes a file, or re-runs a test pays for work the process already finished. Point that step at `claimcheck run`. The process stats files, hashes bytes, counts lines, runs the command you named, or reads one HTTP status, then exits. The person or the next agent reads the table. What an avoided model turn would have cost depends on the model you would have called. claimcheck does not estimate it.

wakegate is the other half of that split. It spends no model call deciding whether to wake the agent. claimcheck spends no model call deciding whether the agent's report holds.

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

See `CONTRIBUTING.md`. The license is MIT, copyright zlephir42069.
