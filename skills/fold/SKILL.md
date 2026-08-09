---
name: fold
description: Compactar o log.md do vault movendo entradas antigas para arquivos mensais em wiki/folds/. Use com "fold the log", "compacta o log", "arquiva o log".
---

# Fold do log

1. Preview: `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" fold` (dry-run; mostra quantas entradas ficam e quantas vão para cada `log-archive-YYYY-MM.md`).
2. Mostre o resumo ao usuário.
3. SÓ com aprovação: `... fold --apply`. O apply reescreve o log.md e atualiza o estado de validação sozinho.
