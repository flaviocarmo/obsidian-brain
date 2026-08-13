# Changelog

All notable changes to this project are documented here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [0.10.0] - 2026-08-13

### Added
- **The compiled index doubles as a per-topic map.** Headings now follow the full folder path (`## domains/infra (28)`) instead of only the top level, so `brain extract index --heading "domains/infra (28)"` returns one theme for ~600 tokens. Before, the smallest loadable slice of `domains` was a single 5.2k-token block mixing infrastructure with business and platforms — which meant the cheapest way to get the infra map was to load everything, and the honest advice was to load nothing.
- **`brain lint` flags bloated pages** (info, >12k estimated tokens, `contracts/` excluded since ledgers are long by design). A page nobody can scan is a page nobody updates, and it drags the whole file into context when one section was wanted.
- **Host → address drift detection** (`brainlib/endpoints.py`, warning). The existing contradiction check joins pages on strong identifiers; a whole class of fact has none and drifts silently — `dbt8` at one address here and another there after a host is rebuilt. It reports both sides with their `updated` dates and never picks a winner.

### Notes
- The drift rule is deliberately narrow, because a noisy linter teaches people to ignore the linter. Session pages (`type: source`) are excluded — a dated record saying "dbt6 was 20.0.0.31" stays true forever. A line needs a single address, stated the way an address is stated (backticks, a port, an `@`, a URL, or wording about hosts), and a name within 80 characters of it. First run against a 564-page vault produced 7 findings of which ~5 were junk: version strings like `1.1.0.15` parsing as IPv4, and `v8`/`e2e`/`route53` picked up as hostnames. With the rule tightened it reports **zero** — and a mutation test (injecting `dbt8` at a wrong address into the real page set) still catches it, which is the check that separates a precise rule from a dead one.

## [0.9.0] - 2026-08-13

### Added
- **Codex CLI support.** `brain install-codex` copies the skills into `~/.agents/skills/` and merges the hooks into `~/.codex/hooks.json`, preserving handlers that belong to other tools. Re-running is idempotent *and* self-healing: our entries are identified by script name, so changing the interpreter or moving the repo refreshes them instead of leaving a stale twin pointing at the old copy.
- `hooks/hook_payload.py`: one adapter both agents share. Claude Code names the file (`tool_input.file_path`); Codex edits through `apply_patch` and puts the patch text in `tool_input.command`, so the touched paths have to be read out of the `*** Add/Update/Delete File:` envelope (plus `*** Move to:`), resolved against the payload's `cwd`. The validator now checks *every* file a patch touches, not one.

- **`brain doctor` reports stale Codex copies.** The install writes a manifest (`~/.agents/skills/.obsidian-brain-install.json`) with the version, repo path and interpreter it used, because a copy has no way of announcing that it is three versions behind — the skills keep working, the old way. The check flags a version mismatch, an install made from a different clone, and hooks whose command still points at another path. Never fatal: not using Codex is a valid state, and the check says so.

### Notes
- Codex **silently skips hooks it has not been shown**: no error at the call site, the write simply lands unvalidated. After installing (or after any upgrade that changes a hook definition, which resets its trust) you must run `/hooks` in the Codex TUI. `codex exec` will not run them even with `--dangerously-bypass-hook-trust`. Documented in the README because it is invisible from inside the tool.
- Hook commands are pinned to an absolute interpreter path — `python` does not necessarily resolve in the environment Codex runs hooks in.

## [0.8.2] - 2026-08-13

### Fixed
- **The log validator called every legitimate append tampering.** `wiki/log.md` opens with a `# Operations Log` title and new entries go *under* it, so the previous body is not a suffix of the new one — and the check hashed the whole body. Every write since the state was last written was blocked; because a `PostToolUse` hook reports rather than reverts, the entries landed anyway, nobody read the message in the headless digest runs, and the stored baseline froze. The comparison now starts at the first `## ` heading, skipping the file's fixed prologue. The state gained a `version` field, and a state in the old shape re-baselines instead of blocking. The test fixture's log had no title at all, which is why the suite never saw this.

## [0.8.1] - 2026-08-13

### Fixed
- **The digest wrote a file in the vault root.** Transcripts are full of talk about *other* files — a `MEMORY.md`, a README, a config — and an unattended model reads that as an instruction: the first live run created `MEMORY.md` at the vault root, which no validator caught because the write hook only inspects paths under `wiki/`. The prompt now states the write scope positively (only `wiki/journal/*.md` and `wiki/log.md`) and says outright that files discussed in the transcript are subject matter, not instructions.

