# obsidian-brain

A [Claude Code](https://claude.com/claude-code) plugin that turns an [Obsidian](https://obsidian.md) vault into a reliable second brain: direct writes guarded by validation hooks, retrieval powered by [basic-memory](https://github.com/basicmachines-co/basic-memory), and a single dependency-free CLI for everything deterministic. Built Windows-first, works everywhere Python runs.

**[English](#english) · [Português](#português-brasil)**

---

## English

### Why

LLM-maintained knowledge bases fail in predictable ways: the hot-context file grows past its budget, compiled indexes get edited by hand, chronological ledger pages receive blind appends, and huge pages get loaded whole into context when only one section matters. obsidian-brain moves that discipline out of prompt prose and into tested code, then lets the model do only what models are good at: judgment.

- **Write directly, validate immediately.** Claude writes with its normal Write/Edit tools. A `PostToolUse` hook validates every write inside the vault and feeds violations straight back to the model, which fixes them in the next turn. No staging area, no transaction engine, safe for vaults synced by Dropbox/OneDrive/Syncthing because nothing ever rolls files back behind your back.
- **Near-duplicate detection.** Two pages about the same thing are worse than one: updates land on a copy and queries return the stale one. Titles are compared within each folder (a session page and the concept page it distils are the intended pattern, not a duplicate).
- **Contradiction detection.** Pages accrete, and two of them end up disagreeing about the same invoice or work order. The linter joins pages on strong identifiers and reports the pair when the *newer* page still says pending while an older one says issued. It never picks a winner: both sides are reported with their `updated` dates.
- **Section extractor for big pages.** Real vaults grow 250 KB ledger pages. `brain extract` returns a token-estimated table of contents, then just the section you ask for, fence-aware (headings inside code blocks are not headings).
- **Search stays external, and required.** basic-memory indexes the vault locally (FTS + vector, zero LLM tokens); this plugin implements what comes after search, not search itself. `brain doctor` fails loudly when it is missing, because silent degradation to grep is worse than an error.
- **Everything deterministic is code with tests.** 136 pytest tests, Windows-native, cp1252-console safe, pure stdlib.

### Requirements

- Python 3.11+ (no packages needed, stdlib only)
- Claude Code with plugin and hook support
- An Obsidian vault (or any folder of Markdown with YAML frontmatter)
- **[basic-memory](https://github.com/basicmachines-co/basic-memory) (required)** — the search layer, with a project pointing at your vault:
  `uv tool install basic-memory` · `basic-memory project add <name> "<vault path>"` · `claude mcp add basic-memory -- basic-memory mcp`

### Install

```
claude plugin marketplace add <path-or-git-url-of-this-repo>
claude plugin install obsidian-brain@obsidian-brain-marketplace
```

On first use, Claude notices there is no vault configured and asks you where it lives, then writes `~/.claude/brain.json` for you. You can also create it yourself:

```json
{ "vault": "C:\\path\\to\\YourVault" }
```

The `BRAIN_VAULT` environment variable overrides the file when set. Start a new Claude Code session and the skills and hooks are live.

Check the install with `python <plugin>/scripts/brain.py doctor` — it verifies Python, the vault, the hooks, and that basic-memory is installed **and** has a project indexing your vault. Exit code 1 means a requirement is missing.

### Vault layout (data-derived taxonomy)

Structure follows the data, not note kinds (note kind already lives in frontmatter `type`):

```
YourVault/
├── .raw/          # immutable sources (the validator blocks edits to existing files)
├── wiki/
│   ├── hot.md     # hot context, 500-word budget, always overwritten whole
│   ├── index.md   # compiled catalog, never hand-edited (a hook recompiles it)
│   ├── log.md     # append-only log, newest entry on top
│   ├── journal/   # dated session pages (time series)
│   ├── contracts/ # living client/contract pages treated as chronological ledgers
│   ├── domains/   # technical knowledge clustered by your real domains (subfolders)
│   ├── people/
│   ├── meta/      # lint reports
│   └── folds/     # archives (old log entries, old hot caches)
```

Every wiki page carries frontmatter: `type`, `title`, `created`, `updated`, `tags`, `status` (with a small canonical vocabulary), no nested objects.

### Use it through skills (inside Claude Code)

| Say | Skill | What happens |
|---|---|---|
| "query the vault: ..." | `query` | hot.md, then basic-memory search, then `extract --toc`/`--heading` on big pages; answers cite `[[Page#Heading]]` |
| `/save` or "save this to the vault" | `save` | picks note type and folder, updates instead of duplicating, inserts ledger records in chronological position |
| "ingest file.md" | `ingest` | source goes to `.raw/`, becomes atomic pages with provenance |
| "lint the wiki" | `lint` | runs the deterministic linter (including cross-page contradictions and near-duplicates), interprets, proposes fixes (applying is a separate approval) |
| "fold the log" | `fold` | dry-run of the log rollup into monthly archives; `--apply` only after approval |
| "update hot cache" | `hot-cache` | archives the current hot.md, rewrites it whole within the 500-word budget |

### Use it from any shell (CLI)

```
python <plugin>/scripts/brain.py extract "Some Big Page" --toc
python <plugin>/scripts/brain.py extract "Some Big Page" --heading "Invoices 2026"
python <plugin>/scripts/brain.py validate path/to/page.md
python <plugin>/scripts/brain.py lint --json
python <plugin>/scripts/brain.py compile-index
python <plugin>/scripts/brain.py hot-check
python <plugin>/scripts/brain.py fold            # dry-run; add --apply to execute
python <plugin>/scripts/brain.py doctor          # check requirements (basic-memory included)
```

Exit codes: 0 ok, 1 violation found, 2 usage or config error.

### What the hooks enforce

- Frontmatter present and on schema for every wiki page
- `hot.md` at 500 words or less, no "previous" sections
- `index.md` untouchable by hand (and recompiled automatically after writes, 30 s debounce)
- `log.md` accepts new entries at the top only; editing history is blocked
- `.raw/` files are immutable once created
- Ledger pages out of chronological order get a warning
- A hook failure never breaks the session: worst case degrades to a plain write

### Automatic session capture (optional)

A `Stop` hook enqueues every Claude Code session (zero LLM cost) into `.vault-meta/capture-queue.jsonl`. A daily batch then turns the queue into `wiki/journal/` pages:

```
python <plugin>/scripts/brain.py digest --dry-run   # list what is pending
python <plugin>/scripts/brain.py digest             # one headless claude run digests the batch
python <plugin>/scripts/brain.py digest --skip-hot  # ... and leave hot.md alone
```

After consolidating, the run rewrites `wiki/hot.md` from the pages it just wrote (a second, short call on a stronger model, since 500 words of hot context are curation, not summarising) and recompiles `wiki/index.md`. If the rewritten hot cache breaks the 500-word contract the previous version is restored and the run says so — the validation hook can report a bad write but cannot undo it. The superseded hot cache is appended to `wiki/folds/hot-cache-archive-<year>-Q<n>.md`.

Schedule it (Windows example):

```
schtasks /Create /F /SC DAILY /ST 22:00 /TN obsidian-brain-digest /TR "cmd /c python C:\path\to\repo\scripts\brain.py digest >> C:\path\to\vault\.vault-meta\digest.log 2>&1"
```

The automatic path writes journal pages, a log entry, the hot cache and the index; contract ledgers stay curated (manual `/save`).

### Development

```
python -m pytest -v      # 136 tests, Windows-native
```

Design spec and implementation plan live in [`docs/superpowers/`](docs/superpowers/).

---

## Português (Brasil)

### Por quê

Bases de conhecimento mantidas por LLM falham de formas previsíveis: o arquivo de contexto quente estoura o orçamento, o índice compilado é editado à mão, páginas de ledger cronológico recebem appends cegos e páginas enormes entram inteiras no contexto quando só uma seção importa. O obsidian-brain tira essa disciplina da prosa de prompt e a coloca em código testado, deixando para o modelo só o que modelo faz bem: julgamento.

- **Escreve direto, valida na hora.** O Claude escreve com Write/Edit normais. Um hook `PostToolUse` valida cada escrita no vault e devolve a violação ao modelo, que corrige no turno seguinte. Sem staging, sem motor de transação, seguro para vault em Dropbox/OneDrive/Syncthing porque nada faz rollback de arquivo pelas suas costas.
- **Detecção de quase-duplicatas.** Duas páginas sobre a mesma coisa são piores que uma: a atualização cai numa cópia e a busca devolve a outra. Títulos são comparados dentro de cada pasta (página de sessão e a página de domínio que ela destila são o padrão desejado, não duplicata).
- **Detecção de contradições.** Páginas crescem por acréscimo e duas acabam discordando sobre a mesma NF ou OS. O linter junta páginas por identificadores fortes e reporta o par quando a página *mais recente* ainda diz pendente e uma mais antiga já diz emitida. Nunca escolhe vencedor: mostra os dois lados com as datas `updated`.
- **Extrator de seção para páginas grandes.** Vault real cria páginas de ledger de 250 KB. `brain extract` devolve um sumário com estimativa de tokens por seção e depois só a seção pedida, ciente de code fences (heading dentro de bloco de código não é heading).
- **Busca fica de fora, e é obrigatória.** O basic-memory indexa o vault localmente (FTS + vetorial, zero tokens de LLM); este plugin implementa o que vem depois da busca, não a busca. O `brain doctor` falha alto quando ele falta, porque degradar para grep em silêncio é pior que erro.
- **Tudo que é determinístico é código com teste.** 136 testes pytest, Windows nativo, seguro em console cp1252, stdlib pura.

### Requisitos

- Python 3.11+ (sem pacotes, só stdlib)
- Claude Code com suporte a plugins e hooks
- Um vault Obsidian (ou qualquer pasta de Markdown com frontmatter YAML)
- **[basic-memory](https://github.com/basicmachines-co/basic-memory) (obrigatório)** — é a camada de busca, com um projeto apontando para o vault:
  `uv tool install basic-memory` · `basic-memory project add <nome> "<caminho do vault>"` · `claude mcp add basic-memory -- basic-memory mcp`

### Instalação

```
claude plugin marketplace add <path-ou-url-git-deste-repo>
claude plugin install obsidian-brain@obsidian-brain-marketplace
```

No primeiro uso, o Claude percebe que não há vault configurado, pergunta onde ele fica e grava o `~/.claude/brain.json` por você. Também dá para criar à mão:

```json
{ "vault": "C:\\caminho\\para\\SeuVault" }
```

A variável de ambiente `BRAIN_VAULT` tem precedência quando definida. Abra uma sessão nova do Claude Code e as skills e hooks estarão ativos.

Confira a instalação com `python <plugin>/scripts/brain.py doctor` — verifica Python, vault, hooks e se o basic-memory está instalado **e** com projeto indexando o vault. Exit 1 = requisito faltando.

### Layout do vault (taxonomia derivada do dado)

O mesmo da seção em inglês: `.raw/` imutável; `wiki/` com `hot.md` (500 palavras, sobrescrito inteiro), `index.md` (compilado, nunca à mão), `log.md` (append no topo), `journal/` (sessões datadas), `contracts/` (ledgers cronológicos de cliente/contrato), `domains/` (conhecimento por domínio real, em subpastas) e `people/`. A estrutura segue o dado; o tipo da nota já vive no frontmatter `type/title/created/updated/tags/status`, sem objetos aninhados.

### Uso por skills (dentro do Claude Code)

| Diga | Skill | O que acontece |
|---|---|---|
| "query o vault: ..." | `query` | hot.md, busca basic-memory, `extract --toc`/`--heading` em página grande; resposta cita `[[Página#Heading]]` |
| `/save` ou "salve no vault" | `save` | decide tipo e pasta, atualiza em vez de duplicar, insere registro de ledger na posição cronológica |
| "ingest arquivo.md" | `ingest` | source vai para `.raw/` e vira páginas atômicas com proveniência |
| "lint the wiki" | `lint` | roda o linter determinístico, interpreta, propõe fixes (aplicar é aprovação separada) |
| "fold the log" | `fold` | dry-run do rollup do log em arquivos mensais; `--apply` só com aprovação |
| "update hot cache" | `hot-cache` | arquiva o hot.md atual e o reescreve inteiro dentro das 500 palavras |

### Uso por CLI (qualquer shell)

Os mesmos comandos da seção em inglês: `extract`, `validate`, `lint`, `compile-index`, `hot-check`, `fold`. Exit codes: 0 ok, 1 violação, 2 erro de uso ou config.

### O que os hooks garantem

Frontmatter no schema em toda página; `hot.md` dentro do contrato de 500 palavras; `index.md` intocável à mão (e recompilado sozinho, debounce de 30 s); `log.md` só aceita entrada nova no topo; `.raw/` imutável; ledger fora de ordem cronológica gera aviso. Falha de hook nunca quebra a sessão: o pior caso degrada para uma escrita simples.

### Captura automática de sessões (opcional)

Um hook `Stop` enfileira toda sessão do Claude Code (custo zero de LLM) em `.vault-meta/capture-queue.jsonl`. Um lote diário transforma a fila em páginas de `wiki/journal/`:

```
python <plugin>/scripts/brain.py digest --dry-run   # lista o que está pendente
python <plugin>/scripts/brain.py digest             # uma execução headless digere o lote
python <plugin>/scripts/brain.py digest --skip-hot  # ... sem mexer no hot.md
```

Depois de consolidar, a execução reescreve o `wiki/hot.md` a partir das páginas que acabou de escrever (segunda chamada, curta, em modelo mais forte: 500 palavras de contexto quente são curadoria, não resumo) e recompila o `wiki/index.md`. Se o hot reescrito estourar o contrato de 500 palavras, a versão anterior é restaurada e a execução avisa — o hook de validação denuncia a escrita ruim, mas não a desfaz. O hot substituído é anexado em `wiki/folds/hot-cache-archive-<ano>-Q<n>.md`.

Agendamento (exemplo Windows): `schtasks /Create /SC DAILY /ST 22:00 ...` como na seção em inglês. O caminho automático escreve journal, log, hot cache e index; ledgers de contrato continuam curadoria manual (`/save`).

### Desenvolvimento

```
python -m pytest -v      # 136 testes, Windows nativo
```

Spec de design e plano de implementação em [`docs/superpowers/`](docs/superpowers/).

---

## Credits / Créditos

Inspired by / Inspirado pelo [claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian), by [AgriciDaniel](https://github.com/AgriciDaniel) (MIT).
