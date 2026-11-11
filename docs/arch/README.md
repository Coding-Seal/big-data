# Architecture

Goal, per the assignment brief: answering a new question, or plugging in a new data source, should mean adding one file, not touching what already works. The files in this directory each cover one concern of the design that makes that true:

| File | Covers |
|---|---|
| [`layered-design.md`](layered-design.md) | The core contract: `sources/`/`pipeline/`/`questions/` layout, the silver schema, the source/question module interfaces, why this split, what was deliberately left out |
| [`ingestion-storage.md`](ingestion-storage.md) | Bronze/silver/gold storage layout, ingestion approach, local→cloud scaling path |

Data source facts (location, format, size, description) live in `docs/sources/`, not here: this directory is about the pipeline's shape, not the raw datasets. See `.agents/skills/docs-arch/SKILL.md` for the conventions that keep this directory from drifting out of sync with the code or growing into one unmanageable file again.
