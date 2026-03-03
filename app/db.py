from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


ENGINE = create_engine("sqlite:///money_robot.db", echo=False, future=True)


class Base(DeclarativeBase):
    pass


class Watchlist(Base):
    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_type: Mapped[str] = mapped_column(String(10), index=True)  # stock|fund
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[Optional[str]] = mapped_column(String(80), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_type: Mapped[str] = mapped_column(String(10), index=True)
    symbol: Mapped[str] = mapped_column(String(30), index=True)
    side: Mapped[str] = mapped_column(String(4))  # BUY|SELL
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class UserBinding(Base):
    __tablename__ = "user_binding"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    open_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    chat_id: Mapped[Optional[str]] = mapped_column(String(100), default=None, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


def init_db() -> None:
    Base.metadata.create_all(ENGINE)


def session_scope() -> Session:
    return Session(ENGINE)


def upsert_user_binding(open_id: str, chat_id: Optional[str]) -> None:
    with session_scope() as session:
        row = session.scalar(select(UserBinding).where(UserBinding.open_id == open_id))
        if row is None:
            row = UserBinding(open_id=open_id, chat_id=chat_id, last_seen_at=datetime.utcnow())
            session.add(row)
        else:
            row.chat_id = chat_id or row.chat_id
            row.last_seen_at = datetime.utcnow()
        session.commit()
