"""
Helper for parsing Telegram reply_to_message objects and extracting contextual prompts.
"""
from typing import Any, Optional


def extract_reply_context(reply_to: Optional[Any]) -> str:
    """
    Extracts contextual quoting text from inbound Telegram reply_to_message payloads.
    Safely handles non-dict payloads, text truncation (300 chars), channel senders,
    and diverse media formats (photo, doc, voice, audio, video, sticker, poll, location, contact).
    """
    if not isinstance(reply_to, dict):
        return ""

    r_from = reply_to.get("from") or {}
    r_sender = (
        r_from.get("first_name")
        or r_from.get("username")
        or reply_to.get("sender_chat", {}).get("title")
        or "User"
    )
    r_text = (reply_to.get("text") or reply_to.get("caption") or "").strip()
    if r_text:
        if len(r_text) > 300:
            r_text = r_text[:297] + "..."
        return f'[Replying to message from {r_sender}: "{r_text}"]\n\n'
    elif "photo" in reply_to and reply_to["photo"] is not None:
        return f"[Replying to photo from {r_sender}]\n\n"
    elif "document" in reply_to and reply_to["document"] is not None:
        doc = reply_to.get("document") or {}
        doc_name = doc.get("file_name", "file") if isinstance(doc, dict) else "file"
        return f"[Replying to file ({doc_name}) from {r_sender}]\n\n"
    elif "voice" in reply_to and reply_to["voice"] is not None:
        return f"[Replying to voice message from {r_sender}]\n\n"
    elif "audio" in reply_to and reply_to["audio"] is not None:
        aud = reply_to.get("audio") or {}
        audio_title = aud.get("title", "audio") if isinstance(aud, dict) else "audio"
        return f"[Replying to audio ({audio_title}) from {r_sender}]\n\n"
    elif "video" in reply_to and reply_to["video"] is not None:
        return f"[Replying to video from {r_sender}]\n\n"
    elif "sticker" in reply_to and reply_to["sticker"] is not None:
        stk = reply_to.get("sticker") or {}
        emoji = stk.get("emoji", "") if isinstance(stk, dict) else ""
        return (
            f"[Replying to sticker {emoji} from {r_sender}]\n\n"
            if emoji
            else f"[Replying to sticker from {r_sender}]\n\n"
        )
    elif "poll" in reply_to and reply_to["poll"] is not None:
        pl = reply_to.get("poll") or {}
        poll_q = pl.get("question", "poll") if isinstance(pl, dict) else "poll"
        return f'[Replying to poll "{poll_q}" from {r_sender}]\n\n'
    elif "location" in reply_to and reply_to["location"] is not None:
        return f"[Replying to shared location from {r_sender}]\n\n"
    elif "contact" in reply_to and reply_to["contact"] is not None:
        cnt = reply_to.get("contact") or {}
        contact_name = cnt.get("first_name", "contact") if isinstance(cnt, dict) else "contact"
        return f"[Replying to shared contact ({contact_name}) from {r_sender}]\n\n"
    else:
        return f"[Replying to message from {r_sender}]\n\n"
