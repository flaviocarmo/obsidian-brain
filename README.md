# obsidian-brain

Plugin de [Claude Code](https://claude.com/claude-code) para operar um *second brain* em um vault [Obsidian](https://obsidian.md), **100% Windows nativo**. Escrita direta com validação por hook, busca via [basic-memory](https://github.com/basicmachines-co/basic-memory) e um CLI único (`brain.py`, stdlib pura) para tudo que é determinístico.

## Contexto

Este projeto substitui o uso do plugin `claude-obsidian` em um cenário específico e comum:

- **Windows nativo.** O motor de transação do `claude-obsidian` exige confinamento por descritor de diretório (WSL/Linux/macOS) e recusa escrita no vault em Windows. Na prática, a escrita acontecia pelo tool `Write` do Claude Code, sem rede de proteção nenhuma.
- **Vault no Dropbox, não em git.** Rollback automático em cima de sync de arquivos é mais perigoso que validação imediata com correção no turno seguinte. Por isso o modelo aqui é `Write` direto + hook `PostToolUse` que valida cada escrita e devolve a violação para o Claude corrigir na hora.
- **Retrieval via basic-memory.** O índice BM25/contextual do plugin antigo custa uma chamada de LLM por chunk para provisionar. O basic-memory indexa localmente (FTS + vetorial) a custo zero de tokens e resolveu melhor em teste real. Este plugin não implementa busca: implementa o que falta depois dela, um **extrator de seção por heading** para páginas grandes (páginas de área com 250 KB+ são realidade em vault de trabalho).
- **Disciplina em código, não em prosa.** O histórico de bugs do vault (hot cache estourando o contrato de 500 palavras, index compilado editado à mão, ledgers com registros fora de ordem cronológica) é todo de disciplina determinística. Prosa de skill degrada; código testado, não.

## Arquitetura

```
skills/    julgamento de LLM: save, query, ingest, lint, fold, hot-cache
scripts/   brain.py, CLI com toda operação determinística:
           extract | validate | lint | compile-index | hot-check | fold
hooks/     PostToolUse: valida cada Write/Edit no vault; recompila o index com debounce
tests/     pytest, Windows nativo, seguro para console cp1252
```

Taxonomia do vault: Modo D (*Second Brain*) com `wiki/` (concepts, areas, sources, people, goals, learning, resources, questions, meta), `hot.md` com contrato de 500 palavras sobrescrito por inteiro, `index.md` compilado (nunca editado à mão), `log.md` append-only no topo e páginas de área tratadas como ledgers cronológicos.

## Requisitos

- Windows 10/11 (funciona em Linux/macOS por consequência, não por meta)
- Python 3.11+ (stdlib pura, sem dependências)
- Claude Code com suporte a plugins e hooks
- [basic-memory](https://github.com/basicmachines-co/basic-memory) apontado para o vault (MCP ou CLI)
- Um vault Obsidian; sync por Dropbox/OneDrive/Syncthing é suportado porque nada aqui faz rollback de arquivo

## Instalação

```
claude plugin marketplace add <path-deste-repo>
claude plugin install obsidian-brain
```

Configuração em `~/.claude/brain.json`:

```json
{ "vault": "C:\\Users\\<user>\\Dropbox\\Apps\\obsidian\\<Vault>" }
```

## Status

Fase de design. Spec completa em [`docs/superpowers/specs/2026-08-07-obsidian-brain-design.md`](docs/superpowers/specs/2026-08-07-obsidian-brain-design.md).
