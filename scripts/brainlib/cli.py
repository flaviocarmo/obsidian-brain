"""obsidian-brain CLI. Exit codes: 0 ok, 1 violation, 2 usage error."""

import argparse
import sys
from pathlib import Path

from . import config, extract

FULL_PAGE_TOKEN_LIMIT = 8000


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brain", description="obsidian-brain CLI")
    p.add_argument("--vault")
    sub = p.add_subparsers(dest="command")

    ext = sub.add_parser("extract")
    ext.add_argument("page")
    ext.add_argument("--heading")
    ext.add_argument("--toc", action="store_true")
    ext.add_argument("--level", type=int, default=None)

    val = sub.add_parser("validate")
    val.add_argument("file")
    val.add_argument("--by-brain", action="store_true")
    lint = sub.add_parser("lint")
    lint.add_argument("--json", action="store_true")
    lint.add_argument("--write", action="store_true")
    sub.add_parser("compile-index")
    sub.add_parser("hot-check")
    fold = sub.add_parser("fold")
    fold.add_argument("--apply", action="store_true")
    return p


def _cmd_extract(args) -> int:
    vault = config.vault_path(args.vault)
    try:
        path = extract.resolve_page(vault, args.page)
    except extract.ExtractError as e:
        print(f"extract: {e}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    if args.heading:
        parts = extract.get_sections(text, args.heading)
        if not parts:
            print(f"extract: heading not found: {args.heading!r}", file=sys.stderr)
            return 1
        print(f"\n{'-' * 8}\n".join(parts))
        return 0
    sections = extract.toc(text)
    if args.level:
        sections = [s for s in sections if s.level <= args.level]
    if args.toc or extract.estimate_tokens(text) >= FULL_PAGE_TOKEN_LIMIT:
        rel = path.as_posix()
        print(f"# TOC: {path.stem} ({extract.estimate_tokens(text)} tokens estimados)")
        for s in sections:
            print(f"{'  ' * (s.level - 1)}- {s.title} (~{s.tokens} tokens)")
        if not args.toc:
            print(f"\nPagina grande. Use: brain extract \"{path.stem}\" --heading \"<titulo>\"")
        return 0
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    try:
        args = build_parser().parse_args(argv)
    except SystemExit:
        return 2
    try:
        if args.command == "extract":
            return _cmd_extract(args)
        if args.command == "validate":
            from . import validate as validate_mod
            vault = config.vault_path(args.vault)
            report = validate_mod.validate_file(vault, Path(args.file), by_brain=args.by_brain)
            for w in report.warnings:
                print(f"WARN: {w}")
            for e in report.errors:
                print(f"ERROR: {e}")
            return 0 if report.ok else 1
        if args.command == "compile-index":
            from . import index as index_mod
            print(index_mod.compile(config.vault_path(args.vault)))
            return 0
        if args.command == "hot-check":
            from . import validate as validate_mod
            hot = config.vault_path(args.vault) / "wiki" / "hot.md"
            errors = validate_mod.check_hot(hot.read_text(encoding="utf-8")) if hot.exists() else []
            for e in errors:
                print(f"ERROR: {e}")
            if not errors:
                print("hot.md ok")
            return 0 if not errors else 1
        if args.command == "lint":
            import json as jsonlib
            from . import lint as lint_mod
            vault = config.vault_path(args.vault)
            findings = lint_mod.run(vault)
            if args.json:
                print(jsonlib.dumps([f.to_dict() for f in findings], ensure_ascii=True, indent=1))
            else:
                for f in findings:
                    print(f"{f.severity.upper()}: {f.path}: {f.message}")
                print(f"{len(findings)} findings")
            if args.write:
                out = vault / "wiki" / "meta" / "lint-report.md"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(lint_mod.report_markdown(findings), encoding="utf-8")
            return 1 if any(f.severity == "error" for f in findings) else 0
    except config.ConfigError as e:
        print(f"config: {e}", file=sys.stderr)
        return 2
    if not args.command:
        print("usage: brain <command>", file=sys.stderr)
        return 2
    print(f"{args.command}: not implemented yet", file=sys.stderr)
    return 2
