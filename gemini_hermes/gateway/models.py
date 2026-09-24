"""
Data models and task representations for the Gemini-Hermes gateway.
"""
from typing import Optional


class QueuedTask(str):
    """
    A string subclass that transparently carries metadata (such as originating
    Telegram message_id and item_type) through task queues.
    Inheriting from str ensures complete backwards-compatibility with string
    comparisons, logging, formatting, and existing tests.
    """
    message_id: Optional[int]
    item_type: str

    def __new__(cls, content: str, message_id: Optional[int] = None, item_type: str = "message"):
        obj = super().__new__(cls, content)
        obj.message_id = message_id
        obj.item_type = item_type
        return obj
