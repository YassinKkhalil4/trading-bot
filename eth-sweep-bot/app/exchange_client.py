from __future__ import annotations
import ccxt
from loguru import logger

class ExchangeClient:
    def __init__(self, settings, runtime):
        self.settings=settings; self.runtime=runtime; self.mode=runtime.mode
        opts={'enableRateLimit': True, 'options': {'defaultType': 'spot'}}
        if self.mode in {'testnet','live'}:
            opts.update({'apiKey': runtime.binance_api_key, 'secret': runtime.binance_api_secret})
        self.exchange=getattr(ccxt, settings.exchange.id)(opts)
        if self.mode == 'testnet': self.exchange.set_sandbox_mode(True)
    def load_markets(self): return self.exchange.load_markets()
    def validate_symbol(self):
        markets=self.load_markets()
        if self.settings.exchange.symbol not in markets: raise RuntimeError('configured symbol unavailable')
        return markets[self.settings.exchange.symbol]
    def check_connectivity(self):
        if self.mode in {'testnet','live'}: self.exchange.fetch_balance()
        else: self.exchange.fetch_ticker(self.settings.exchange.symbol)
    def create_order(self,*args,**kwargs):
        if self.mode == 'paper': raise RuntimeError('paper mode must not call private order endpoints')
        return self.exchange.create_order(*args,**kwargs)
    def cancel_order(self,*args,**kwargs):
        if self.mode == 'paper': return {'status':'canceled','paper':True}
        return self.exchange.cancel_order(*args,**kwargs)
    def fetch_open_orders(self, symbol):
        if self.mode == 'paper': return []
        return self.exchange.fetch_open_orders(symbol)
