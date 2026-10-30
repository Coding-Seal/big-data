---
name: validating-question-output
description: Use before reporting, charting, or drawing a conclusion from any question module's output (Q1-Q5, gold specs, run-question results) — separates real findings from the artifacts this pipeline produces silently.
---

# Trusting a question's answer

Every wrong answer this project has produced looked completely plausible,
exited 0, and differed from the right answer by a factor of 2–20. None of
them announced themselves. So the output of a successful run is a draft,
not a result: walk this list before any number leaves the session.

Each check below is here because it has already caught a real error.

## 1. Did the question read the window its config names?

`pageviews_fact` is partitioned and silver is written with
`partitionOverwriteMode=dynamic`, so a write replaces only the partitions
it touches — changing `date_range` leaves the previous window on disk
beside the new one. `run.py::load_tables` now filters every question's
`pageviews_fact` to `date_range`, which closes this, but verify rather than
assume:

```python
pv.agg(F.min("ts"), F.max("ts"), F.countDistinct("date")).show()
```

Measured 2026-10-28, before the filter existed: `silver/en` held the
configured Sept 14–20 *and* a stale Oct 4–10. Q2 called 18 of its top 20
spikes `NEWS_UNKNOWN` (true of the October hours, irrelevant to the
question) and Q5's per-weekday totals were silently the sum of two
different weeks. Note that two profiles configuring different weeks is
normal — extra partitions under `silver/simple` are not automatically
stale.

## 2. Is absence of signal absence of data?

Before reading "no effect" into a null result, check that the source could
have shown an effect. `mediawiki_history` lags the pageviews dumps by
weeks, and its newest monthly file is often a stub.

```python
itn.agg(F.min("news_ts"), F.max("news_ts")).show()   # vs the window
```

Q2 encodes this as three states — `NEWS_MATCHED` / `NEWS_ABSENT` /
`NEWS_UNKNOWN` — specifically so "the dump doesn't reach this hour" can't
be read as "this spike wasn't news." Generalize the discipline to any new
question: **collapsing missing data into a negative finding manufactures a
result.** For reference, a healthy September `itn_edit_fact` spans
2026-09-01 → 2026-10-01 with 46 edits inside a Sept 14–20 window.

## 3. Is the unit of analysis an article?

`pageviews_fact` keys on the title in the URL, so grouping by `page_title`
treats every redirect as its own article. That is 7.2% of traffic,
concentrated on exactly the news-driven pages the questions care about.

- Fold through `common/pages.py::with_page_id` **before** any arithmetic,
  not after — a peak, baseline, or spike ratio computed per title is the
  wrong number, not a slightly noisy right one.
- Aggregate *and* count by `page_id`; `countDistinct("page_title")`
  overstates article counts.
- Carry `page_title` only as a display column, joined back from `page_dim`
  at the end.
- Remember the fold also *drops* titles resolving to no namespace-0 page
  (`Special:*`, pages newer than the snapshot), so view totals are article
  traffic and are not comparable with raw dump counts.

## 4. What is the denominator?

Averaging over "articles that were viewed" answers a different question
than averaging over all articles. With a short window ~97% of articles have
zero views, and conditioning on being viewed hid most of Q4's effect
(20x → 1.9x). Prefer a left join *from* `page_dim` with a zero fill, and
state which denominator a reported average uses.

## 5. Is the threshold reachable in the window?

With n hourly samples a page's `views / avg(views)` cannot exceed n, so any
spike threshold ≥ n returns zero rows by arithmetic — Q2 once looked
"implemented but finding nothing" on a 2-hour window. Q5 needs at least a
full week to have one of every weekday, and one week means n=1 per weekday,
which cannot separate a real pattern from a single viral page.

## 6. Does the top of the output look like what it claims to measure?

Read the top-N rows before believing the aggregate.

- **Automated traffic.** `european_election_2014` drew 482K views in a 2026
  week through a lowercase redirect — a scraper, not readership. A
  stale-looking title among current ones is the tell.
- **Maintenance categories.** `category_dim` is not a topic taxonomy: at
  enwiki scale the top categories by views are *entirely* tracking tags
  (`Articles_with_short_description` 871M). Q1 and the "by topic" half of
  Q5 measure template usage until a Wikidata-backed `topic_dim` lands — say
  so rather than reporting them as topics.
- **Partial dimensions.** enwiki's `revision_dim` only covers pages edited
  in the months downloaded, so its `avg_revisions` is not a whole-wiki
  average.

## Reporting

State the window, the wiki, and the denominator alongside any number — most
of the errors above are invisible in the number itself and obvious once
those three are written next to it. If a check fails, fix the cause rather
than annotating the output: these artifacts are indistinguishable from
findings to anyone reading the chart later.
