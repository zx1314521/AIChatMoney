from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select

from app.db import Trade, Watchlist, session_scope


@dataclass
class Position:
    asset_type: str
    symbol: str
    quantity: float
    avg_cost: float
    realized_pnl: float


class PortfolioService:
    def add_watch(self, asset_type: str, symbol: str, name: str | None = None) -> None:
        with session_scope() as session:
            exists = session.scalar(
                select(Watchlist).where(Watchlist.asset_type == asset_type, Watchlist.symbol == symbol)
            )
            if exists:
                return
            session.add(Watchlist(asset_type=asset_type, symbol=symbol, name=name))
            session.commit()

    def list_watch(self) -> list[Watchlist]:
        with session_scope() as session:
            rows = session.scalars(select(Watchlist).order_by(Watchlist.asset_type, Watchlist.symbol)).all()
            return list(rows)

    def record_trade(
        self, *, asset_type: str, symbol: str, side: str, quantity: float, price: float, fee: float = 0.0, note: str | None = None
    ) -> None:
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side 只能是 BUY 或 SELL")
        if quantity <= 0 or price <= 0:
            raise ValueError("quantity 和 price 必须大于 0")
        with session_scope() as session:
            session.add(
                Trade(asset_type=asset_type, symbol=symbol, side=side, quantity=quantity, price=price, fee=fee, note=note)
            )
            session.commit()

    def _position_from_trades(self, asset_type: str, symbol: str, trades: Iterable[Trade]) -> Position:
        qty = 0.0
        cost = 0.0
        realized = 0.0
        for t in trades:
            if t.asset_type != asset_type or t.symbol != symbol:
                continue
            if t.side == "BUY":
                qty += t.quantity
                cost += t.quantity * t.price + t.fee
            else:
                if qty <= 0:
                    continue
                avg_cost = cost / qty
                sell_qty = min(t.quantity, qty)
                realized += sell_qty * (t.price - avg_cost) - t.fee
                qty -= sell_qty
                cost -= sell_qty * avg_cost
        avg = (cost / qty) if qty > 0 else 0.0
        return Position(asset_type=asset_type, symbol=symbol, quantity=qty, avg_cost=avg, realized_pnl=realized)

    def list_positions(self) -> list[Position]:
        with session_scope() as session:
            all_trades = session.scalars(select(Trade).order_by(Trade.created_at, Trade.id)).all()
        keys = sorted({(t.asset_type, t.symbol) for t in all_trades})
        result: list[Position] = []
        for asset_type, symbol in keys:
            result.append(self._position_from_trades(asset_type, symbol, all_trades))
        return result
