"""
Astraea MT5 Out-of-Sample (OOS) & Walk-Forward Testing Engine.
Evaluates strategy robustness across chronological, non-overlapping or rolling
Out-of-Sample validation windows without strategy parameter optimization or future data leakage.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from trading.backtester import (
    ForexBacktester,
    BacktestConfig,
    BacktestMetrics,
    BacktestTradeLog,
)
from trading.risk_manager import SymbolSpecification

logger = logging.getLogger("AstraeaMT5.WalkForward")


@dataclass
class WalkForwardConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M5"
    initial_balance: float = 10000.0
    spread_points: int = 0
    slippage_points: int = 0
    lookback_bars: int = 400
    pred_len: int = 120
    dev_window_bars: int = 500
    oos_window_bars: int = 200
    step_bars: int = 200
    window_type: str = "rolling"  # "rolling" or "expanding"


@dataclass
class WalkForwardWindowResult:
    window_index: int
    dev_start_time: str
    dev_end_time: str
    oos_start_time: str
    oos_end_time: str
    metrics: BacktestMetrics
    trade_logs: List[BacktestTradeLog] = field(default_factory=list)


@dataclass
class AggregateOOSMetrics:
    total_windows: int = 0
    profitable_windows: int = 0
    losing_windows: int = 0
    window_win_rate_pct: float = 0.0
    aggregate_net_profit: float = 0.0
    aggregate_net_profit_pct: float = 0.0
    total_oos_trades: int = 0
    total_winning_trades: int = 0
    total_losing_trades: int = 0
    overall_trade_win_rate_pct: float = 0.0
    overall_gross_profit: float = 0.0
    overall_gross_loss: float = 0.0
    overall_profit_factor: float = 0.0
    average_window_pnl: float = 0.0
    max_oos_drawdown: float = 0.0
    max_oos_drawdown_pct: float = 0.0
    best_window_pnl: float = 0.0
    worst_window_pnl: float = 0.0
    consistency_score_pct: float = 0.0


class WalkForwardEngine:
    """
    Evaluates Astraea strategy across chronological walk-forward windows to verify
    out-of-sample consistency without parameter optimization or look-ahead bias.
    """

    def __init__(
        self,
        config: Optional[WalkForwardConfig] = None,
        symbol_spec: Optional[SymbolSpecification] = None,
        backtester: Optional[ForexBacktester] = None,
    ):
        self.config = config or WalkForwardConfig()
        self.symbol_spec = symbol_spec or SymbolSpecification(symbol=self.config.symbol)
        self.backtester = backtester

    def run_walk_forward(
        self, historical_df: pd.DataFrame
    ) -> Tuple[AggregateOOSMetrics, List[WalkForwardWindowResult]]:
        """
        Executes walk-forward testing over historical DataFrame.
        """
        if historical_df is None or len(historical_df) == 0:
            logger.error("Walk-Forward Engine: Historical DataFrame is empty or None.")
            return AggregateOOSMetrics(), []

        df = historical_df.copy()
        if "timestamps" in df.columns:
            df["timestamps"] = pd.to_datetime(df["timestamps"])
            df = df.sort_values("timestamps").reset_index(drop=True)

        total_bars = len(df)
        dev_len = self.config.dev_window_bars
        oos_len = self.config.oos_window_bars
        step_len = self.config.step_bars
        lookback = self.config.lookback_bars

        min_required = dev_len + oos_len
        if total_bars < min_required:
            logger.error(
                f"Insufficient historical bars ({total_bars} < {min_required}) for walk-forward evaluation."
            )
            return AggregateOOSMetrics(), []

        window_results: List[WalkForwardWindowResult] = []
        window_idx = 1
        current_dev_start = 0

        while current_dev_start + dev_len + oos_len <= total_bars:
            if self.config.window_type == "expanding":
                dev_start_idx = 0
            else:  # rolling
                dev_start_idx = current_dev_start

            dev_end_idx = current_dev_start + dev_len
            oos_start_idx = dev_end_idx
            oos_end_idx = oos_start_idx + oos_len

            # Extract Dev & OOS Data Slices
            dev_df = df.iloc[dev_start_idx:dev_end_idx].reset_index(drop=True)
            # OOS slice includes lookback historical context from end of dev set for continuous indicators
            oos_context_start = max(0, oos_start_idx - lookback)
            oos_df = df.iloc[oos_context_start:oos_end_idx].reset_index(drop=True)

            dev_start_time = str(dev_df.iloc[0]["timestamps"]) if "timestamps" in dev_df else "0"
            dev_end_time = str(dev_df.iloc[-1]["timestamps"]) if "timestamps" in dev_df else str(dev_len)
            oos_start_time = str(df.iloc[oos_start_idx]["timestamps"]) if "timestamps" in df else str(oos_start_idx)
            oos_end_time = str(df.iloc[oos_end_idx - 1]["timestamps"]) if "timestamps" in df else str(oos_end_idx)

            # Create Backtest Config for OOS Window
            bt_cfg = BacktestConfig(
                symbol=self.config.symbol,
                timeframe=self.config.timeframe,
                initial_balance=self.config.initial_balance,
                spread_points=self.config.spread_points,
                slippage_points=self.config.slippage_points,
                lookback_bars=lookback,
                pred_len=self.config.pred_len,
            )

            # Instantiate or use provided backtester
            bt = ForexBacktester(config=bt_cfg, symbol_spec=self.symbol_spec)
            oos_metrics, oos_logs = bt.run_backtest(oos_df)

            res = WalkForwardWindowResult(
                window_index=window_idx,
                dev_start_time=dev_start_time,
                dev_end_time=dev_end_time,
                oos_start_time=oos_start_time,
                oos_end_time=oos_end_time,
                metrics=oos_metrics,
                trade_logs=oos_logs,
            )
            window_results.append(res)

            logger.info(
                f"Walk-Forward Window #{window_idx} Completed: OOS Trades={oos_metrics.total_trades}, Net PnL=${oos_metrics.net_profit:+.2f}"
            )

            window_idx += 1
            current_dev_start += step_len

        aggregate_metrics = self.calculate_aggregate_metrics(window_results)
        return aggregate_metrics, window_results

    def calculate_aggregate_metrics(
        self, window_results: List[WalkForwardWindowResult]
    ) -> AggregateOOSMetrics:
        """
        Calculates aggregate Out-of-Sample metrics across all evaluated walk-forward windows.
        """
        total_windows = len(window_results)
        if total_windows == 0:
            return AggregateOOSMetrics()

        profitable_windows = 0
        losing_windows = 0
        all_logs: List[BacktestTradeLog] = []

        window_pnls = []
        for w in window_results:
            pnl = w.metrics.net_profit
            window_pnls.append(pnl)
            if pnl > 0:
                profitable_windows += 1
            elif pnl < 0:
                losing_windows += 1
            all_logs.extend(w.trade_logs)

        window_win_rate = (profitable_windows / total_windows * 100.0) if total_windows > 0 else 0.0
        agg_net_pnl = sum(window_pnls)
        agg_net_pnl_pct = (agg_net_pnl / self.config.initial_balance * 100.0) if self.config.initial_balance > 0 else 0.0

        total_oos_trades = len(all_logs)
        wins = [t.profit_loss for t in all_logs if t.profit_loss > 0]
        losses = [t.profit_loss for t in all_logs if t.profit_loss <= 0]

        tot_wins = len(wins)
        tot_losses = len(losses)
        overall_win_rate = (tot_wins / total_oos_trades * 100.0) if total_oos_trades > 0 else 0.0

        overall_gross_profit = sum(wins)
        overall_gross_loss = abs(sum(losses))
        overall_pf = (
            (overall_gross_profit / overall_gross_loss)
            if overall_gross_loss > 0
            else (overall_gross_profit if overall_gross_profit > 0 else 0.0)
        )

        avg_window_pnl = agg_net_pnl / total_windows if total_windows > 0 else 0.0
        best_pnl = max(window_pnls) if window_pnls else 0.0
        worst_pnl = min(window_pnls) if window_pnls else 0.0

        # Overall OOS Equity Curve & Max Drawdown
        equity_curve = [self.config.initial_balance]
        curr = self.config.initial_balance
        for t in all_logs:
            curr += t.profit_loss
            equity_curve.append(curr)

        peak = equity_curve[0]
        max_dd = 0.0
        max_dd_pct = 0.0

        for eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = peak - eq
            dd_pct = (dd / peak * 100.0) if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        return AggregateOOSMetrics(
            total_windows=total_windows,
            profitable_windows=profitable_windows,
            losing_windows=losing_windows,
            window_win_rate_pct=round(window_win_rate, 2),
            aggregate_net_profit=round(agg_net_pnl, 2),
            aggregate_net_profit_pct=round(agg_net_pnl_pct, 2),
            total_oos_trades=total_oos_trades,
            total_winning_trades=tot_wins,
            total_losing_trades=tot_losses,
            overall_trade_win_rate_pct=round(overall_win_rate, 2),
            overall_gross_profit=round(overall_gross_profit, 2),
            overall_gross_loss=round(overall_gross_loss, 2),
            overall_profit_factor=round(overall_pf, 2),
            average_window_pnl=round(avg_window_pnl, 2),
            max_oos_drawdown=round(max_dd, 2),
            max_oos_drawdown_pct=round(max_dd_pct, 2),
            best_window_pnl=round(best_pnl, 2),
            worst_window_pnl=round(worst_pnl, 2),
            consistency_score_pct=round(window_win_rate, 2),
        )
