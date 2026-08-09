# obsidian-brain — Design

Data: 2026-08-07. Status: aprovado em sessão (brainstorming com Flavio).

## Problema

O vault Obsidian (Windows, sync via Dropbox) roda sobre o plugin `claude-obsidian` 2.1.0, que nunca foi re-adotado após a v1.6.0: sem `.claude-obsidian.json`, sem `mode.json`, sem ledgers. O motor de transação exige WSL (recusa escrita em Windows nativo), o retrieval próprio (`retrieve.py`) nunca foi provisionado e perdeu para o basic-memory na análise diferencial de 2026-08-07, e 3 das 4 capacidades "degraded" no relatório são falso positivo de encoding/plataforma Windows. O uso real dos últimos 3 meses é: escrita via tool Write, busca via basic-memory, disciplina de schema em prosa de CLAUDE.md — sem rede de proteção. Adaptar/fatiar o plugin upstream é trabalho recorrente sem retorno.

Gargalo medido em uso real (consulta financeira de contrato, 2026-08-07): a busca acerta a página em 1º lugar, mas a leitura é tudo-ou-nada. A maior página de área do vault tem 251 KB (~65k tokens) e não há extrator de seção.

## Decisão

Substituir o `claude-obsidian` por plugin próprio **obsidian-brain**: 100% Windows nativo, taxonomia Modo D existente preservada, retrieval via basic-memory, disciplina determinística em código testado (não em prosa), skills carregando apenas julgamento de LLM.

Decisões de clarificação (registradas em sessão):

| Tema | Decisão |
|---|---|
| Escopo v1 | Núcleo (save, query, ingest) + manutenção (lint, fold, hot-cache). Sem canvas, autoresearch, skills de referência |
| Modelo de escrita | Write direto + validação por hook PostToolUse. Sem staging/transação |
| Empacotamento | Repo próprio `C:\drive-d\projetos\obsidian-brain`, instalado como marketplace local |
| Hooks | Validador de escrita + recompilação automática do index. Sem SessionStart, sem sync forçado do basic-memory |
| Cutover | Corte limpo: desinstala `claude-obsidian` no v1 |
| Arquitetura | Opção B: um CLI `brain.py` com toda operação determinística; skills só com julgamento |

Racional da opção B: o histórico de bugs do vault (hot.md appendado, index.md editado à mão, ledger fora de ordem cronológica) é inteiro de disciplina determinística, e disciplina determinística em prosa de skill degrada; em código testado, não.

## Layout do repo

```
C:\drive-d\projetos\obsidian-brain\
├── .claude-plugin/
│   ├── plugin.json              # nome, versão, hooks declarados
│   └── marketplace.json         # marketplace local de 1 plugin
├── skills/
│   ├── save/SKILL.md
│   ├── query/SKILL.md
│   ├── ingest/SKILL.md
│   ├── lint/SKILL.md
│   ├── fold/SKILL.md
│   └── hot-cache/SKILL.md
├── scripts/
│   ├── brain.py                 # CLI único, stdlib-only, Python >= 3.11
│   └── brain/                   # frontmatter.py, extract.py, validate.py,
│                                #   lint.py, index.py, fold.py
├── hooks/
│   ├── validate-write.py        # PostToolUse Write|Edit
│   └── recompile-index.py       # PostToolUse Write|Edit em wiki/
├── tests/                       # pytest, Windows nativo
└── README.md
```

- Instalação: `claude plugin marketplace add <path do repo>` + `claude plugin install`. Upgrade = commit.
- Config: `~/.claude/brain.json` com `{"vault": "C:\\path\\to\\vault"}`. Nada de path hardcoded. Hooks usam o mesmo arquivo para decidir escopo (Write fora do vault = no-op).
- **Stdlib pura.** Sem PyYAML: o frontmatter do vault é YAML restrito por schema (sem nested objects, decisão do Obsidian Properties UI), parser próprio de ~60 linhas cobre e é testável. Sem dependência = sem passo de install.

