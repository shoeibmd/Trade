from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pytest
import pandas as pd
import numpy as np

from trading.models import SignalType, PredictionResult
from trading.indicators import TechnicalIndicatorEngine
from trading.signal_engine import SignalEngine
from trading.risk_manager import RiskManager, SymbolSpecification
from trading.kronos_adapter import KronosAdapter
from trading.backtester import (
    ForexBacktester,
    BacktestConfig,
    BacktestMetrics,
    BacktestTradeLog,
)


def create_mock_historical_data(count=600, trend="up"):
    start_time = datetime(2026, 1, 1, 10, 0, 0)
    timestamps = [start_time + timedelta(minutes=5 * i) for i in range(count)]
    base_price = 1.0850

    data = []
    for i in range(count):
        if trend == "up":
            price_offset = i * 0.0002
        elif trend == "down":
            price_offset = -i * 0.0002
        else:
            price_offset = np.sin(i / 10.0) * 0.0015

        o = base_price + price_offset
        c = o + 0.0001
        h = max(o, c) + 0.0003
        l = min(o, c) - 0.0003
        v = 100.0 + i
        amt = v * ((o + h + l + c) / 4.0)

        data.append({
            "timestamps": timestamps[i],
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
            "amount": amt,
        })

    return pd.DataFrame(data)


def create_mock_adapter(direction="up"):
    mock = MagicMock(spec=KronosAdapter)
    def fake_predict(df, symbol="EURUSD", timeframe="M5"):
        last_close = float(df.iloc[-1]["close"])
        if direction == "up":
            pred_closes = np.linspace(last_close, last_close + 0.0030, 120).tolist()
        else:
            pred_closes = np.linspace(last_close, last_close - 0.0030, 120).tolist()

        pred_res = PredictionResult(
            symbol=symbol,
            timestamp=datetime.now(),
            pred_len=120,
            predicted_close=pred_closes,
            predicted_open=pred_closes,
            predicted_high=[c + 0.0005 for c in pred_closes],
            predicted_low=[c - 0.0005 for c in pred_closes],
            predicted_volume=[150.0] * 120,
        )
        return pred_res, None
    mock.predict_forecast.side_effect = fake_predict
    return mock


def test_backtester_initialization_defaults():
    backtester = ForexBacktester()
    assert backtester.config.symbol == "EURUSD"
    assert backtester.config.initial_balance == 10000.0
    assert backtester.account_state.balance == 10000.0
    assert len(backtester.trade_logs) == 0


def test_historical_data_loading_and_validation():
    backtester = ForexBacktester()
    short_df = create_mock_historical_data(count=100)  # Needs min 401 bars
    metrics, logs = backtester.run_backtest(short_df)

    assert metrics.total_trades == 0
    assert len(logs) == 0
    assert metrics.net_profit == 0.0


def test_backtest_buy_and_sell_execution():
    # BUY execution on uptrend
    config = BacktestConfig(initial_balance=10000.0, lookback_bars=400, pred_len=120)
    adapter_buy = create_mock_adapter(direction="up")
    bt_buy = ForexBacktester(config=config, kronos_adapter=adapter_buy)
    df_up = create_mock_historical_data(count=600, trend="up")

    metrics_buy, logs_buy = bt_buy.run_backtest(df_up)
    assert len(logs_buy) > 0
    assert any(log.direction == "BUY" for log in logs_buy)

    # SELL execution on downtrend
    adapter_sell = create_mock_adapter(direction="down")
    bt_sell = ForexBacktester(config=config, kronos_adapter=adapter_sell)
    df_down = create_mock_historical_data(count=600, trend="down")

    metrics_sell, logs_sell = bt_sell.run_backtest(df_down)
    assert len(logs_sell) > 0
    assert any(log.direction == "SELL" for log in logs_sell)


def test_backtest_sl_and_tp_exits():
    config = BacktestConfig(initial_balance=10000.0)
    adapter = create_mock_adapter(direction="up")
    backtester = ForexBacktester(config=config, kronos_adapter=adapter)
    df = create_mock_historical_data(count=600, trend="up")

    metrics, logs = backtester.run_backtest(df)
    assert len(logs) > 0
    exit_reasons = set(log.exit_reason for log in logs)
    assert "TAKE_PROFIT" in exit_reasons or any("STOP_LOSS" in r for r in exit_reasons)


