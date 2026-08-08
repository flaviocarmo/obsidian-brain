---
name: ingest
description: Ingerir um source (arquivo em .raw/, texto colado, transcript) no vault Obsidian criando/atualizando páginas atômicas. Use com "ingest <arquivo>", "processa esse source", "ingere isso no vault".
---

# Ingest de source

1. Source é arquivo? Mova/copie para `.raw/` primeiro (imutável: nunca edite um arquivo existente lá; o validador bloqueia).
2. Leia o source inteiro e liste os fatos/entidades/decisões que merecem página.
3. Para CADA candidato: busque no basic-memory se já existe página. Existir = atualizar (update-não-duplica). Página nova só para conceito realmente novo.
4. Páginas atômicas: uma página, um assunto. Frontmatter universal + `sources:` apontando o arquivo em `.raw/` (provenance).
5. Wikilinks entre as páginas tocadas; entrada nova no topo do `log.md` (`## [YYYY-MM-DD] Ingest: <source>`) listando páginas criadas/atualizadas.
6. Batch ("ingest all of these") = repetir por source, um de cada vez, mesmo rigor.

Hooks validam cada escrita e recompilam o index; não rode compile-index manualmente.
