from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from app.config import settings


BASE_URL = "https://open.feishu.cn/open-apis"


@dataclass
class TokenCache:
    access_token: str = ""
    expire_at: float = 0


class FeishuClient:
    def __init__(self) -> None:
        self._cache = TokenCache()

    def _request_access_token(self) -> str:
        if not settings.has_feishu_auth:
            raise RuntimeError("FEISHU_APP_ID / FEISHU_APP_SECRET 未配置")

        url = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
        body = {"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret}
        resp = requests.post(url, json=body, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书鉴权失败: {data}")

        token = data["tenant_access_token"]
        expire = int(data.get("expire", 7200))
        self._cache = TokenCache(access_token=token, expire_at=time.time() + expire - 60)
        return token

    def _get_token(self) -> str:
        if self._cache.access_token and time.time() < self._cache.expire_at:
            return self._cache.access_token
        return self._request_access_token()

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json; charset=utf-8"}

    def send_text(self, text: str, *, receive_id_type: str, receive_id: str) -> dict[str, Any]:
        url = f"{BASE_URL}/im/v1/messages?receive_id_type={receive_id_type}"
        body = {"receive_id": receive_id, "msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)}
        resp = requests.post(url, headers=self._headers(), json=body, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书发消息失败: {data}")
        return data

    def reply_text(self, message_id: str, text: str) -> dict[str, Any]:
        url = f"{BASE_URL}/im/v1/messages/{message_id}/reply"
        body = {"msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)}
        resp = requests.post(url, headers=self._headers(), json=body, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书回复失败: {data}")
        return data

    @staticmethod
    def parse_text_message(event: dict[str, Any]) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        message = event.get("message", {}) or {}
        sender = event.get("sender", {}) or {}
        chat_id = message.get("chat_id")
        message_id = message.get("message_id")
        sender_open_id = ((sender.get("sender_id") or {}).get("open_id")) or None
        content = message.get("content")
        if not content:
            return sender_open_id, chat_id, message_id, None
        try:
            parsed = json.loads(content)
            return sender_open_id, chat_id, message_id, parsed.get("text")
        except Exception:
            return sender_open_id, chat_id, message_id, None
