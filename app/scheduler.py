from __future__ import annotations

from dataclasses import dataclass

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.bot_service import BotService
from app.config import settings
from app.db import UserBinding, session_scope
from app.feishu_client import FeishuClient
from app.market_data import get_fund_quote, get_hot_topics, get_stock_quote
from app.trading import PortfolioService


@dataclass
class PriceState:
    last_price: float


class PushScheduler:
    def __init__(self, feishu_client: FeishuClient, bot_service: BotService) -> None:
        self.feishu = feishu_client
        self.bot = bot_service
        self.scheduler = BackgroundScheduler(timezone=settings.tz)
        self.portfolio = PortfolioService()
        self.price_state: dict[tuple[str, str], PriceState] = {}

    def _targets(self) -> list[tuple[str, str]]:
        targets: list[tuple[str, str]] = []
        with session_scope() as session:
            users = session.query(UserBinding).all()
            for u in users:
                if u.open_id:
                    targets.append(("open_id", u.open_id))
        if settings.default_open_id:
            targets.append(("open_id", settings.default_open_id))
        if settings.default_chat_id:
            targets.append(("chat_id", settings.default_chat_id))
        # 去重
        return list(dict.fromkeys(targets))

    def _push_report(self) -> None:
        text = self.bot.daily_report()
        for receive_id_type, receive_id in self._targets():
            try:
                self.feishu.send_text(text, receive_id_type=receive_id_type, receive_id=receive_id)
            except Exception:
                continue

    def _push_hot_summary(self) -> None:
        hot = get_hot_topics(limit=8)
        analysis = self.bot.ai.analyze_hot_topics(hot)
        text = "热点摘要:\n" + "\n".join(f"- {x}" for x in hot) + f"\n\nAI分析:\n{analysis}"
        for receive_id_type, receive_id in self._targets():
            try:
                self.feishu.send_text(text, receive_id_type=receive_id_type, receive_id=receive_id)
            except Exception:
                continue

    def _current_price(self, asset_type: str, symbol: str) -> float | None:
        try:
            if asset_type == "stock":
                return float(get_stock_quote(symbol).price)
            if asset_type == "fund":
                f = get_fund_quote(symbol)
                return float(f.estimated_nav or f.nav)
        except Exception:
            return None
        return None

    def _price_alert_check(self) -> None:
        watch = self.portfolio.list_watch()
        alerts: list[str] = []
        threshold = abs(settings.price_alert_threshold_pct)
        for w in watch:
            key = (w.asset_type, w.symbol)
            price = self._current_price(w.asset_type, w.symbol)
            if price is None or price <= 0:
                continue
            prev = self.price_state.get(key)
            if prev and prev.last_price > 0:
                pct = (price - prev.last_price) / prev.last_price * 100
                if abs(pct) >= threshold:
                    direction = "上涨" if pct > 0 else "下跌"
                    alerts.append(
                        f"{w.asset_type}:{w.symbol} {direction}{pct:.2f}% (上次:{prev.last_price:.4f} 当前:{price:.4f})"
                    )
            self.price_state[key] = PriceState(last_price=price)

        if not alerts:
            return
        text = "价格异动提醒(单次采样变化超过阈值):\n" + "\n".join(f"- {a}" for a in alerts)
        for receive_id_type, receive_id in self._targets():
            try:
                self.feishu.send_text(text, receive_id_type=receive_id_type, receive_id=receive_id)
            except Exception:
                continue

    @staticmethod
    def _parse_hot_times(value: str) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for raw in [x.strip() for x in value.split(",") if x.strip()]:
            if ":" not in raw:
                continue
            h, m = raw.split(":", 1)
            try:
                hh = int(h)
                mm = int(m)
            except ValueError:
                continue
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                result.append((hh, mm))
        return result

    def start(self) -> None:
        # 兼容旧配置: 若 report_cron 配置合法，仍保留日报任务
        cron = settings.report_cron.split()
        if len(cron) == 5:
            trigger = CronTrigger.from_crontab(settings.report_cron, timezone=settings.tz)
            self.scheduler.add_job(self._push_report, trigger=trigger, id="daily-report", replace_existing=True)

        # 工作日固定热点摘要推送（默认 09:30、14:30）
        for idx, (hh, mm) in enumerate(self._parse_hot_times(settings.hot_push_times)):
            self.scheduler.add_job(
                self._push_hot_summary,
                trigger=CronTrigger(day_of_week="mon-fri", hour=hh, minute=mm, timezone=settings.tz),
                id=f"hot-summary-{idx}",
                replace_existing=True,
            )

        # 每5分钟检查一次自选价格异动
        try:
            price_trigger = CronTrigger.from_crontab(settings.price_alert_cron, timezone=settings.tz)
        except Exception:
            price_trigger = CronTrigger(day_of_week="mon-fri", minute="*/5", timezone=settings.tz)
        self.scheduler.add_job(
            self._price_alert_check,
            trigger=price_trigger,
            id="price-alert",
            replace_existing=True,
        )
        self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
