---
name: lint
description: Health check do vault Obsidian. Use com "lint the wiki", "lint o vault", "saúde do vault", "checa o vault". Roda o linter determinístico e interpreta; propor fix é separado de aplicar.
---

# Lint do vault

1. Rode: `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" lint --json`
2. Agrupe por severidade. `error` = quebra contrato (schema, hot.md); `warning` = degradação (link morto, seção vazia, index velho); `info` = revisão humana (órfã, [!stale]).
3. Interprete: separe o que é fix mecânico (rodar compile-index, corrigir frontmatter) do que exige decisão do usuário (órfã pode ser intencional).
4. **Conflitos** (mensagens `conflito em <NF|OS|Fatura> <id>`): duas páginas discordam sobre o mesmo identificador — uma diz emitida/paga, a página MAIS RECENTE ainda diz pendente. Abra as duas linhas citadas antes de opinar: pode ser (a) contradição real a resolver com a fonte (Financeiro/Redmine), (b) tarefa aberta sobre algo já concluído, ou (c) falso positivo, quando o "pendente" da linha se refere a outra coisa. NUNCA escolha o vencedor sozinho: apresente os dois lados com as datas `updated`.
5. **Duplicatas** (`possivel duplicata`): duas páginas da MESMA pasta com títulos quase iguais. Costuma ser (a) duas sessões do mesmo assunto que deviam ser uma, ou (b) títulos que não distinguem o conteúdo — nos dois casos o leitor não sabe qual abrir e a busca devolve as duas. Proponha fundir ou renomear; fundir é operação aprovada à parte, e o conteúdo perdido não volta.
6. **Página inchada** (`bloated page: ~N tokens`): trate, não só reporte — página que ninguém escaneia é página que ninguém atualiza, e toda leitura futura paga por ela.
   1. `brain extract "<página>" --toc` mostra as seções com custo em tokens. Uma ou duas seções costumam responder pela maior parte do peso.
   2. Escolha o corte e proponha ao usuário: qual seção sai, com que título e para que pasta. **A escolha é semântica, sua; a execução é do `brain split`.**
   3. `brain split "<página>" --heading "<seção>"` mostra o plano sem escrever nada: nova página, quanto sai, quanto fica, e quais páginas usam `[[Página#Seção]]`. Com `--apply` ele efetiva — o heading permanece na origem com um ponteiro `[[Nova Página]]`, então âncoras continuam resolvendo, e a página nova herda `type`, `status` e `tags` (passa no validador de primeira).
   4. Nem todo inchaço quer split. Se a página cresceu de prosa repetida, destile. Se a parte pesada é histórico datado, arquive em `wiki/folds/`. Ledger de contrato é grande por natureza e nem entra nessa checagem.
7. Proponha os fixes. SÓ aplique após aprovação explícita. Relatório persistido: `... lint --write` grava `wiki/meta/lint-report.md`.
