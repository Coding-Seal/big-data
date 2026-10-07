# Mapping from the existing PoC

This is a rename-and-regroup of code that already works, not a rewrite —
the parsing/filtering logic proven in `poc/` doesn't change, only where it
lives and how it's invoked, per [`layered-design.md`](layered-design.md).

| PoC file | Becomes | Status |
|---|---|---|
| `poc/sqldump.py` | `src/common/sqldump.py` (unchanged logic) | done |
| `poc/ingest.py` | `src/sources/pageviews.py::to_silver` | done |
| `poc/ingest_dims.py` | `src/sources/page_dump.py::to_silver` | done |
| `poc/ingest_simple_pageviews.py` | deleted — becomes a config choice (`wiki: simple`) rather than a separate script | config choice now exists (`config.yaml`); `poc/ingest_simple_pageviews.py` not yet deleted |
| `poc/join_demo.py` | split into `src/questions/q1_topic_time.py` (category join) and `src/questions/q4_length_revisions.py` (length join) | done (Q4's revision-count half still pending `mediawiki_history`) |
| `poc/analyze.py` | folded into the relevant `questions/*.py` modules | not yet done |

**This table is temporary scaffolding** (per
`.agents/skills/docs-arch/SKILL.md`'s conventions) — once
[`implementation-order.md`](implementation-order.md) actually happens and
`poc/` is retired, delete this file rather than maintaining it against code
it no longer describes.
