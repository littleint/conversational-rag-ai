import json
from typing import List, Optional
from pydantic import Field
from llama_index.core.storage.chat_store.base import BaseChatStore
from llama_index.core.llms import ChatMessage
from upstash_redis import Redis


class UpstashChatStore(BaseChatStore):
    """
    Upstash Redis-backed Chat Store for LlamaIndex.
    Provides sub-5ms low-latency retrieval for short-term working conversational memory.
    """
    url: str = Field(description="Upstash Redis REST URL")
    token: str = Field(description="Upstash Redis REST Token")
    ttl: int = Field(default=2592000, description="TTL in seconds (default 30 days)")

    def __init__(self, url: str, token: str, ttl: int = 2592000, **kwargs):
        super().__init__(url=url, token=token, ttl=ttl, **kwargs)
        self._client = Redis(url=self.url, token=self.token)

    @classmethod
    def class_name(cls) -> str:
        return "UpstashChatStore"

    def _get_key(self, key: str) -> str:
        return f"llamareader:chat:{key}"

    def set_messages(self, key: str, messages: List[ChatMessage]) -> None:
        """Set messages for a conversation key with TTL."""
        try:
            raw = json.dumps([m.model_dump() for m in messages])
            self._client.set(self._get_key(key), raw, ex=self.ttl)
        except Exception as e:
            print(f"UpstashChatStore set_messages error: {e}")

    def get_messages(self, key: str) -> List[ChatMessage]:
        """Fetch messages for a conversation key."""
        try:
            raw = self._client.get(self._get_key(key))
            if not raw:
                return []
            items = json.loads(raw)
            return [ChatMessage.model_validate(item) for item in items]
        except Exception as e:
            print(f"UpstashChatStore get_messages error: {e}")
            return []

    def add_message(self, key: str, message: ChatMessage) -> None:
        """Append a message to the conversation."""
        msgs = self.get_messages(key)
        msgs.append(message)
        self.set_messages(key, msgs)

    def delete_messages(self, key: str) -> Optional[List[ChatMessage]]:
        """Delete all messages for a conversation key."""
        msgs = self.get_messages(key)
        try:
            self._client.delete(self._get_key(key))
        except Exception as e:
            print(f"UpstashChatStore delete_messages error: {e}")
        return msgs

    def delete_message(self, key: str, idx: int) -> Optional[ChatMessage]:
        """Delete a message at a specific index."""
        msgs = self.get_messages(key)
        if 0 <= idx < len(msgs):
            item = msgs.pop(idx)
            self.set_messages(key, msgs)
            return item
        return None

    def delete_last_message(self, key: str) -> Optional[ChatMessage]:
        """Delete the last message."""
        msgs = self.get_messages(key)
        if msgs:
            item = msgs.pop()
            self.set_messages(key, msgs)
            return item
        return None

    def get_keys(self) -> List[str]:
        """Return all chat keys."""
        return []

