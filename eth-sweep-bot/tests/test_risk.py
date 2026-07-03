from datetime import datetime
import pytz
from app.config import Settings
from app.risk import RiskEngine, validate_trade_plan
from app.models import Signal, Retest, TradePlan, Candle
import yaml

def settings(): return Settings(**yaml.safe_load(open('config/settings.yaml')))
def test_rejects_after_daily_loss(): assert RiskEngine(settings()).can_trade_now({'realized_pnl_usd':-4,'trades_taken':0,'losses':0}, None, now=pytz.timezone('Africa/Cairo').localize(datetime(2026,1,1,17))).reason=='max_daily_loss_hit'
def test_rejects_after_weekly_loss(): assert RiskEngine(settings()).can_trade_now(None, {'realized_pnl_usd':-12}, now=pytz.timezone('Africa/Cairo').localize(datetime(2026,1,1,17))).reason=='max_weekly_loss_hit'
def test_rejects_after_max_trades(): assert RiskEngine(settings()).can_trade_now({'realized_pnl_usd':0,'trades_taken':2,'losses':0}, None, now=pytz.timezone('Africa/Cairo').localize(datetime(2026,1,1,17))).reason=='max_trades_per_day_hit'
def test_rejects_after_max_losses(): assert RiskEngine(settings()).can_trade_now({'realized_pnl_usd':0,'trades_taken':0,'losses':2}, None, now=pytz.timezone('Africa/Cairo').localize(datetime(2026,1,1,17))).reason=='max_losses_per_day_hit'
def test_rejects_outside_window(): assert RiskEngine(settings()).can_trade_now(now=pytz.timezone('Africa/Cairo').localize(datetime(2026,1,1,12))).reason=='outside_trading_window'
def test_rejects_low_rr():
    s=settings(); sig=Signal('x',100,99,101,datetime.now()); ret=Retest(Candle(datetime.now(),1,1,1,1,1),101); p=TradePlan('ETH/USDT','buy',101,100,101.5,0.5,sig,ret)
    assert validate_trade_plan(p,s,{}).reason=='reward_risk_below_minimum'
def test_rejects_exceeding_max_notional_via_min_notional():
    s=settings(); sig=Signal('x',100,99,101,datetime.now()); ret=Retest(Candle(datetime.now(),1,1,1,1,1),1000); p=TradePlan('ETH/USDT','buy',1000,990,1020,2,sig,ret)
    assert validate_trade_plan(p,s,{'min_notional':101}).reason=='notional_below_exchange_min_notional'
