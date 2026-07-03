from __future__ import annotations
from datetime import datetime, timezone
from .models import Candle, Ticker
class MarketData:
    def __init__(self, exchange): self.exchange=exchange
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> list[Candle]:
        rows=self.exchange.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        candles=[Candle(datetime.fromtimestamp(r[0]/1000, tz=timezone.utc), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in rows]
        return candles[:-1] if candles else []
    def fetch_ticker(self, symbol: str) -> Ticker:
        t=self.exchange.exchange.fetch_ticker(symbol); return Ticker(t.get('bid'), t.get('ask'), t.get('last'))
    def fetch_order_book(self, symbol: str, limit: int=5): return self.exchange.exchange.fetch_order_book(symbol, limit=limit)
    def get_spread_pct(self, symbol: str) -> float:
        ob=self.fetch_order_book(symbol); bid=ob['bids'][0][0]; ask=ob['asks'][0][0]; mid=(bid+ask)/2; return (ask-bid)/mid
