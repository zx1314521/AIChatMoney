from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass
from typing import Any

import requests

try:
    import akshare as ak  # type: ignore
except Exception:  # pragma: no cover
    ak = None


@dataclass
class StockQuote:
    symbol: str
    name: str
    price: float
    change_pct: float
    high: float | None = None
    low: float | None = None
    open: float | None = None
    volume: float | None = None


@dataclass
class FundQuote:
    symbol: str
    name: str
    nav: float
    estimated_nav: float | None = None
    estimated_change_pct: float | None = None
    update_time: str | None = None


def _stock_secid(symbol: str) -> str:
    s = symbol.strip().lower()
    if s.startswith(("sh", "sz")):
        mkt = "1" if s.startswith("sh") else "0"
        return f"{mkt}.{s[2:]}"
    if s.startswith("6") or s.startswith("9"):
        return f"1.{s}"
    return f"0.{s}"


def get_stock_quote(symbol: str) -> StockQuote:
    secid = _stock_secid(symbol)
    fields = "f57,f58,f43,f46,f44,f45,f47,f48,f170"
    url = f"https://push2.eastmoney.com/api/qt/stock/get?fltt=2&invt=2&fields={fields}&secid={secid}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    if not data:
        raise ValueError(f"未获取到股票数据: {symbol}")

    def to_price(v: Any) -> float | None:
        if v in (None, "-"):
            return None
        return float(v) / 100

    return StockQuote(
        symbol=str(data.get("f57", symbol)),
        name=str(data.get("f58", symbol)),
        price=to_price(data.get("f43")) or 0.0,
        open=to_price(data.get("f46")),
        high=to_price(data.get("f44")),
        low=to_price(data.get("f45")),
        volume=float(data.get("f47") or 0),
        change_pct=float(data.get("f170") or 0) / 100,
    )


def get_fund_quote(symbol: str) -> FundQuote:
    url = f"https://fundgz.1234567.com.cn/js/{symbol}.js"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    m = re.search(r"jsonpgz\((\{.*\})\);?", resp.text)
    if not m:
        raise ValueError(f"未获取到基金估值: {symbol}")
    row = json.loads(m.group(1))
    nav = float(row.get("dwjz") or 0)
    gszzl = row.get("gszzl")
    return FundQuote(
        symbol=symbol,
        name=row.get("name", symbol),
        nav=nav,
        estimated_nav=float(row.get("gsz")) if row.get("gsz") else None,
        estimated_change_pct=float(gszzl) if gszzl not in (None, "") else None,
        update_time=row.get("gztime"),
    )


def get_hot_topics(limit: int = 8) -> list[str]:
    topics: list[str] = []
    if ak is not None and hasattr(ak, "stock_hot_rank_em"):
        try:
            df = ak.stock_hot_rank_em()
            for _, row in df.head(limit).iterrows():
                name = str(row.get("股票名称") or row.get("name") or row.get("股票") or "").strip()
                rank = row.get("当前排名") or row.get("排名") or ""
                change = row.get("涨跌幅") or row.get("涨跌幅%") or ""
                if name:
                    topics.append(f"{name} 排名:{rank} 涨跌幅:{change}")
        except Exception:
            topics = []
    if topics:
        return topics[:limit]

    # Fallback: 使用概念板块涨幅当作热点线索
    url = (
        "https://push2.eastmoney.com/api/qt/clist/get?"
        "pn=1&pz=20&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2"
        "&fid=f3&fs=m:90+t:3&fields=f12,f14,f2,f3"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    diff = (((resp.json() or {}).get("data") or {}).get("diff")) or []
    for item in diff[:limit]:
        name = item.get("f14")
        pct = item.get("f3")
        if name:
            topics.append(f"{name} 板块涨跌幅:{pct}%")
    return topics


def get_fund_recommendations(top_n: int = 5) -> list[dict[str, str]]:
    end = dt.date.today()
    start = end - dt.timedelta(days=365)
    url = (
        "https://fund.eastmoney.com/data/rankhandler.aspx?"
        f"op=ph&dt=kf&ft=all&rs=&gs=0&sc=6yzf&st=desc&sd={start}&ed={end}"
        "&qdii=&tabSubtype=,,,,,&pi=1&pn=50&dx=1&v=0.1"
    )
    resp = requests.get(url, timeout=12)
    resp.raise_for_status()
    text = resp.text
    m = re.search(r"datas:\[(.*)\],allRecords", text)
    if not m:
        return []
    raw = m.group(1)
    rows = re.findall(r"\"([^\"]+)\"", raw)

    picks: list[dict[str, str]] = []
    for row in rows:
        cols = row.split(",")
        if len(cols) < 2:
            continue
        code = cols[0].strip()
        name = cols[1].strip()
        if not code or not name:
            continue
        perf = ""
        for c in cols[2:]:
            s = c.strip()
            if re.fullmatch(r"-?\d+(\.\d+)?", s):
                perf = s
                break
        picks.append({"symbol": code, "name": name, "score": perf})
        if len(picks) >= top_n:
            break
    return picks
