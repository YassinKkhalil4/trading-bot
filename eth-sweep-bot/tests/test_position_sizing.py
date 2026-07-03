import pytest
from app.risk import calculate_position_size

def test_calculates_quantity_correctly(): assert calculate_position_size(100,2,100,98,104,100).quantity==1
def test_caps_quantity_by_notional(): assert calculate_position_size(100,2,100,99,102,50).quantity==0.5
def test_rejects_below_exchange_min_notional():
    with pytest.raises(ValueError, match='notional_below_exchange_min_notional'): calculate_position_size(100,2,100,98,104,100,min_notional=101)
def test_rejects_insufficient_balance():
    with pytest.raises(ValueError, match='insufficient_free_quote_balance'): calculate_position_size(100,2,100,98,104,100,free_quote_balance=50)
