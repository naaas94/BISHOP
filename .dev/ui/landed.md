# Landed page

`GET /landed` lists indexed entries from query-api `GET /recent` (DuckDB `entries_mirror`, `ingested_at` descending). Default window is 7 days. Optional `source`. Empty `q` is allowed — this is a list of what was indexed, not search.

Dashboard “Indexed today” links here with `days=1`. A DuckDB writer lock already returns an empty 200 from query-api; the page treats that as an empty window.

Not a digest and not a persist. Reading status stays on the entry page. Rebuild `ui` after template edits.
