"""
Astraea MT5 Strategy Evaluation & Controlled Optimization Engine.
Provides reproducible baseline strategy performance measurement, parameter sensitivity analysis,
chronological development/validation/untouched-OOS evaluations, and transaction cost analysis
without parameter overfitting, model retraining, or automatic config overwriting.
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
from trading.walk_forward import WalkForwardEngine, WalkForwardConfig
from trading.risk_manager import SymbolSpecification, RiskManager
from trading.signal_engine import SignalEngine

logger = logging.getLogger("AstraeaMT5.StrategyOptimizer")


@dataclass
class EvaluationConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M5"
    initial_balance: float = 10000.0
    spread_points: int = 0
    slippage_points: int = 0
    dev_split_ratio: float = 0.5
    val_split_ratio: float = 0.25
    oos_split_ratio: float = 0.25  # Final untouched OOS period
    lookback_bars: int = 400
    pred_len: int = 120


@dataclass
class OptimizationCandidate:
    candidate_id: str
    params: Dict[str, Any]
    dev_metrics: BacktestMetrics
    val_metrics: Optional[BacktestMetrics] = None
    untouched_oos_metrics: Optional[BacktestMetrics] = None
    score: float = 0.0


@dataclass
class OptimizationReport:
    timestamp: datetime = field(default_factory=datetime.now)
    data_type: str = "SYNTHETIC / MOCK DATA"
    total_bars: int = 0
    dev_bars: int = 0
    val_bars: int = 0
    oos_bars: int = 0
    baseline_metrics: Optional[BacktestMetrics] = None
    best_candidate: Optional[OptimizationCandidate] = None
    all_candidates: List[OptimizationCandidate] = field(default_factory=list)
    cost_sensitivity: Dict[str, Any] = field(default_factory=dict)
    recommendations: Dict[str, Any] = field(default_factory=dict)


class StrategyOptimizer:
    """
    Evaluates baseline strategy performance and performs controlled candidate parameter search
    across chronological development and validation data splits while keeping a final
    untouched OOS dataset. NEVER modifies production config files automatically.
    """

    def __init__(
        self,
        config: Optional[EvaluationConfig] = None,
        symbol_spec: Optional[SymbolSpecification] = None,
    ):
        self.config = config or EvaluationConfig()
        self.symbol_spec = symbol_spec or SymbolSpecification(symbol=self.config.symbol)

    def evaluate_baseline(self, historical_df: pd.DataFrame) -> BacktestMetrics:
        """
        Evaluates the strategy baseline using current default configuration.
        """
        bt_cfg = BacktestConfig(
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            initial_balance=self.config.initial_balance,
            spread_points=self.config.spread_points,
            slippage_points=self.config.slippage_points,
            lookback_bars=self.config.lookback_bars,
            pred_len=self.config.pred_len,
        )
        backtester = ForexBacktester(config=bt_cfg, symbol_spec=self.symbol_spec)
        metrics, _ = backtester.run_backtest(historical_df)
        return metrics

    def run_controlled_optimization(
        self,
        historical_df: pd.DataFrame,
        candidate_param_grid: Optional[List[Dict[str, Any]]] = None,
    ) -> OptimizationReport:
        """
        Executes anti-overfitting strategy evaluation across chronological splits:
        1. Dev Set (50%): Candidate parameter generation / search.
        2. Validation Set (25%): Candidate selection (choosing best candidate).
        3. Untouched OOS Set (25%): Final single evaluation of the chosen best candidate.
        """
        if historical_df is None or len(historical_df) == 0:
            logger.error("StrategyOptimizer: Historical DataFrame is empty or None.")
            return OptimizationReport()

        df = historical_df.copy()
        if "timestamps" in df.columns:
            df["timestamps"] = pd.to_datetime(df["timestamps"])
            df = df.sort_values("timestamps").reset_index(drop=True)

        total_bars = len(df)
        dev_end = int(total_bars * self.config.dev_split_ratio)
        val_end = dev_end + int(total_bars * self.config.val_split_ratio)

        lookback = self.config.lookback_bars

        dev_df = df.iloc[:dev_end].reset_index(drop=True)

        # Include lookback historical context for validation and OOS sets
        val_context_start = max(0, dev_end - lookback)
        val_df = df.iloc[val_context_start:val_end].reset_index(drop=True)

        oos_context_start = max(0, val_end - lookback)
        oos_df = df.iloc[oos_context_start:].reset_index(drop=True)

        dev_bars = len(dev_df)
        val_bars = max(0, val_end - dev_end)
        oos_bars = max(0, total_bars - val_end)

        # Baseline performance on whole dataset
        baseline_metrics = self.evaluate_baseline(df)

        # Default grid if none provided
        if not candidate_param_grid:
            candidate_param_grid = [
                {"minimum_signal_score": 70, "risk_per_trade_percent": 1.0, "reward_risk_ratio": 1.5},
                {"minimum_signal_score": 75, "risk_per_trade_percent": 1.0, "reward_risk_ratio": 1.5},
                {"minimum_signal_score": 70, "risk_per_trade_percent": 0.5, "reward_risk_ratio": 1.5},
                {"minimum_signal_score": 70, "risk_per_trade_percent": 1.0, "reward_risk_ratio": 2.0},
            ]

        candidates_evaluated: List[OptimizationCandidate] = []

        for idx, p in enumerate(candidate_param_grid):
            cid = f"candidate_{idx + 1}"
            min_score = p.get("minimum_signal_score", 70)
            risk_pct = p.get("risk_per_trade_percent", 1.0)
            rr_ratio = p.get("reward_risk_ratio", 1.5)

            # Custom signal & risk engines for candidate
            sig_eng = SignalEngine(minimum_signal_score=min_score)
            risk_mgr = RiskManager(risk_per_trade_percent=risk_pct, reward_risk_ratio=rr_ratio)

            bt_cfg = BacktestConfig(
                symbol=self.config.symbol,
                timeframe=self.config.timeframe,
                initial_balance=self.config.initial_balance,
                spread_points=self.config.spread_points,
                slippage_points=self.config.slippage_points,
                lookback_bars=lookback,
                pred_len=self.config.pred_len,
            )

            # 1. Evaluate Candidate on Development Set
            bt_dev = ForexBacktester(
                config=bt_cfg,
                signal_engine=sig_eng,
                risk_manager=risk_mgr,
                symbol_spec=self.symbol_spec,
            )
            dev_m, _ = bt_dev.run_backtest(dev_df)

            # 2. Evaluate Candidate on Validation Set
            bt_val = ForexBacktester(
                config=bt_cfg,
                signal_engine=sig_eng,
                risk_manager=risk_mgr,
                symbol_spec=self.symbol_spec,
            )
            val_m, _ = bt_val.run_backtest(val_df)

            # Simple scoring function: Net Profit * Profit Factor on Validation set
            val_score = val_m.net_profit * (val_m.profit_factor if val_m.profit_factor > 0 else 1.0)

            cand = OptimizationCandidate(
                candidate_id=cid,
                params=p,
                dev_metrics=dev_m,
                val_metrics=val_m,
                score=val_score,
            )
            candidates_evaluated.append(cand)

        # Select Best Candidate based strictly on Validation Set performance
        best_candidate = max(candidates_evaluated, key=lambda c: c.score) if candidates_evaluated else None

        # 3. Final Single Evaluation of Best Candidate on Untouched OOS Set
        if best_candidate and oos_bars > 0:
            bp = best_candidate.params
            sig_eng_best = SignalEngine(minimum_signal_score=bp.get("minimum_signal_score", 70))
            risk_mgr_best = RiskManager(
                risk_per_trade_percent=bp.get("risk_per_trade_percent", 1.0),
                reward_risk_ratio=bp.get("reward_risk_ratio", 1.5),
            )
            bt_cfg_best = BacktestConfig(
                symbol=self.config.symbol,
                timeframe=self.config.timeframe,
                initial_balance=self.config.initial_balance,
                spread_points=self.config.spread_points,
                slippage_points=self.config.slippage_points,
                lookback_bars=lookback,
                pred_len=self.config.pred_len,
            )
            bt_oos = ForexBacktester(
                config=bt_cfg_best,
                signal_engine=sig_eng_best,
                risk_manager=risk_mgr_best,
                symbol_spec=self.symbol_spec,
            )
            oos_m, _ = bt_oos.run_backtest(oos_df)
            best_candidate.untouched_oos_metrics = oos_m

        # Transaction Cost Sensitivity Analysis
        cost_sensitivity = self.analyze_cost_sensitivity(df)

        return OptimizationReport(
            timestamp=datetime.now(),
            data_type="SYNTHETIC / MOCK DATA",
            total_bars=total_bars,
            dev_bars=dev_bars,
            val_bars=val_bars,
            oos_bars=oos_bars,
            baseline_metrics=baseline_metrics,
            best_candidate=best_candidate,
            all_candidates=candidates_evaluated,
            cost_sensitivity=cost_sensitivity,
            recommendations={
                "status": "RECOMMENDATION ONLY (Config file unchanged)",
                "recommended_params": best_candidate.params if best_candidate else {},
                "note": "Production configuration was NOT automatically modified. Manual review required.",
            },
        )

    def analyze_cost_sensitivity(self, historical_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates baseline strategy sensitivity to transaction costs (spread & slippage points).
        """
        results = {}
        for spread in [0, 10, 20, 30]:  # 0, 1.0, 2.0, 3.0 pips
            bt_cfg = BacktestConfig(
                symbol=self.config.symbol,
                timeframe=self.config.timeframe,
                initial_balance=self.config.initial_balance,
                spread_points=spread,
                slippage_points=0,
                lookback_bars=self.config.lookback_bars,
                pred_len=self.config.pred_len,
            )
            bt = ForexBacktester(config=bt_cfg, symbol_spec=self.symbol_spec)
            m, _ = bt.run_backtest(historical_df)
            results[f"spread_{spread}_points"] = {
                "net_profit": m.net_profit,
                "win_rate_pct": m.win_rate_pct,
                "profit_factor": m.profit_factor,
            }
        return results
