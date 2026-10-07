"""
Minimal parser for MediaWiki's MySQL dump INSERT statements.

Classic mysqldump extended-insert format puts a whole statement on one
line:
  INSERT INTO `page` VALUES (1,0,'Foo',0,...),(2,0,'Bar',1,...);

**Current Wikimedia dumps don't actually look like that** -- confirmed by
downloading a real `simplewiki` dump while building this pipeline: `VALUES`
appears on its own line, then one tuple per following line:
  INSERT INTO `page` VALUES
  (1,0,'Foo',0,...),
  (2,0,'Bar',1,...);
Parsing this with a strict `line.find("VALUES (")` (one physical line at a
time) silently finds nothing -- not an error, just zero rows, which is far
more dangerous than a crash.

`parse_insert_line` below handles a single line/chunk at a time -- given
either a full classic statement, a header line (`...VALUES`, no data), or
a single bare tuple line (no `VALUES` at all), it finds whatever tuples are
actually present. `VALUES` is optional: if absent, scanning starts from
the beginning of the text, which is exactly what a bare `(1,0,'Foo',...),`
data line is. Reassembling *which* lines belong to which table's INSERT
block across line boundaries is the caller's job (see
`sources/page_dump.py::_parse_table`, which streams line-by-line rather
than loading a whole file into memory at once -- that was tried first and
overflowed the JVM heap on a ~30MB dump, let alone enwiki's multi-GB ones).

This is NOT a general SQL parser -- it only handles what these dumps
actually contain: parenthesized tuples of NULL / integers / single-quoted
byte strings with backslash escaping. Good enough for these dumps, not
meant for arbitrary SQL.

Originally ported from poc/sqldump.py (per docs/arch/poc-mapping.md); the
multi-line handling above was added after poc/sqldump.py's single-line
assumption was proven wrong against a real current dump.
"""

_WHITESPACE = " \t\r\n"


def parse_insert_line(text: str):
    """Yield one list-of-raw-field-strings per value tuple found in `text`.

    If `text` contains `VALUES`, scanning starts right after it (handles a
    full classic single-line statement, or a lone header line with no data,
    which correctly yields nothing). If `VALUES` is absent, scanning starts
    from the beginning -- handles a bare data line like `(1,0,'Foo',...),`.
    Stops at the first non-tuple, non-whitespace character (typically a
    statement's terminating `;`), so trailing content doesn't matter.
    """
    idx = text.find("VALUES")
    i = idx + len("VALUES") if idx != -1 else 0
    n = len(text)

    while i < n:
        while i < n and text[i] in _WHITESPACE:
            i += 1
        if i >= n or text[i] != "(":
            break
        i += 1
        fields = []
        buf = []
        in_str = False
        while i < n:
            c = text[i]
            if in_str:
                if c == "\\":
                    buf.append(text[i + 1])
                    i += 2
                    continue
                if c == "'":
                    in_str = False
                    i += 1
                    continue
                buf.append(c)
                i += 1
                continue
            if c == "'":
                in_str = True
                i += 1
                continue
            if c == ",":
                fields.append("".join(buf))
                buf = []
                i += 1
                continue
            if c == ")":
                fields.append("".join(buf))
                i += 1
                break
            buf.append(c)
            i += 1
        yield fields
        while i < n and text[i] in _WHITESPACE:
            i += 1
        if i < n and text[i] == ",":
            i += 1


def as_int(v):
    return None if v == "NULL" else int(v)


def as_str(v):
    return None if v == "NULL" else v
