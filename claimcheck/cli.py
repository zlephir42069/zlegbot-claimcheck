"""Command line: run, validate, extract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claimcheck.errors import ConfigError
from claimcheck.redact import scrub


def main(argv=None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return 0 if code is None else int(code)

    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "run":
            return _run(args)
        if args.command == "extract":
            return _extract(args)
    except ConfigError as exc:
        prefix = "error" if getattr(args, "command", None) == "extract" else "config error"
        for message in exc.messages:
            print(f"{prefix}: {scrub(message)}", file=sys.stderr, flush=True)
        return 2
    except BrokenPipeError:
        return 0
    print("config error: unknown command", file=sys.stderr, flush=True)
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claimcheck",
        description="Check an agent's claims against files, command exits, and HTTP status.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="evaluate every claim and print PASS, FAIL, or ERROR")
    run_parser.add_argument("claims", help="path to the claims file (YAML or JSON)")
    run_parser.add_argument(
        "--json",
        action="store_true",
        help="print a JSON object instead of the text table",
    )
    run_parser.add_argument(
        "--root",
        help="directory claim paths and commands are relative to (overrides the file)",
    )

    validate_parser = sub.add_parser("validate", help="validate the claims file and exit")
    validate_parser.add_argument("claims", help="path to the claims file (YAML or JSON)")
    validate_parser.add_argument(
        "--root",
        help="directory claim paths are relative to (checked only as a path, not created)",
    )

    extract_parser = sub.add_parser(
        "extract",
        help="pull file paths and md5 sums from a plain-text report",
    )
    extract_parser.add_argument(
        "report",
        help="path to the report, or - to read stdin",
    )
    extract_parser.add_argument(
        "-o",
        "--output",
        help="write the starter claims here instead of stdout",
    )
    return parser


def _claim_count(count: int) -> str:
    noun = "claim" if count == 1 else "claims"
    return f"{count} {noun}"


def _validate(args) -> int:
    from claimcheck.config import load_config

    load_config(Path(args.claims), root=args.root)
    print("ok", flush=True)
    return 0


def _run(args) -> int:
    from claimcheck.config import load_config
    from claimcheck.run import execute

    config = load_config(Path(args.claims), root=args.root)
    return execute(config, as_json=args.json)


def _extract(args) -> int:
    from claimcheck.extract import extract_claims, render_claims

    if args.report == "-":
        text = sys.stdin.read()
        source = "stdin"
    else:
        path = Path(args.report)
        if not path.is_file():
            raise ConfigError(f"report not found: {path}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ConfigError("report is not utf-8 text") from exc
        except OSError as exc:
            raise ConfigError(f"could not read report: {exc.__class__.__name__}") from exc
        source = path.name
    claims = extract_claims(text)
    rendered = render_claims(claims, source)
    if args.output:
        dest = Path(args.output)
        try:
            dest.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            raise ConfigError(f"could not write claims: {exc.__class__.__name__}") from exc
        print(f"wrote {_claim_count(len(claims))} to {dest}", flush=True)
        return 0
    print(f"extracted {_claim_count(len(claims))}", file=sys.stderr, flush=True)
    sys.stdout.write(rendered)
    return 0
