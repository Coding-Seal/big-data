# Suggested implementation order

1. ✅ Scaffold `src/common/`, `src/sources/`, `src/questions/`,
   `config.yaml`, `src/run.py` per [`layered-design.md`](layered-design.md).
2. ✅ Port `sqldump.py` verbatim, into `src/common/sqldump.py`.
3. ✅ Rebuild `src/sources/pageviews.py` and `src/sources/page_dump.py` from
   the PoC logic, parameterized by config instead of hardcoded paths/wikis.
   Both also gained a
   download-with-retry helper (`src/common/http.py`) and a proper
   User-Agent — hit a real `403` from dumps.wikimedia.org without one, and
   a transient `SSLEOFError` confirmed retries are worth having, not
   theoretical.
4. ✅ Write `sources/mediawiki_history.py` against the verified 78-column
   schema in `docs/sources/mediawiki-history.md`. Since no "latest" alias
   exists for this dataset, `download()` discovers the current snapshot and
   real per-wiki filenames from the dumps site's own directory listings
   instead of hardcoding either.
5. ✅ `q1_topic_time.py` and `q4_length_revisions.py` work against the
   existing silver tables (ran end-to-end against real downloaded
   `simplewiki` data). Note: `q1` actually needs `pageviews_fact` +
   `page_dim` + `category_dim`, not just the two tables this doc originally
   suggested — `pageviews_fact` only has `page_title`, and `page_dim` is
   the required bridge to `page_id`.
6. ✅ Add `revision_dim` via `mediawiki_history` → Q4's revision half is in
   (surfaced as `avg_revisions` in the tooltip, same length-bucket chart).
7. ✅ Add Q3 (decay curves, pure window functions over `pageviews_fact`,
   no new source needed) and Q5 (day-of-week, same).
8. ✅ Q2 (spikes) — decided ITN-via-`mediawiki_history` over an external
   source (reuses step 4's parser, no new one needed; see
   `docs/sources/wikinews-itn.md`). Caveat found while implementing: the
   default `simple`/`simplewiki` config has no actively-maintained ITN-style
   page (confirmed against the downloaded page dump — the only
   `Current_events`-titled pages are redirects), so `itn_page_title` is
   left unset by default, and `config.enwiki.yaml` exists as a second
   profile for the run that can actually answer Q2.
9. ✅ First real run (7 days, 2026-10-04..10) — and the questions, not the
   code, were what needed fixing. Four changes came out of reading the
   output instead of the implementation:
   - **Window length is load-bearing and fails silently.** With *n* hourly
     samples a page's `views / avg(views)` cannot exceed *n*, so Q2's
     `SPIKE_RATIO = 3` returned zero rows on the original 2-hour slice by
     arithmetic alone, and Q5 had a single Sunday to contrast against
     itself. Neither looked like an error.
   - **`redirect_dim` + `common/pages.py`** — joining `pageviews_fact` to
     `page_dim` on title dropped 7.2% of views, since `page_dim` holds
     only non-redirect pages ([`redirect.md`](../sources/redirect.md)).
   - **Q4 now zero-fills.** Inner-joining to pageviews answered "views per
     *viewed* article" and hid most of the effect (1.9× across length
     buckets instead of 20×); ~97% of articles have no views in a week.
   - **Q2 reports three states, not a boolean** — `mediawiki_history`
     lags pageviews by weeks, so "no ITN edit nearby" and "no ITN data for
     this hour" are different answers and must not be merged.
10. Once the above prove the contract holds, revisit `category_dim`:
   either filter maintenance categories or bring in Wikidata as
   `topic_dim` (see [`extending-with-new-sources.md`](extending-with-new-sources.md))
   — don't ship Q1/Q5 on raw categories as final.
