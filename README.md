# rss-feed-snapshots

Weekly JSON snapshots of public RSS/Atom feeds from institutional and
regulatory newsrooms (law enforcement, financial supervisors, NGOs, research).

Every Sunday a GitHub Action fetches all feeds in `sources.json`, keeps the
entries from the last 9 days and writes:

- `output/<ISO-week>.json` — archived weekly snapshot
- `output/latest.json` — stable URL for downstream consumers

Per source the snapshot also records the most recent publication date seen
on the feed and a fetch status (`ok` / `empty` / `error`), so silent or dead
feeds are visible immediately.

All content is public metadata (title, link, date, summary excerpt) from the
original publishers; no analysis or other data is stored here.
