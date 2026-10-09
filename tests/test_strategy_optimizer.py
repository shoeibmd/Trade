from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pytest
import pandas as pd
import numpy as np
import yaml

from trading.models import PredictionResult
from trading.kronos_adapter import KronosAdapter
from trading.strategy_optimizer import (
    StrategyOptimizer,
    EvaluationConfig,
    OptimizationCandidate,
    OptimizationReport,
)


def create_mock_historical_data(count=1200, trend="up"):
    start_time = datetime(2026, 1, 1, 10, 0, 0)
    timestamps = [start_time + timedelta(minutes=5 * i) for i in range(count)]
    base_price = 1.0850

    data = []
    for i in range(count):
        if trend == "up":
            price_offset = i * 0.00015
        elif trend == "down":
            price_offset = -i * 0.00015
        else:
            price_offset = np.sin(i / 15.0) * 0.0020

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


def test_strategy_optimizer_initialization_defaults():
    optimizer = StrategyOptimizer()
    assert optimizer.config.symbol == "EURUSD"
    assert optimizer.config.dev_split_ratio == 0.5
    assert optimizer.config.val_split_ratio == 0.25
    assert optimizer.config.oos_split_ratio == 0.25


def test_baseline_evaluation_reproducibility():
    optimizer = StrategyOptimizer()
    df = create_mock_historical_data(count=600, trend="up")

    m1 = optimizer.evaluate_baseline(df)
    m2 = optimizer.evaluate_baseline(df)

    assert m1.net_profit == m2.net_profit
    assert m1.total_trades == m2.total_trades
    assert m1.win_rate_pct == m2.win_rate_pct


def test_chronological_data_splits_and_anti_overfitting_search():
    optimizer = StrategyOptimizer()
    df = create_mock_historical_data(count=1200, trend="up")

    param_grid = [
        {"minimum_signal_score": 70, "risk_per_trade_percent": 1.0},
        {"minimum_signal_score": 75, "risk_per_trade_percent": 1.0},
    ]

    report = optimizer.run_controlled_optimization(df, candidate_param_grid=param_grid)

    assert isinstance(report, OptimizationReport)
    assert report.total_bars == 1200
    assert report.dev_bars == 600
    assert report.val_bars == 300
    assert report.oos_bars == 300
    assert report.best_candidate is not None
    assert report.best_candidate.untouched_oos_metrics is not None


def test_transaction_cost_and_spread_sensitivity():
    optimizer = StrategyOptimizer()
    df = create_mock_historical_data(count=600, trend="up")

    cost_results = optimizer.analyze_cost_sensitivity(df)

    assert "spread_0_points" in cost_results
    assert "spread_10_points" in cost_results
    assert "spread_20_points" in cost_results
    # Profit decreases or stays equal as transaction cost increases
    assert cost_results["spread_0_points"]["net_profit"] >= cost_results["spread_20_points"]["net_profit"]


def test_empty_or_insufficient_dataset_handling():
    optimizer = StrategyOptimizer()
    empty_report = optimizer.run_controlled_optimization(pd.DataFrame())

    assert empty_report.total_bars == 0
    assert empty_report.best_candidate is None


def test_protection_ensures_config_file_never_modified_automatically():
    """
    PROTECTION TEST:
    Verifies that running strategy evaluation and optimization NEVER modifies
    the production config/config.yaml file on disk.
    """
    config_path = "config/config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        before_content = f.read()

    optimizer = StrategyOptimizer()
    df = create_mock_historical_data(count=1200, trend="up")
    optimizer.run_controlled_optimization(df)

    with open(config_path, "r", encoding="utf-8") as f:
        after_content = f.read()

    assert before_content == after_content  # Config strictly untouched
