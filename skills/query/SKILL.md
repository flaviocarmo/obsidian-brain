---
name: query
description: Responder perguntas a partir do vault Obsidian (second brain). Use quando o usuário pedir "consulte o vault", "query o vault", "o que sabemos sobre X", "procure no vault". Fluxo: hot.md, busca basic-memory, extrator de seção. Somente leitura.
---

# Query do vault

Responda a partir do vault, sem modificar nenhum arquivo dele.

1. Leia `wiki/hot.md` (contexto recente, barato). Se a pergunta tem um **mental model** em `wiki/models/`, leia-o: é resposta permanente já escrita, sem custo de retrieval.
2. Busque com `brain recall "<pergunta>"` — funde busca semântica (basic-memory), busca por título e **grep por identificador forte** (NF/OS/Fatura, IP, host) com reciprocal rank fusion. Use o MCP `search_notes` direto só quando quiser filtrar por tag/status/data. Identificador exato é onde o vetor erra: a página que diz `NF 1142` estava em 7º na busca semântica e é 1ª no recall.
   Se o basic-memory não responder, **avise o usuário e rode `brain doctor`** antes de continuar. Grep é degradação temporária, não o caminho normal: a resposta fica pior sem sinal.
3. NUNCA carregue `wiki/index.md` ou `wiki/log.md` inteiros; log só via `grep "^## \[" wiki/log.md`. Precisa do mapa de UM tema? `brain extract index --toc` e depois `--heading "<pasta> (<n>)"` — uma subpasta custa uma fração do arquivo.
   **Pergunta operacional ("como faço X", "X quebrou, e agora")**: olhe `wiki/runbooks/` PRIMEIRO (`type: runbook` tem passos e verificação prontos). Página de sessão narra o incidente; runbook executa.
4. Página candidata grande? NÃO leia inteira:
   - `python "${CLAUDE_PLUGIN_ROOT}/scripts/brain.py" extract "<pagina>" --toc`
   - depois `... extract "<pagina>" --heading "<secao>"`
   Páginas pequenas o extract devolve inteiras sozinho.

**Credenciais**: o vault guarda senha, token e connection string de propósito — não é achado, não sanitize. Mas o valor NUNCA sai do vault: nada de credencial em issue, MR, commit, e-mail ou código. Cite pelo nome e pela página (`a senha do X está em [[Página]]`). Exceção: o usuário pedir o valor.

Regras de evidência:
- Cite a fonte mais específica: `[[Página#Heading]]`.
- Separe explicitamente o que é evidência do vault do que é inferência sua.
- Duas páginas divergindo sobre o mesmo fato: apresente as duas com as datas `updated`, aponte qual é mais recente, não escolha calado.
- O vault não cobre a pergunta: diga o que falta e pare. Não preencha com memória do modelo.
