---
name: lint
description: Health check do vault Obsidian. Use com "lint the wiki", "lint o vault", "saúde do vault", "checa o vault". Roda o linter determinístico e interpreta; propor fix é separado de aplicar.
---

# Lint do vault

1. Rode: `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" lint --json`
2. Agrupe por severidade. `error` = quebra contrato (schema, hot.md); `warning` = degradação (link morto, seção vazia, index velho); `info` = revisão humana (órfã, [!stale]).
3. Interprete: separe o que é fix mecânico (rodar compile-index, corrigir frontmatter) do que exige decisão do usuário (órfã pode ser intencional).
4. Proponha os fixes. SÓ aplique após aprovação explícita. Relatório persistido: `... lint --write` grava `wiki/meta/lint-report.md`.