### Added
- A post-run scope check compares a file snapshot taken before the model runs against the vault afterwards and reports anything touched outside journal and log. It reports rather than deletes: content is never destroyed by a heuristic, and a stray page in the vault root is otherwise invisible until someone trips over it.

## [0.8.0] - 2026-08-13

### Fixed
- **The digest no longer digests itself.** `brain digest` runs a headless `claude -p`, whose Stop hook is the very hook that fills the queue, so every run enqueued its own session and the next day wrote a journal page about the previous day's digest — forever, one wasted LLM run per day. The child is now marked with `BRAIN_DIGEST=1` and the capture hook returns early when it sees it. Verified end to end: a headless run with the marker leaves the queue untouched.

### Added
- The daily run recompiles `wiki/index.md` after consolidating. The `PostToolUse` hook only fires for pages an agent writes with Write/Edit; anything typed straight into Obsidian left the index stale until someone remembered to run `brain compile-index`. No LLM involved in this step.
- **The daily run also refreshes `wiki/hot.md`** from the pages it just wrote, in a second short call on `sonnet` — the hot cache is the file every session reads first, and choosing which 500 words survive is curation, not summarising. The rewrite is validated against the contract and **rolled back to the previous version if it breaks it**: the PostToolUse validator can report a bad write but never undoes it, which is fine when a human is watching and useless at 22:00. The superseded version is appended to `wiki/folds/hot-cache-archive-<year>-Q<n>.md`. `--skip-hot` opts out.

## [0.7.0] - 2026-08-10

### Fixed
- **Frontmatter validation now rejects YAML comment markers.** `#` outside quotes opens a comment, so `tags: [#deploy, #ci]` is a flow sequence that never closes. The regex reader accepted it; downstream YAML parsers did not, and basic-memory "repaired" the page by prepending a second frontmatter block, leaving three digest-generated pages with two stacked blocks and every required key reported missing. Detection walks the line tracking quote state (a quote may stay open across folded lines), so `title: "NF #1130"`, `issue #200` inside a quoted list item and `pagina#secao` all remain valid.
- The digest prompt now pins the exact frontmatter schema, including the no-`#` rule. Unattended writes cannot rely on the model inferring the format.

### Notes
- Root cause of a real incident: the scheduled digest ran successfully (exit 0, 3 sessions consolidated) and produced three invalid pages that nobody was told about. The validator gap is the defect — fixing only the pages would have left tonight's run free to repeat it.

## [0.6.1] - 2026-08-09

### Fixed
- Duplicate detection discarded tokens of two characters or fewer, which silently removed the ordinals and counters (`3a`, `5a`, `dia-1`) that are often the *only* thing distinguishing two titles. Pages renamed precisely to disambiguate them still came back flagged at 100%. Tokens containing a digit are now always kept.

## [0.6.0] - 2026-08-09

### Added
- **Near-duplicate page detection** in `brain lint` (severity `info`): titles are tokenised and compared with Jaccard similarity inside each top-level folder, reporting pairs at or above 75%. Dated session prefixes and the `email-scan` marker are stripped first, otherwise every session page looks alike; single-token titles are skipped.

### Notes
- Cross-folder pairs are deliberately NOT compared: a `journal/` session page and the `domains/` page that distils it are the intended pattern, not a duplicate. The 75% threshold was calibrated against a 527-page vault (0.85 → 3 pairs, 0.75 → 5, 0.55 → 10) and the folder restriction removed the only cross-kind false positive.

## [0.5.0] - 2026-08-09

### Added
- **Cross-page contradiction detection** in `brain lint`: pages are joined on strong identifiers (NF/OS/Fatura numbers) and a warning is raised when the more recently updated page still claims *pending* while an older page already claims *issued*. Both sides are reported with their `updated` dates; the tool never picks a winner.

### Notes
- A money-value comparison rule was implemented and **dropped after testing against a real vault**: gross, net and retention figures for the same invoice legitimately differ, and the rule produced 4x more findings than the status rule with no added signal. The recency guard exists for the same reason — "pending in May, issued in August" is progress, not a contradiction.

## [0.4.0] - 2026-08-09

### Added
- `brain doctor`: verifies every requirement before use (Python floor, vault reachable with `wiki/`, hooks installed, **basic-memory installed and with a project indexing the vault**). Exit 1 when a requirement is missing.

### Changed
- **basic-memory is now a hard requirement, not optional.** It is the search layer; silently degrading to grep produced worse answers with no signal. The `query` skill now surfaces the failure and points at `brain doctor` instead of quietly falling back.

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

[0.7.0]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.6.1...v0.7.0
[0.6.1]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/flaviocarmo/obsidian-brain/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/flaviocarmo/obsidian-brain/releases/tag/v0.1.0
