# Suggested implementation order

1. ✅ Scaffold `src/common/`, `src/sources/`, `src/questions/`,
   `config.yaml`, `src/run.py` per [`layered-design.md`](layered-design.md).
2. ✅ Port `sqldump.py` verbatim, into `src/common/sqldump.py`.
3. ✅ Rebuild `src/sources/pageviews.py` and `src/sources/page_dump.py` from
   the PoC logic, parameterized by config instead of hardcoded paths/wikis
   (see [`poc-mapping.md`](poc-mapping.md)). Both also gained a
   download-with-retry helper (`src/common/http.py`) and a proper
   User-Agent — hit a real `403` from dumps.wikimedia.org without one, and
   a transient `SSLEOFError` confirmed retries are worth having, not
   theoretical.
4. Write `sources/mediawiki_history.py` against the verified 78-column
   schema in `docs/sources/mediawiki-history.md` (this was previously
   unverified — resolved by downloading a real file).
5. ✅ `q1_topic_time.py` and `q4_length_revisions.py` work against the
   existing silver tables (ran end-to-end against real downloaded
   `simplewiki` data). Note: `q1` actually needs `pageviews_fact` +
   `page_dim` + `category_dim`, not just the two tables this doc originally
   suggested — `pageviews_fact` only has `page_title`, and `page_dim` is
   the required bridge to `page_id`.
6. Add `revision_dim` via `mediawiki_history` → unblocks the rest of Q4.
7. Add Q3 (decay curves, pure window functions over `pageviews_fact`,
   no new source needed) and Q5 (day-of-week, same).
8. Q2 (spikes) needs a news timeline — decide between Wikinews/ITN
   (in-ecosystem, cheaper) vs. an external source before implementing;
   this is the one question still missing a committed data source.
9. Once the above prove the contract holds, revisit `category_dim`:
   either filter maintenance categories or bring in Wikidata as
   `topic_dim` (see [`extending-with-new-sources.md`](extending-with-new-sources.md))
   — don't ship Q1/Q5 on raw categories as final.
