"""The research questions, registered by name.

A question module implements required_tables / run / chart_encoding /
default_mark (docs/arch/layered-design.md). Adding one means adding a file
here and a line below -- deliberately explicit rather than auto-discovered.
"""
from . import (
    q1_topic_time,
    q1b_topic_time_filtered,
    q2_spikes_news,
    q3_decay,
    q4_length_revisions,
    q4b_length_no_mainpage,
    q5_weekday,
    q5b_weekday_no_mainpage,
)

QUESTIONS = {
    "q1_topic_time": q1_topic_time,
    "q1b_topic_time_filtered": q1b_topic_time_filtered,
    "q2_spikes_news": q2_spikes_news,
    "q3_decay": q3_decay,
    "q4_length_revisions": q4_length_revisions,
    "q4b_length_no_mainpage": q4b_length_no_mainpage,
    "q5_weekday": q5_weekday,
    "q5b_weekday_no_mainpage": q5b_weekday_no_mainpage,
}

__all__ = ["QUESTIONS"]
