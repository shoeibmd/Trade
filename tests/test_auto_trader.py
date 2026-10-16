"""
Unit Tests for AutoTradingController and REST endpoints.
"""

from unittest.mock import MagicMock
import pytest
from trading.auto_trader import AutoTradingController, AutoTraderConfig
from trading.risk_manager import SymbolSpecification


def test_autotrader_start_stop_lifecycle():
    controller = AutoTradingController()
    assert controller.is_running is False

    ok, msg = controller.start_trading()
    assert ok is True
    assert controller.is_running is True

    ok_stop, msg_stop = controller.stop_trading()
    assert ok_stop is True
    assert controller.is_running is False


def test_autotrader_manual_lot_size_validation():
    controller = AutoTradingController()
    spec = SymbolSpecification(symbol="EURUSD", min_volume=0.01, max_volume=100.0, volume_step=0.01)

    # Valid lot
    ok, msg = controller.validate_manual_lot_size(0.50, spec)
    assert ok is True

    # Too small
    ok_small, msg_small = controller.validate_manual_lot_size(0.005, spec)
    assert ok_small is False
    assert "below minimum broker volume" in msg_small

    # Too large
    ok_large, msg_large = controller.validate_manual_lot_size(150.0, spec)
    assert ok_large is False
    assert "exceeds maximum broker volume" in msg_large


def test_live_mode_rejected_safety_gate():
    config = AutoTraderConfig(system_mode="LIVE", live_trading_enabled=True)
    controller = AutoTradingController(config=config)

    ok, msg = controller.start_trading()
    assert ok is False
    assert "SAFETY REJECTED" in msg
