# Persist vendor payloads

Standing rule: if an API already returned a fact, persist it. Do not log-and-drop.

Typed columns for anything we will query, rank, or join. JSON bag (`extras_json`) for the rest of that object so a new field is not a migration to avoid data loss.

**Do not persist:** secrets, README/full content (content-scraper), a whole Search page as one blob.

## This landing (harvest sidecar)

GitHub Search repository objects go on `${BISHOP_DATA_ROOT}/harvest/ledger.sqlite` (`candidates` + `harvest_runs`). Release into `DISCOVERED` stays the thin `ManifestIngestEntry` wire. Gate 1 stays title+tagline. Harvest mill cadence miss (90s on the scrape tick / 6h sleep): PB-011, `.dev/decision-logs/ops/harvest-pool-first-landing.md`.

## Known holes (later slices — do not wait on harvest)

| Surface | What we already have | Where it dies today |
|---|---|---|
| Anthropic `message.usage` | `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens` parsed in batch-poller | structured logs only. `batches` has no usage columns. **PB-002.** |
| ArXiv primary category | extracted in `parse_atom_feed_with_categories` | dropped at the wire; never on `manifest` |
| Semantic Scholar | `fields=` can add citationCount, venue, tldr, fieldsOfStudy | harvest requests only `paperId,title,abstract,url,publicationDate` |
| Hugging Face Hub | likes, downloads, pipeline_tag, tags | dropped in `parse_entity_list` |
| LessWrong GraphQL | karma / wordCount available | query asks `_id title postedAt pageUrl` only |
| Park promote | HTTP succeed/fail | no who/when audit trail |

Projected harvest $ on the dashboard is derived from `config/harvest/economics.yaml`, not live Anthropic spend. Do not invent UI token fields first (PB-002).