## CLI `brain.py` — subcomandos

Todos leem o vault de `~/.claude/brain.json`. Saída em stdout; exit code 0 = ok, 1 = violação, 2 = erro de uso. Texto compacto por padrão, `--json` onde outra máquina consome.

### `brain extract <página> [--heading "X"] [--toc] [--level N]`

O extrator de seção — ataca o gargalo de leitura. `--toc` lista headings com estimativa de tokens por seção; `--heading` devolve só a seção (case-insensitive, aceita prefixo); sem argumento devolve a página inteira se <8k tokens, senão devolve o TOC e instrui a pedir seção. Resolve página por título, permalink ou path relativo. É o passo pós-`search_notes` da skill query.

### `brain validate <arquivo>`

Chamado pelo hook a cada Write/Edit no vault:

- Frontmatter presente e no schema universal (`type/title/created/updated/tags/status`), sem nested objects, `updated` coerente.
- `hot.md`: ≤500 palavras, sem seção "anterior".
- `index.md`: **bloqueia sempre** (é compilado; só passa com `--by-brain`) — exit 1 com mensagem que o hook repassa ao Claude.
- `log.md`: permitido **só append no topo** — o conteúdo anterior deve ser sufixo exato do novo (após o frontmatter); qualquer edição no miolo bloqueia.
- Ledger (páginas de `wiki/areas/` e afins): heurística de append cego — registro datado novo depois do registro mais recente, no fim do arquivo = **aviso**, não bloqueio.

### `brain lint [--json] [--write]`

Checks determinísticos: wikilinks mortos, páginas órfãs, frontmatter inválido, seções vazias, snapshots datados velhos / `[!stale]` vencido, hot.md fora do contrato, index desatualizado vs filesystem. `--write` grava relatório em `wiki/meta/lint-report.md`; sem flag, só stdout.

### `brain compile-index`

Migração do `_scripts/compile_index.py` do vault, mesma saída. Debounce via `.vault-meta/index-dirty`: hook marca dirty; recompila no próximo hook se >30s desde a última compilação (evita recompilar 15× num ingest).

### `brain hot-check`

Contrato do hot.md isolado (≤500 palavras, estrutura, sem seções "anterior"). Usado por `validate` e pela skill hot-cache.

### `brain fold [--dry-run|--apply]`

Rollup extrativo do `log.md` para `wiki/folds/`. Dry-run é o default; `--apply` move de verdade.

## Skills — o julgamento em prosa

Todas em pt-BR, curtas, referenciam o CLAUDE.md do vault como contrato-mestre (uma fonte para a regra de ledger, não três). Triggers preservam os atuais (`/save`, "ingest X", "lint the wiki", "query o vault").

- **query** — fluxo: `hot.md` → `search_notes` (basic-memory MCP; fallback CLI `basic-memory tool search-notes`; fallback Grep) → `brain extract --toc` na página grande → `brain extract --heading` na seção. Regras de evidência herdadas do wiki-query que sobrevivem: citar `[[Página#Heading]]`, distinguir evidência de inferência, declarar conflito entre páginas sem escolher vencedor calado (caso canônico: um snapshot antigo e a página de área divergindo sobre o status de duas notas fiscais; a resposta apresenta os dois com data de atualização). Morre a instrução de claim-ledger — sem ledger fantasma.
- **save** — decide o que preservar, tipo de nota, pasta canônica; regra de ledger (inserção cronológica, consolidação de seção, título de período atualizado) por referência ao CLAUDE.md do vault. Escreve com Write; validador de hook cobre o resto; compile-index acontece via hook, zero passo manual.
- **ingest** — source em `.raw/` → páginas atômicas com provenance no frontmatter `sources:`; update-não-duplica (buscar no basic-memory antes de criar página). Batch = loop do single.
- **lint** — roda `brain lint --json`, interpreta, propõe fixes; aplicar é operação separada aprovada.
- **fold** — `brain fold --dry-run`, preview, `--apply` só com aprovação.
- **hot-cache** — sobrescrever inteiro, ≤500 palavras; arquivar versão anterior em `wiki/folds/hot-cache-archive-*.md` antes (LLM faz o archive, `brain hot-check` confirma o resultado).