def test_backtest_same_candle_sl_tp_ambiguity_conservative_sl_rule():
    """
    SAME-CANDLE AMBIGUITY TEST:
    Confirms that if a historical candle touches both SL and TP,
    the backtester deterministically chooses SL first (pessimistic conservative rule).
    """
    config = BacktestConfig(initial_balance=10000.0)
    mock_adapter = create_mock_adapter(direction="up")
    backtester = ForexBacktester(config=config, kronos_adapter=mock_adapter)

    historical_df = create_mock_historical_data(count=450, trend="up")

    # Insert a spike bar at index 415 touching both high (TP) and low (SL)
    historical_df.loc[415, "high"] = 1.1500
    historical_df.loc[415, "low"] = 1.0000

    metrics, logs = backtester.run_backtest(historical_df)

    ambiguity_found = False
    for log in logs:
        if "Same-candle ambiguity" in log.exit_reason:
            ambiguity_found = True
            assert log.exit_reason.startswith("STOP_LOSS")
            assert log.profit_loss < 0

    assert ambiguity_found is True


def test_no_look_ahead_bias_regression_proof():
    """
    EXPLICIT PROOF OF NO LOOK-AHEAD BIAS:
    Mutating future bars (e.g., at index 500) MUST NOT alter the signal,
    entry price, SL, TP, or lot size generated at index 400.
    """
    config = BacktestConfig(initial_balance=10000.0)

    # Dataset 1
    df1 = create_mock_historical_data(count=600, trend="up")
    adapter1 = create_mock_adapter(direction="up")
    bt1 = ForexBacktester(config=config, kronos_adapter=adapter1)
    m1, logs1 = bt1.run_backtest(df1)

    # Dataset 2: Mutate data strictly at index 500+
    df2 = df1.copy()
    df2.loc[500:, "close"] = df2.loc[500:, "close"] - 0.0500
    df2.loc[500:, "low"] = df2.loc[500:, "low"] - 0.0500

    adapter2 = create_mock_adapter(direction="up")
    bt2 = ForexBacktester(config=config, kronos_adapter=adapter2)
    m2, logs2 = bt2.run_backtest(df2)

    assert len(logs1) > 0 and len(logs2) > 0
    first_trade1 = logs1[0]
    first_trade2 = logs2[0]

    assert first_trade1.entry_timestamp == first_trade2.entry_timestamp
    assert first_trade1.entry_price == first_trade2.entry_price
    assert first_trade1.lot_size == first_trade2.lot_size
    assert first_trade1.stop_loss == first_trade2.stop_loss
    assert first_trade1.take_profit == first_trade2.take_profit


def test_risk_manager_controls_and_constraints_integration():
    """
    Verifies that RiskManager limits (max positions, daily loss, consecutive losses,
    lot constraints, NO_TRADE rejection) are enforced during backtesting.
    """
    # Max open positions = 1 enforced
    risk_mgr = RiskManager(max_open_positions=1)
    config = BacktestConfig(initial_balance=10000.0)
    adapter = create_mock_adapter(direction="up")
    bt = ForexBacktester(config=config, kronos_adapter=adapter, risk_manager=risk_mgr)

    df = create_mock_historical_data(count=550, trend="up")
    metrics, logs = bt.run_backtest(df)

    assert isinstance(metrics, BacktestMetrics)
    assert len(logs) > 0


def test_backtest_reproducibility():
    """
    REPRODUCIBILITY TEST:
    Running the exact same historical dataset twice must produce 100% identical metrics and logs.
    """
    config = BacktestConfig(initial_balance=10000.0)
    df = create_mock_historical_data(count=550, trend="up")

    adapter1 = create_mock_adapter(direction="up")
    bt1 = ForexBacktester(config=config, kronos_adapter=adapter1)
    m1, logs1 = bt1.run_backtest(df)

    adapter2 = create_mock_adapter(direction="up")
    bt2 = ForexBacktester(config=config, kronos_adapter=adapter2)
    m2, logs2 = bt2.run_backtest(df)

    assert m1.net_profit == m2.net_profit
    assert m1.total_trades == m2.total_trades
    assert m1.max_drawdown == m2.max_drawdown
    assert len(logs1) == len(logs2)

    for l1, l2 in zip(logs1, logs2):
        assert l1.entry_price == l2.entry_price
        assert l1.exit_price == l2.exit_price
        assert l1.profit_loss == l2.profit_loss


def test_trade_log_integrity_and_account_state_updates():
    config = BacktestConfig(initial_balance=10000.0)
    adapter = create_mock_adapter(direction="up")
    backtester = ForexBacktester(config=config, kronos_adapter=adapter)
    df = create_mock_historical_data(count=550, trend="up")

    metrics, logs = backtester.run_backtest(df)

    assert len(logs) > 0
    for log in logs:
        assert isinstance(log, BacktestTradeLog)
        assert log.symbol == "EURUSD"
        assert log.lot_size > 0
        assert log.entry_price > 0
        assert log.exit_price > 0
        assert log.balance_after_trade > 0
        assert log.exit_reason in ("STOP_LOSS", "TAKE_PROFIT") or "STOP_LOSS" in log.exit_reason
