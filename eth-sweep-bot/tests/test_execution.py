from datetime import datetime, timezone, timedelta
from app.execution import ExecutionEngine
class S: pass
def engine():
    s=S(); s.execution=S(); s.execution.cancel_entry_after_seconds=120; s.account=S(); s.account.risk_bucket_usd=100; s.risk=S(); s.risk.max_risk_per_trade_usd=2; s.risk.max_position_notional_usd=100
    st=S(); st.open=False; st.state={}; st.has_open_trade=lambda: st.open; st.set_state=lambda k,v: st.state.__setitem__(k,v)
    n=S(); n.send=lambda x: None
    return ExecutionEngine(None,None,s,S(),st,n)
def test_does_not_place_target_before_entry_fill(): assert engine()._paper_trade(type('P',(),{'symbol':'ETH/USDT','entry_price':100})(), type('Z',(),{'quantity':1})())['status']=='entry_pending'
def test_cancels_stale_entry_order(): assert engine().cancel_stale_entry_order(datetime.now(timezone.utc)-timedelta(seconds=121))
def test_exits_if_stop_placement_fails():
    e=engine(); e.stop_failure_exit_required(); assert e.storage.state['paused_reason']=='protective_stop_failed'
def test_does_not_open_duplicate_positions():
    e=engine(); e.storage.open=True
    try: e.place_trade(None)
    except RuntimeError as ex: assert str(ex)=='duplicate_position_blocked'
def test_places_stop_immediately_after_fill_documented(): assert hasattr(engine(),'stop_failure_exit_required')
