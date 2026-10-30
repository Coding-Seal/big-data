"""Namespace-prefix filtering for pageviews `page_title` values.

Approximation, not a formal namespace lookup -- a few true edge cases may
slip through. See docs/sources/pageviews.md.
"""

# Canonical namespace ids, for config values written the way a reader sees
# them ("Template:In_the_news"). `mediawiki_history` stores `page_title`
# *without* the prefix and keeps the id in its own column, so a config
# value carrying one matches nothing until it's split -- and a filter that
# matches nothing is not an error, just an empty table.
NAMESPACE_IDS = {
    "": 0, "Talk": 1, "User": 2, "User_talk": 3, "Wikipedia": 4,
    "Wikipedia_talk": 5, "File": 6, "File_talk": 7, "MediaWiki": 8,
    "MediaWiki_talk": 9, "Template": 10, "Template_talk": 11, "Help": 12,
    "Help_talk": 13, "Category": 14, "Category_talk": 15, "Portal": 100,
    "Portal_talk": 101, "Draft": 118, "Draft_talk": 119,
}


def split_prefixed_title(title: str) -> tuple[int, str]:
    """"Template:In_the_news" -> (10, "In_the_news"); "Foo" -> (0, "Foo").

    Only splits on a *known* namespace prefix: plenty of article titles
    contain a colon ("Dune: Part Two"), and those belong in namespace 0.
    """
    prefix, sep, rest = title.partition(":")
    key = prefix.replace(" ", "_")
    if sep and key in NAMESPACE_IDS:
        return NAMESPACE_IDS[key], rest.replace(" ", "_")
    return 0, title.replace(" ", "_")


NON_ARTICLE_PREFIXES = [
    "Talk", "User", "User_talk", "Wikipedia", "Wikipedia_talk", "File",
    "File_talk", "MediaWiki", "MediaWiki_talk", "Template", "Template_talk",
    "Help", "Help_talk", "Category", "Category_talk", "Portal", "Portal_talk",
    "Draft", "Draft_talk", "TimedText", "TimedText_talk", "Module",
    "Module_talk", "Special", "Media",
]
NON_ARTICLE_REGEX = "^(" + "|".join(NON_ARTICLE_PREFIXES) + "):"
