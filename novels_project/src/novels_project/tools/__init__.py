"""
小说创作工具集
"""
from .sample_retriever import retrieve_writing_samples, refresh_sample_library
from .character_voice_checker import check_character_voice, get_character_voice_guide, refresh_character_cards
from .feedback_tools import retrieve_feedback, get_common_mistakes, record_feedback, record_batch_feedback
from .iteration_tools import check_iteration_status, should_continue_iteration, get_revision_feedback, record_iteration
from .character_card_tools import (
    update_character_card,
    add_character_dialogue_example,
    get_character_card,
    list_all_characters,
)

__all__ = [
    "retrieve_writing_samples",
    "refresh_sample_library",
    "check_character_voice",
    "get_character_voice_guide",
    "refresh_character_cards",
    "retrieve_feedback",
    "get_common_mistakes",
    "record_feedback",
    "record_batch_feedback",
    "check_iteration_status",
    "should_continue_iteration",
    "get_revision_feedback",
    "record_iteration",
    "update_character_card",
    "add_character_dialogue_example",
    "get_character_card",
    "list_all_characters",
]
