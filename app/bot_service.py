from __future__ import annotations

from typing import Optional

from app.ai_client import AIClient
from app.market_data import get_fund_quote, get_fund_recommendations, get_hot_topics, get_stock_quote
from app.trading import PortfolioService


class BotService:
    def __init__(self) -> None:
        self.portfolio = PortfolioService()
        self.ai = AIClient()

    def _help(self) -> str:
        return (
            "可用命令:\n"
            "help\n"
            "quote 股票代码           例如: quote 600519\n"
            "fund 基金代码            例如: fund 161725\n"
            "analyze stock 代码       例如: analyze stock 600519\n"
            "analyze fund 代码        例如: analyze fund 161725\n"
            "hot                     查看热点+分析\n"
            "ai list                 查看AI provider列表\n"
            "ai use provider         切换当前AI provider(进程内)\n"
            "funds [N]               推荐基金\n"
            "plan 金额 期数           例如: plan 12000 12\n"
            "add stock 代码 [名称]\n"
            "add fund 代码 [名称]\n"
            "watch                   查看自选\n"
            "buy stock|fund 代码 数量 价格 [手续费]\n"
            "sell stock|fund 代码 数量 价格 [手续费]\n"
            "portfolio               查看持仓与收益"
        )

    @staticmethod
    def _stock_context(symbol: str) -> str:
        q = get_stock_quote(symbol)
        return (
            f"代码:{q.symbol}\n"
            f"名称:{q.name}\n"
            f"现价:{q.price}\n"
            f"涨跌幅:{q.change_pct}%\n"
            f"开盘:{q.open}\n"
            f"最高:{q.high}\n"
            f"最低:{q.low}\n"
            f"成交量:{q.volume}"
        )

    @staticmethod
    def _fund_context(symbol: str) -> str:
        f = get_fund_quote(symbol)
        return (
            f"代码:{f.symbol}\n"
            f"名称:{f.name}\n"
            f"单位净值:{f.nav}\n"
            f"估值:{f.estimated_nav}\n"
            f"估涨跌:{f.estimated_change_pct}%\n"
            f"更新时间:{f.update_time}"
        )

    def _portfolio_report(self) -> str:
        positions = self.portfolio.list_positions()
        if not positions:
            return "当前没有模拟持仓。"
        lines = ["模拟持仓:"]
        total_mv = 0.0
        total_cost = 0.0
        total_realized = 0.0
        for p in positions:
            if p.quantity <= 0:
                continue
            price = 0.0
            try:
                if p.asset_type == "stock":
                    price = get_stock_quote(p.symbol).price
                else:
                    fq = get_fund_quote(p.symbol)
                    price = fq.estimated_nav or fq.nav
            except Exception:
                price = 0.0

            mv = p.quantity * price
            cost = p.quantity * p.avg_cost
            pnl = mv - cost
            total_mv += mv
            total_cost += cost
            total_realized += p.realized_pnl
            lines.append(
                f"- {p.asset_type}:{p.symbol} 数量:{p.quantity:.2f} 成本:{p.avg_cost:.4f} "
                f"现价:{price:.4f} 浮盈:{pnl:.2f} 已实现:{p.realized_pnl:.2f}"
            )
        total_float = total_mv - total_cost
        lines.append(f"汇总 浮盈:{total_float:.2f} 已实现:{total_realized:.2f} 总收益:{total_float + total_realized:.2f}")
        return "\n".join(lines)

    def _watch_report(self) -> str:
        watch = self.portfolio.list_watch()
        if not watch:
            return "自选为空。"
        lines = ["自选列表:"]
        for w in watch:
            label = w.name or ""
            if w.asset_type == "stock":
                try:
                    q = get_stock_quote(w.symbol)
                    lines.append(f"- stock:{w.symbol} {q.name} 现价:{q.price} 涨跌:{q.change_pct}% {label}".strip())
                except Exception:
                    lines.append(f"- stock:{w.symbol} {label}".strip())
            else:
                try:
                    f = get_fund_quote(w.symbol)
                    est = f" 估值:{f.estimated_nav}" if f.estimated_nav else ""
                    chg = f" 估涨跌:{f.estimated_change_pct}%" if f.estimated_change_pct is not None else ""
                    lines.append(f"- fund:{w.symbol} {f.name} 净值:{f.nav}{est}{chg} {label}".strip())
                except Exception:
                    lines.append(f"- fund:{w.symbol} {label}".strip())
        return "\n".join(lines)

    def _make_plan(self, amount: float, periods: int) -> str:
        picks = get_fund_recommendations(top_n=4)
        if not picks:
            return "暂无可用基金推荐数据。"
        per_period = amount / periods
        per_fund = per_period / len(picks)
        lines = [f"定投计划: 总金额 {amount:.2f}, 共 {periods} 期, 每期 {per_period:.2f}"]
        for p in picks:
            lines.append(f"- {p['symbol']} {p['name']} 每期投入 {per_fund:.2f}")
        lines.append("建议: 每月固定日期执行，单只基金占比不超过30%，回撤超15%时暂停加仓复盘。")
        return "\n".join(lines)

    def daily_report(self) -> str:
        hot = get_hot_topics(limit=5)
        analysis = self.ai.analyze_hot_topics(hot)
        return f"{self._portfolio_report()}\n\n今日热点:\n" + "\n".join(f"- {x}" for x in hot) + f"\n\nAI分析:\n{analysis}"

    def handle_text(self, text: Optional[str]) -> str:
        if not text:
            return self._help()
        txt = text.strip()
        parts = txt.split()
        cmd = parts[0].lower()

        try:
            if cmd in {"help", "h", "?"}:
                return self._help()

            if cmd == "quote" and len(parts) >= 2:
                return self._stock_context(parts[1])

            if cmd == "fund" and len(parts) >= 2:
                return self._fund_context(parts[1])

            if cmd == "analyze" and len(parts) >= 3:
                asset_type = parts[1].lower()
                symbol = parts[2]
                if asset_type == "stock":
                    context = self._stock_context(symbol)
                elif asset_type == "fund":
                    context = self._fund_context(symbol)
                else:
                    return "analyze 仅支持 stock/fund。"
                analysis = self.ai.analyze_asset(asset_type, symbol, context)
                return f"{context}\n\nAI分析:\n{analysis}"

            if cmd == "hot":
                hot = get_hot_topics(limit=8)
                analysis = self.ai.analyze_hot_topics(hot)
                return "热点:\n" + "\n".join(f"- {x}" for x in hot) + "\n\nAI分析:\n" + analysis

            if cmd == "ai" and len(parts) >= 2:
                sub = parts[1].lower()
                if sub == "list":
                    statuses = self.ai.list_providers()
                    lines = ["AI providers:"]
                    for s in statuses:
                        lines.append(
                            f"- {s.name} active:{s.active} enabled:{s.enabled_in_list} "
                            f"configured:{s.configured} model:{s.model} base_url:{s.base_url}"
                        )
                    return "\n".join(lines)
                if sub == "use" and len(parts) >= 3:
                    current = self.ai.set_active_provider(parts[2])
                    return f"已切换AI provider: {current}"
                return "用法: ai list | ai use <provider>"

            if cmd == "funds":
                top_n = int(parts[1]) if len(parts) >= 2 else 5
                picks = get_fund_recommendations(top_n=top_n)
                if not picks:
                    return "暂无可用基金推荐数据。"
                lines = ["基金推荐(按近一年收益排序):"]
                for p in picks:
                    lines.append(f"- {p['symbol']} {p['name']} 参考收益:{p['score']}")
                lines.append("提示: 推荐仅供研究，不构成投资建议。")
                return "\n".join(lines)

            if cmd == "plan" and len(parts) >= 3:
                amount = float(parts[1])
                periods = int(parts[2])
                return self._make_plan(amount, periods)

            if cmd == "add" and len(parts) >= 3:
                asset_type = parts[1].lower()
                symbol = parts[2]
                name = " ".join(parts[3:]) if len(parts) > 3 else None
                if asset_type not in {"stock", "fund"}:
                    return "资产类型仅支持 stock/fund。"
                self.portfolio.add_watch(asset_type, symbol, name)
                return f"已加入自选: {asset_type} {symbol}"

            if cmd == "watch":
                return self._watch_report()

            if cmd in {"buy", "sell"} and len(parts) >= 5:
                side = "BUY" if cmd == "buy" else "SELL"
                asset_type = parts[1].lower()
                symbol = parts[2]
                quantity = float(parts[3])
                price = float(parts[4])
                fee = float(parts[5]) if len(parts) >= 6 else 0.0
                if asset_type not in {"stock", "fund"}:
                    return "资产类型仅支持 stock/fund。"
                self.portfolio.record_trade(
                    asset_type=asset_type,
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=price,
                    fee=fee,
                )
                return f"已记录 {cmd.upper()}: {asset_type} {symbol} 数量:{quantity} 价格:{price}"

            if cmd == "portfolio":
                return self._portfolio_report()

            return "无法识别命令，发送 help 查看可用命令。"
        except Exception as e:
            return f"处理失败: {e}"
