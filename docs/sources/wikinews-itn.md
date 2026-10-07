# Wikinews / "In the news" (ITN) history

**Status:** not fetched — the one research question (Q2) still missing a
committed data source; see `docs/arch/implementation-order.md`, step 8.

## Location

Either `https://dumps.wikimedia.org/enwikinews/latest/enwikinews-latest-pages-articles.xml.bz2`
(confirmed present by listing the live directory), or the revision history
of the `Wikipedia:In the news` page, obtainable via
[`mediawiki-history.md`](mediawiki-history.md) filtered to that one page.

## Format

The `enwikinews` option is confirmed to be the standard MediaWiki XML
export format (`pages-articles.xml.bz2`) — the same export format used for
full-text Wikipedia article dumps, not a format this project has otherwise
worked with (the other sources here are either pre-parsed TSV or raw SQL
dumps). Would need an XML parser, not `sqldump.py`. The `mediawiki_history`
option would instead reuse the TSV schema already verified in
[`mediawiki-history.md`](mediawiki-history.md), filtered to one page title
— likely the lower-effort path if this source gets added, since it needs
no new parsing code.

## Size

Not measured for either option.

## Description

An actual timeline of Wikipedia-recognized news events, without leaving
the Wikimedia ecosystem — a cheaper substitute for an external news API
(GDELT, NewsAPI) for Q2 (traffic spikes vs. news correlation): same
ecosystem, same license, no new vendor dependency. Spike detection itself
(window functions over `pageviews_fact`) doesn't need this source — only
the "correlate with real news events" half of Q2 does. The actual matching
of spike timestamps to news events is a manual/heuristic step either way,
not something derivable automatically from either dataset alone.
