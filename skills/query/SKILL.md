---
name: query
description: Responder perguntas a partir do vault Obsidian (second brain). Use quando o usuário pedir "consulte o vault", "query o vault", "o que sabemos sobre X", "procure no vault". Fluxo: hot.md, busca basic-memory, extrator de seção. Somente leitura.
---

# Query do vault

Responda a partir do vault, sem modificar nenhum arquivo dele.

1. Leia `wiki/hot.md` (contexto recente, barato).
2. Busque com basic-memory: tool MCP `search_notes` (projeto `work`); sem MCP, CLI `basic-memory tool search-notes --query "<termos>"`; sem basic-memory, Grep no vault (`wiki/**/*.md`).
3. NUNCA carregue `wiki/index.md` ou `wiki/log.md` inteiros; log só via `grep "^## \[" wiki/log.md`.
4. Página candidata grande? NÃO leia inteira:
   - `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" extract "<pagina>" --toc`
   - depois `... extract "<pagina>" --heading "<secao>"`
   Páginas pequenas o extract devolve inteiras sozinho.

Regras de evidência:
- Cite a fonte mais específica: `[[Página#Heading]]`.
- Separe explicitamente o que é evidência do vault do que é inferência sua.
- Duas páginas divergindo sobre o mesmo fato: apresente as duas com as datas `updated`, aponte qual é mais recente, não escolha calado.
- O vault não cobre a pergunta: diga o que falta e pare. Não preencha com memória do modelo.
