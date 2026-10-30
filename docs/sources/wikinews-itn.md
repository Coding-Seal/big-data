# Wikinews / "In the news" (ITN) history

**Status:** in use, via the mediawiki_history option below — implemented as
`sources/mediawiki_history.py::to_silver`'s `itn_edit_fact` output, filtered
to `config.yaml`'s `mediawiki_history.itn_page_title`. Chosen over the
`enwikinews` XML option because it reuses the TSV parsing already needed for
Q4's revision half, with no new parser.

**Caveat found while wiring this up:** the project's default `simple`
wiki/config has no actively-maintained ITN-style page. Checked directly
against the already-downloaded `simplewiki` page dump — the only
`Current_events`-titled pages in both the main (`ns=0`) and project
(`ns=4`) namespaces are themselves redirects (`is_redirect=1`), not a live,
regularly-edited portal; only user-sandbox pages (`ns=2`) match
`In_the_news` by name. So with the default config, `itn_page_title` is left
unset and Q2 runs but reports every spike as `has_nearby_news=false`. Real
signal needs `wiki: en` / `page_dump.wiki_db: enwiki` and
`itn_page_title: "Wikipedia:In_the_news"` (not independently verified
against a downloaded enwiki dump — enwiki is documented elsewhere as
maintaining this page actively, but confirm before relying on it for a
real run).

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
