# SurrealEngine Notebooks

This directory contains feature demos and production-pattern examples.

## Start Here (Current Release)

- `v1_2_syncmanager_routing.ipynb`
  - Freshness routing (`stale_ok`, `realtime`, `auto`) with `SyncManager`.
- `v1_2_context_scoped_sync_manager.ipynb`
  - Request/task-scoped routing with `using_sync_manager(...)`.
- `v1_2_live_reliability_patterns.ipynb`
  - LIVE patterns for long-running services: dedicated connections, queue bounds, backpressure.
- `v1_2_replay_checkpoint_recovery.ipynb`
  - Checkpoint persistence and replay recovery flow (`show_changes` + replay).
- `v1_2_search_ergonomics.ipynb`
  - Preferred search APIs: FTS (`search_and`, `search_or`, score/highlight) + vector (`semantic_search`, `__knn`) and hybrid chains.

## Release Bridge

- `v1_x_surrealkv_features.ipynb`
  - Compact overview of 1.x capabilities on embedded SurrealKV.

## API Style Guides

- `polyglot_api.ipynb`
  - Sync/async usage patterns with shared models.
- `sync_api.ipynb`
  - Synchronous API walkthrough.

## Search and Data Modeling

- `14_full_text_search.ipynb`
  - Full-text indexing/search setup and usage.
- `schema_management.ipynb`, `hybrid_schemas.ipynb`
  - Schema and index lifecycle patterns.

## Graph and Relationships

- `relationships.ipynb`, `relation_document.ipynb`, `bidirectional_relations.ipynb`
  - Relationship modeling and graph traversal patterns.

## Legacy Feature Demos

- `v0_7_0_features.ipynb`, `v0_6_0_features.ipynb`
  - Prior release snapshots and historical examples.


## Quick Usage-Test Run Order

1. `v1_2_syncmanager_routing.ipynb`
   - Success signal: final line prints `ALL ROUTING SMOKE CHECKS PASSED`.
2. `v1_2_context_scoped_sync_manager.ipynb`
   - Success signal: final line prints `ALL CONTEXT-SCOPED SMOKE CHECKS PASSED`.
3. `v1_2_live_reliability_patterns.ipynb`
   - Success signal: final line prints `ALL LIVE SMOKE CHECKS PASSED`.
4. `v1_2_replay_checkpoint_recovery.ipynb`
   - Success signal: final line prints `CHECKPOINT/REPLAY SMOKE CHECKS PASSED`.

## Environment Checklist

- SurrealDB reachable at `ws://localhost:8000/rpc`
- Namespace/database values in notebooks are available
- Root credentials in demo cells are valid for your local environment
- CHANGEFEED enabled for replay demo table(s) when testing full recovery
