"""Small host-side registry for synchronous text/function model clients.

Each client owns its provider-specific HTTP format. The durable store decides
whether a call can be sent; registry lookup by itself never sends or retries.
"""
from typing import Any, Dict, Protocol


class TextModelClient(Protocol):
    provider_id: str
    base_url: str

    def send(self, body: Dict[str, Any]) -> Dict[str, Any]:
        ...


class TextModelRegistry:
    def __init__(self):
        self._clients = {}

    def register(self, client: TextModelClient):
        provider = getattr(client, "provider_id", None)
        endpoint = getattr(client, "base_url", None)
        if not isinstance(provider, str) or not provider or not isinstance(endpoint, str) or not endpoint.startswith("https://"):
            raise ValueError("TEXT_MODEL_CLIENT_IDENTITY_INVALID")
        if not callable(getattr(client, "send", None)):
            raise ValueError("TEXT_MODEL_SEND_REQUIRED")
        identity = (provider, endpoint.rstrip("/"))
        if identity in self._clients and self._clients[identity] is not client:
            raise ValueError("TEXT_MODEL_CLIENT_ALREADY_REGISTERED")
        self._clients[identity] = client

    def send_once(self, store, call_id):
        frozen = store.read(call_id)
        client = self._clients.get((frozen["provider_id"], frozen["endpoint"]))
        if client is None:
            raise ValueError("TEXT_MODEL_CLIENT_NOT_REGISTERED")
        return store.send_once(call_id, client)
