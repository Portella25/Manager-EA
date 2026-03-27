# Live Editor Data Contract v2

Este contrato descreve os arquivos exportados pelo `companion_export.lua` e como o backend os ingere sem alterar o motor narrativo.

## Arquivos Exportados

- `state.json`: snapshot operacional contínuo do save.
- `schema.json`: catálogo dinâmico de tabelas/campos disponíveis no Live Editor.
- `reference_data.json`: dados de referência pouco voláteis.
- `events.jsonl`: log incremental de eventos crus e normalizados.
- `season_stats.json`: estatísticas por jogador/competição.
- `transfer_history.json`: histórico global de transferências.

## Estrutura Geral

- Todos os arquivos incluem `save_uid` quando aplicável.
- `state.json` preserva compatibilidade com o contrato atual e adiciona:
  - `meta.export_version`
  - `meta.career_type`
  - `meta.source`
  - `runtime_signals`
  - `event_summary`
  - `sync_info`
- `schema.json` contém:
  - `export_version`
  - `save_uid`
  - `timestamp`
  - `total_tables`
  - `tables[]` com `table_name`, `priority`, `fields_count`, `fields[]`
- `reference_data.json` contém:
  - `entities.players`
  - `entities.teams`
  - `entities.teamplayerlinks`
  - `entities.manager`
  - `entities.career_presignedcontract`
  - `metadata` de contagem por entidade

## Regras Operacionais

- Escrita de snapshots em modo atômico (`.tmp` + rename).
- `events.jsonl` em append incremental.
- Resiliência a campos ausentes via `safe_call` e leitura defensiva.
- `save_uid` como chave de segregação entre carreiras.

## Ingestão no Backend

- O watcher continua ingerindo `state.json` como fonte primária.
- Novo módulo `external_ingestion.py` ingere:
  - `schema.json`
  - `reference_data.json`
  - `season_stats.json`
  - `transfer_history.json`
  - `events.jsonl`
- Persistência por `save_uid` em:
  - `external_artifacts`
  - `external_event_logs`

## Endpoints Novos

- `GET /state/schema?save_uid=...`
- `GET /state/reference?save_uid=...`
- `GET /state/season-stats?save_uid=...`
- `GET /state/transfer-history?save_uid=...`
- `GET /events/external/recent?save_uid=...&limit=...`

## Compatibilidade

- O motor narrativo atual permanece inalterado.
- A camada nova é de observabilidade e ingestão de contexto.