## Hooks — mecânica e erro

### validate-write (PostToolUse, matcher `Write|Edit`)

Lê o JSON do evento em stdin, extrai `file_path`; fora do vault → exit 0 imediato (~50ms de custo em sessão normal). No vault → `brain validate <arquivo>`. Violação bloqueante → feedback pro Claude no turno ("hot.md com 612 palavras, contrato é 500 — corrija"). PostToolUse não desfaz o write: o arquivo já mudou, o hook força correção imediata. Deliberado — rollback automático sobre Dropbox é mais perigoso que correção no turno seguinte.

### recompile-index (PostToolUse, paths `wiki/**`)

Toca `.vault-meta/index-dirty`, recompila com debounce de 30s. Falha de compilação nunca bloqueia: loga em `.vault-meta/brain.log` e segue — index é derivado, atraso não corrompe.

### Erros do próprio hook

Python quebrado, `brain.json` ausente: exit 0 com aviso em stderr uma vez por sessão. O hook de validação nunca pode ser o motivo de não conseguir escrever no vault — pior caso degrada pro comportamento atual (Write sem rede de proteção).

### Casos de borda do validate

- Arquivo novo sem frontmatter em `wiki/` = violação.
- Edit parcial que corrompe o YAML = violação.
- `_attachments/`, `_templates/`: fora do escopo de schema.
- `.raw/` imutável: criação ok, **edição de arquivo existente = violação**.
- Escritas legítimas do próprio brain em `index.md`/`log.md` (compile-index, fold --apply) passam por flag interna `--by-brain` via variável de ambiente no subprocess — não aceita do LLM.

## Testes

pytest, Windows nativo. Regra herdada do post-mortem do claude-obsidian: **nenhum print de caractere fora de ASCII em teste** — todo teste sobrevive a console cp1252 (3 dos 4 "degraded" do plugin antigo eram exatamente isso).

Fixtures: mini-vault em `tests/fixtures/vault/` com páginas boas e más (hot.md estourado, frontmatter nested, wikilink morto, ledger fora de ordem).

Cobertura obrigatória:

- frontmatter parser: round-trip (parse → serialize → parse idêntico);
- extract: heading com acento, heading duplicado, página de 251 KB real anonimizada;
- validate: cada regra com um caso que passa e um que bloqueia;
- debounce do compile-index;
- smoke de hook: invocar `validate-write.py` com JSON de evento real via stdin.

## Cutover (ordem importa)

1. Brain instalado, testes verdes, skills respondendo em sessão real.
2. `claude plugin uninstall claude-obsidian` — corte limpo, sem convivência.
3. CLAUDE.md do vault: seção "Skills e Comandos do Plugin" trocada pelos comandos do brain; remover referência ao "plugin claude-obsidian v1.6.0".
4. `_scripts/compile_index.py` do vault vira stub de 3 linhas chamando `brain compile-index` (não apagar — páginas do vault e o hot.md apontam pra ele).
5. `~/.claude/CLAUDE.md` global: seção "Vault Obsidian — Second Brain (Work)" atualizada (triggers `claude-obsidian:save` → skill save do brain).
6. Memória do projeto: [[claude_obsidian_vault_nunca_readotado]] ganha desfecho.

## Fora do escopo v1 (registrado, não esquecido)

- canvas, autoresearch, obsidian-bases/obsidian-markdown (referência);
- qualquer staging/transação;
- sync forçado do basic-memory pós-escrita (watcher resolve; se não resolver, hook no v1.1);
- suporte a segundo vault (`brain.json` já é extensível, nada implementado);
- CI remota (testes rodam local; job de CI se o repo ganhar remote).
