---
name: hot-cache
description: Atualizar o wiki/hot.md do vault (contexto quente, contrato de 500 palavras). Use com "update hot cache", "atualiza o hot", "refresh do hot.md".
---

# Hot cache

Contrato: `wiki/hot.md` tem NO MÁXIMO 500 palavras e é SOBRESCRITO por inteiro. Nunca existe seção "anterior".

1. Arquive a versão atual: append do conteúdo (sem frontmatter) em `wiki/folds/hot-cache-archive-<YYYY-Qn>.md` (crie com frontmatter `type: meta` se não existir).
2. Reescreva `wiki/hot.md` inteiro: seções `## Last Updated` (parágrafo único do estado atual), `## Key Recent Facts` (fatos datados, 1 linha cada), `## Active Threads` (pendências vivas). Poder de síntese: o que saiu do hot continua acessível via busca.
3. Confira: `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" hot-check` (exit 0 = dentro do contrato).
