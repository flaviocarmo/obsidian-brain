# Changelog

All notable changes to this project are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [0.3.0] - 2026-08-09

### Added
- Automatic session capture: a `Stop` hook enqueues sessions into `.vault-meta/capture-queue.jsonl` (deterministic, zero LLM cost, consecutive stops collapse).
- `brain digest [--dry-run] [--model X]`: batches pending sessions into one headless `claude -p` run that writes `wiki/journal/` pages and a top log entry. Contract ledgers, hot cache and index remain out of the automatic path.

## [0.2.1] - 2026-08-09

### Added
- `decision` in the canonical `type` vocabulary (engineering decision records are a first-class page kind).

## [0.2.0] - 2026-08-09

### Changed
- **Data-derived taxonomy** replaces the inherited kind-of-note folders. Canonical content dirs are now `journal/` (dated session pages), `contracts/` (client/contract ledger pages), `domains/<subdomain>/` (technical knowledge clustered by what the data actually contains) and `people/`; `meta/` and `folds/` remain system dirs. Folder-by-note-kind duplicated the frontmatter `type` field and said nothing about the content.
- Ledger chronology validation now applies to `contracts/` (with `areas/` kept for backward compatibility).
- The `save` skill files pages into the new taxonomy.

## [0.1.1] - 2026-08-09

### Added
- First-use onboarding: with no vault configured, the CLI error now instructs Claude to ask the user for the vault folder and write `~/.claude/brain.json` before retrying.
- Bilingual README (EN-US and PT-BR) with install, usage, vault layout and hook contract.
- Credits section.

### Changed
- All documentation examples use neutral placeholder paths.

## [0.1.0] - 2026-08-09

Initial release.

### Added
- `brain.py` CLI (pure stdlib, Python 3.11+, Windows-native): `extract` (token-estimated TOC and per-heading section retrieval, fence-aware), `validate` (frontmatter schema, hot-cache word budget, compiled-index guard, append-at-top log contract with persisted state, `.raw/` immutability, ledger chronology warnings), `lint` (dead wikilinks, orphans, schema, empty sections, stale markers, index freshness), `compile-index`, `hot-check`, `fold` (log rollup into monthly archives, dry-run by default, pre-apply backup).
- Two `PostToolUse` hooks: write validation with block feedback to the model, and debounced automatic index recompilation. Hook failures never break the session.
- Six skills (pt-BR): `query`, `save`, `ingest`, `lint`, `fold`, `hot-cache`.
- Restricted-YAML frontmatter parser with folded-line support; UTF-8-safe subprocess handling for accented filenames.
- 81 pytest tests, cp1252-console safe.

[0.3.0]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/flaviocarmo/obsidian-brain/releases/tag/v0.1.0
