"""Namespace-prefix filtering for pageviews `page_title` values.

Approximation, not a formal namespace lookup -- a few true edge cases may
slip through. See docs/sources/pageviews.md.
"""

NON_ARTICLE_PREFIXES = [
    "Talk", "User", "User_talk", "Wikipedia", "Wikipedia_talk", "File",
    "File_talk", "MediaWiki", "MediaWiki_talk", "Template", "Template_talk",
    "Help", "Help_talk", "Category", "Category_talk", "Portal", "Portal_talk",
    "Draft", "Draft_talk", "TimedText", "TimedText_talk", "Module",
    "Module_talk", "Special", "Media",
]
NON_ARTICLE_REGEX = "^(" + "|".join(NON_ARTICLE_PREFIXES) + "):"
