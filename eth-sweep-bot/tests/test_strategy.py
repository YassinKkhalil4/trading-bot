from datetime import datetime, timezone, timedelta
from app.models import Candle
from app.strategy import detect_bullish_sweep, detect_retest, build_trade_plan

def c(i,o=100,h=101,l=99,cl=100): return Candle(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(minutes=5*i),o,h,l,cl,1)
def test_detects_bullish_sweep_correctly():
    candles=[c(i,l=100+i*0.01) for i in range(12)]+[c(13,o=100,h=102,l=99.5,cl=100.2)]
    assert detect_bullish_sweep(candles,12,0.05).level==100
def test_rejects_sweep_without_reclaim():
    candles=[c(i,l=100) for i in range(12)]+[c(13,o=100,h=101,l=99,cl=99.5)]
    assert detect_bullish_sweep(candles,12,0.05) is None
def test_rejects_no_sweep():
    assert detect_bullish_sweep([c(i,l=100) for i in range(13)],12,0.05) is None
def test_rejects_huge_candle():
    candles=[c(i,l=100) for i in range(12)]+[c(13,o=100,h=120,l=99,cl=101)]
    assert detect_bullish_sweep(candles,12,0.015) is None
def test_detects_valid_retest():
    sig=detect_bullish_sweep([c(i,l=100) for i in range(12)]+[c(13,o=100,h=102,l=99,cl=101)],12,0.05)
    ret=detect_retest([c(14,o=101,h=103,l=100.05,cl=101)],sig,5,0.001)
    assert ret.trigger_price==103
def test_rejects_retest_breaking_sweep_low():
    sig=detect_bullish_sweep([c(i,l=100) for i in range(12)]+[c(13,o=100,h=102,l=99,cl=101)],12,0.05)
    assert detect_retest([c(14,l=98.9,cl=100)],sig,5,0.001) is None
    assert sig.rejection_reason=='retest_broke_sweep_low'
def test_builds_correct_entry_stop_target():
    sig=detect_bullish_sweep([c(i,l=100) for i in range(12)]+[c(13,o=100,h=102,l=99,cl=101)],12,0.05)
    ret=detect_retest([c(14,h=103,l=100.05,cl=101)],sig,5,0.001)
    plan=build_trade_plan('ETH/USDT',sig,ret,0.0005,2.0,2.0)
    assert plan.entry_price==103 and round(plan.stop_price,4)==98.9505 and round(plan.target_price,4)==111.099
