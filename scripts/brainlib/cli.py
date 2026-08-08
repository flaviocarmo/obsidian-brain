"""obsidian-brain CLI. Exit codes: 0 ok, 1 violation, 2 usage error."""

import argparse
import sys

COMMANDS = ("extract", "validate", "lint", "compile-index", "hot-check", "fold")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brain", description="obsidian-brain CLI")
    p.add_argument("--vault", help="override vault path (else BRAIN_VAULT or ~/.claude/brain.json)")
    sub = p.add_subparsers(dest="command")
    for name in COMMANDS:
        sub.add_parser(name)
    return p


def main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        args, _rest = build_parser().parse_known_args(argv)
    except SystemExit:
        return 2
    if not args.command:
        print("usage: brain <command>; commands: " + ", ".join(COMMANDS), file=sys.stderr)
        return 2
    if args.command not in COMMANDS:
        return 2
    print(f"{args.command}: not implemented yet", file=sys.stderr)
    return 2
