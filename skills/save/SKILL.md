---
name: save
description: Salvar conteúdo da conversa no vault Obsidian (second brain). Use com "/save", "salve no vault", "anote no vault", "registre isso". Decide tipo, pasta e formato; escreve com o tool Write; hooks validam e recompilam o index.
---

# Save no vault

O usuário escolheu o que preservar. Seu trabalho é julgamento: o que, onde e como. A validação é dos hooks, não sua.

1. **O quê**: destile o conteúdo aprovado (decisão, análise, sessão). Não despeje transcript.
2. **Onde** (pasta canônica em `wiki/`): sessão/snapshot em `sources/` (nome `Sessao YYYY-MM-DD <tema>.md`), decisão/conceito em `concepts/`, contrato/pendência viva em `areas/`, pessoa em `people/`. ANTES de criar, busque no basic-memory se já existe página para atualizar. Update vence create.
3. **Como**: frontmatter universal (`type,title,created,updated,tags,status`, sem nested objects), wikilinks `[[Assim]]`, filename Title Case.
4. **Ledger** (páginas de `areas/` com registros datados): inserir o registro na posição cronológica correta, consolidar com a seção existente do mesmo período, atualizar título de seção que cite período. Regra completa: CLAUDE.md do vault, seção "Ledgers e páginas datadas". Nunca append cego no fim.
5. **log.md**: adicione a entrada nova NO TOPO (`## [YYYY-MM-DD] Título`), corpo antigo intocado.
6. **hot.md**: se o fato muda o contexto quente, reescreva o hot.md INTEIRO (contrato de 500 palavras; skill hot-cache).

Não rode compile-index manualmente; o hook recompila sozinho.
