"""
Telegram API client service handling HTTP transport, message dispatch, and media downloads.
"""
import os
import logging
from typing import Optional, Dict, Any
import httpx

from gemini_hermes.config import config

logger = logging.getLogger("gemini-hermes.telegram.client")


class TelegramClient:
    """
    Dedicated client service for Telegram Bot API operations.
    Handles network requests, serialization, retries, and markdown/reply fallbacks.
    """

    def __init__(self, token: Optional[str] = None):
        self.token = token or config.bot_token
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.client: Optional[httpx.AsyncClient] = None

    async def _api_call(self, method: str, json_data: Optional[Dict[str, Any]] = None, timeout: float = 35.0) -> Any:
        if not self.client or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=timeout)
        url = f"{self.api_url}/{method}"
        try:
            resp = await self.client.post(url, json=json_data, timeout=timeout)
            data = resp.json()
            if not data.get("ok"):
                logger.warning(f"Telegram API {method} returned not ok: {data}")
            return data
        except Exception as e:
            logger.error(f"Telegram API request {method} error: {e}")
            return {"ok": False, "error": str(e)}

    async def get_me(self) -> Dict[str, Any]:
        res = await self._api_call("getMe")
        if res.get("ok"):
            return res.get("result", {})
        return {}

    async def get_file_path(self, file_id: str) -> Optional[str]:
        res = await self._api_call("getFile", {"file_id": file_id})
        if res.get("ok"):
            return res["result"].get("file_path")
        return None

    async def download_file_to(self, file_path: str, dest_path: str) -> bool:
        file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        try:
            if not self.client or self.client.is_closed:
                self.client = httpx.AsyncClient(timeout=60.0)
            resp = await self.client.get(file_url, timeout=60.0)
            if resp.status_code == 200:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                return True
            else:
                logger.error(f"Download failed for {file_path}: status {resp.status_code}")
        except Exception as e:
            logger.error(f"Error downloading file {file_path}: {e}")
        return False

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = "Markdown",
        reply_to_message_id: Optional[int] = None,
    ) -> Optional[int]:
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
            payload["allow_sending_without_reply"] = True
            payload["reply_parameters"] = {
                "message_id": reply_to_message_id,
                "allow_sending_without_reply": True,
            }
        res = await self._api_call("sendMessage", payload)
        if not res.get("ok"):
            # Fallback 1: without markdown parsing if syntax error occurred
            if parse_mode:
                fallback_payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
                if reply_to_message_id:
                    fallback_payload["reply_to_message_id"] = reply_to_message_id
                    fallback_payload["allow_sending_without_reply"] = True
                    fallback_payload["reply_parameters"] = {
                        "message_id": reply_to_message_id,
                        "allow_sending_without_reply": True,
                    }
                res = await self._api_call("sendMessage", fallback_payload)

            # Fallback 2: if still failing and reply was targeted, send directly without reply parameters
            # (protects against Telegram API rejecting invalid/deleted message reply references)
            if not res.get("ok") and reply_to_message_id:
                direct_payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
                res = await self._api_call("sendMessage", direct_payload)

        if res.get("ok"):
            return res["result"]["message_id"]
        return None

    async def delete_message(self, chat_id: int, message_id: int) -> bool:
        res = await self._api_call(
            "deleteMessage",
            {"chat_id": chat_id, "message_id": message_id},
        )
        return bool(res.get("ok"))

    async def edit_message_text(
        self, chat_id: int, message_id: int, text: str, parse_mode: Optional[str] = "Markdown"
    ) -> bool:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        res = await self._api_call("editMessageText", payload)
        if not res.get("ok"):
            desc = res.get("description", "")
            if "message is not modified" in desc:
                return True
            if parse_mode:
                # Fallback without markdown
                fallback_res = await self._api_call(
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": text,
                    },
                )
                if not fallback_res.get("ok") and "message is not modified" in fallback_res.get("description", ""):
                    return True
                return bool(fallback_res.get("ok"))
        return bool(res.get("ok"))

    async def send_chat_action(self, chat_id: int, action: str = "typing"):
        await self._api_call("sendChatAction", {"chat_id": chat_id, "action": action}, timeout=10.0)

    async def close(self):
        if self.client and not self.client.is_closed:
            await self.client.aclose()
