import os
from pathlib import Path
import pytest
import yaml

from trading.models import (
    BarData,
    Position,
    PredictionResult,
    SignalType,
    TickData,
    TradingSignal,
)


def test_required_directories_exist():
    root_dir = Path(__file__).parent.parent
    required_dirs = ["trading", "config", "data", "logs", "scripts"]
    for d in required_dirs:
        dir_path = root_dir / d
        assert dir_path.exists(), f"Required directory {d} does not exist."
        assert dir_path.is_dir(), f"{d} is not a directory."


def test_configuration_file_loads():
    root_dir = Path(__file__).parent.parent
    config_path = root_dir / "config" / "config.yaml"
    assert config_path.exists(), "config/config.yaml does not exist."

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    assert "system" in config
    assert config["system"]["mode"] == "PAPER"
    assert "mt5" in config
    assert "EURUSD" in config["mt5"]["symbols"]
    assert "kronos" in config
    assert config["kronos"]["lookback"] == 400
    assert "strategy" in config
    assert "risk" in config
    assert "safety" in config
    assert config["safety"]["live_trading_enabled"] is False


def test_env_example_file_exists():
    root_dir = Path(__file__).parent.parent
    env_example = root_dir / ".env.example"
    assert env_example.exists(), ".env.example does not exist."


def test_kronos_imports_remain_functional():
    from model import Kronos, KronosPredictor, KronosTokenizer, get_model_class

    assert Kronos is not None
    assert KronosTokenizer is not None
    assert KronosPredictor is not None
    assert get_model_class("kronos") == Kronos


def test_trading_models_instantiation():
    from datetime import datetime

    now = datetime.now()
    tick = TickData(symbol="EURUSD", timestamp=now, bid=1.0850, ask=1.0852)
    assert abs(tick.spread - 0.0002) < 1e-6

    bar = BarData(
        symbol="EURUSD",
        timeframe="M5",
        timestamp=now,
        open=1.0850,
        high=1.0860,
        low=1.0845,
        close=1.0855,
        volume=100.0,
    )
    assert bar.to_dict()["close"] == 1.0855

    pred = PredictionResult(
        symbol="EURUSD",
        timestamp=now,
        pred_len=5,
        predicted_close=[1.0856, 1.0858, 1.0860, 1.0862, 1.0865],
    )
    assert len(pred.predicted_close) == 5

    signal = TradingSignal(
        symbol="EURUSD",
        timestamp=now,
        signal_type=SignalType.BUY,
        score=85.0,
        predicted_change_pct=0.0015,
    )
    assert signal.signal_type == SignalType.BUY

    pos = Position(
        position_id="POS_001",
        symbol="EURUSD",
        signal_type=SignalType.BUY,
        volume=0.1,
        open_price=1.0850,
        current_price=1.0855,
        unrealized_pnl=5.0,
    )
    assert pos.volume == 0.1
