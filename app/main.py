from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.bot_service import BotService
from app.config import settings
from app.db import init_db, upsert_user_binding
from app.feishu_client import FeishuClient
from app.scheduler import PushScheduler


feishu = FeishuClient()
bot = BotService()
scheduler = PushScheduler(feishu, bot)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        scheduler.start()
    except Exception:
        # 定时任务失败不阻塞服务启动
        pass
    yield
    scheduler.shutdown()


app = FastAPI(title="MoneyRobot", version="0.1.0", lifespan=lifespan)


def _event_token(payload: dict[str, Any]) -> str:
    if payload.get("token"):
        return str(payload.get("token"))
    header = payload.get("header") or {}
    return str(header.get("token") or "")


def _strip_mention_keys(event: dict[str, Any], text: str | None) -> str | None:
    if text is None:
        return None
    message = event.get("message") or {}
    mentions = message.get("mentions") or []
    cleaned = text
    for mention in mentions:
        key = mention.get("key")
        if key:
            cleaned = cleaned.replace(str(key), " ")
    return " ".join(cleaned.split())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/feishu/events")
def feishu_events(payload: dict[str, Any]) -> dict[str, Any]:
    print("收到事件:", payload)
    # 飞书 URL 校验
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}

    if settings.feishu_verification_token:
        token = _event_token(payload)
        if token != settings.feishu_verification_token:
            return {"ok": False, "error": "invalid verification token"}

    header = payload.get("header") or {}
    if header.get("event_type") != "im.message.receive_v1":
        return {"ok": True}

    event = payload.get("event") or {}
    sender_open_id, chat_id, message_id, text = feishu.parse_text_message(event)
    text = _strip_mention_keys(event, text)
    if not message_id:
        return {"ok": True}

    if sender_open_id:
        upsert_user_binding(sender_open_id, chat_id)

    reply = bot.handle_text(text)
    try:
        feishu.reply_text(message_id, reply)
    except Exception as e:
        # 回复失败时返回错误便于飞书重试
        return {"ok": False, "error": str(e)}
    return {"ok": True}


@app.post("/admin/push")
def manual_push() -> dict[str, Any]:
    text = bot.daily_report()
    targets: list[dict[str, str]] = []
    if settings.default_open_id:
        feishu.send_text(text, receive_id_type="open_id", receive_id=settings.default_open_id)
        targets.append({"receive_id_type": "open_id", "receive_id": settings.default_open_id})
    if settings.default_chat_id:
        feishu.send_text(text, receive_id_type="chat_id", receive_id=settings.default_chat_id)
        targets.append({"receive_id_type": "chat_id", "receive_id": settings.default_chat_id})
    return {"ok": True, "targets": targets}
