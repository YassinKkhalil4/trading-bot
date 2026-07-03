from datetime import datetime, timezone, timedelta
from app.execution import ExecutionEngine
from app.storage import Storage
from app.models import Signal, Retest, TradePlan, Candle, Ticker
from app.config import Settings, RuntimeConfig
import yaml

class DummyNotifier:
    def send(self, text): pass
class DummyMarket:
    def __init__(self, tickers): self.tickers=tickers
    def fetch_ticker(self, symbol): return self.tickers.pop(0) if self.tickers else Ticker(120,121,120)
class DummyExchange:
    mode='paper'

def settings(tmp_path):
    data=yaml.safe_load(open('config/settings.yaml')); data['storage']['sqlite_path']=str(tmp_path/'bot.db'); return Settings(**data)
def plan():
    sig=Signal('bullish_sweep_reclaim',100,99,101,datetime.now(timezone.utc)); ret=Retest(Candle(datetime.now(timezone.utc),1,105,100,101,1),105)
    return TradePlan('ETH/USDT','buy',105,99,117,2,sig,ret)
def engine(tmp_path, tickers):
    s=settings(tmp_path); st=Storage(s.storage.sqlite_path); runtime=RuntimeConfig(mode='paper')
    risk=type('R',(),{'cairo_date':lambda self:'2026-01-01','cairo_week':lambda self:'2026-W01'})()
    return ExecutionEngine(DummyExchange(), DummyMarket(tickers), s, runtime, st, DummyNotifier(), risk), st

def test_does_not_place_target_before_entry_fill(tmp_path):
    e, st=engine(tmp_path, [Ticker(110,111,110)])
    trade_id=e.place_trade(plan(), signal_id=None, market_limits={})
    trade=st.get_open_trade()
    assert trade['status']=='entry_pending' and trade['target_order_id'] is None

def test_places_stop_immediately_after_paper_fill(tmp_path):
    e, st=engine(tmp_path, [Ticker(104,105,105)])
    e.place_trade(plan(), signal_id=None, market_limits={}); e.monitor_open_trade(); trade=st.get_open_trade()
    assert trade['status']=='open' and trade['stop_order_id']=='paper-stop'

def test_paper_lifecycle_closes_target_and_updates_stats(tmp_path):
    e, st=engine(tmp_path, [Ticker(104,105,105), Ticker(117,118,117)])
    e.place_trade(plan(), signal_id=None, market_limits={}); e.monitor_open_trade(); e.monitor_open_trade()
    closed=st.conn.execute('select * from trades where status="closed"').fetchone()
    assert closed['close_reason']=='target_hit' and st.daily('2026-01-01')['trades_taken']==1

def test_cancels_stale_entry_order(tmp_path):
    e,_=engine(tmp_path, [])
    assert e.cancel_stale_entry_order(datetime.now(timezone.utc)-timedelta(seconds=121))

def test_exits_if_stop_placement_fails(tmp_path):
    e, st=engine(tmp_path, [])
    e.stop_failure_exit_required(); assert st.get_state('paused_reason')=='protective_stop_failed'

def test_does_not_open_duplicate_positions(tmp_path):
    e, _=engine(tmp_path, [])
    e.place_trade(plan(), signal_id=None, market_limits={})
    try: e.place_trade(plan(), signal_id=None, market_limits={})
    except RuntimeError as ex: assert str(ex)=='duplicate_position_blocked'
