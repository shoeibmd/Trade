"""
Astraea MT5 Forex Backtesting Engine.
Reuses existing Astraea pipeline components (Market Data Validation, Kronos Forecast Adapter,
Technical Indicators, Signal Engine, Risk Manager, and Paper Execution P&L math)
to evaluate historical performance with zero look-ahead bias and deterministic reproducibility.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import yaml

from trading.models import SignalType, PredictionResult
from trading.mt5_data import MT5DataEngine, ValidationResult
from trading.kronos_adapter import KronosAdapter
from trading.indicators import TechnicalIndicatorEngine
from trading.signal_engine import SignalEngine, SignalResult
from trading.risk_manager import RiskManager, RiskDecision, AccountState, SymbolSpecification
from trading.paper_execution import PaperExecutionEngine, PaperPosition, PaperTradeRecord, PaperAccountState

logger = logging.getLogger("AstraeaMT5.Backtester")


@dataclass
class BacktestConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M5"
    initial_balance: float = 10000.0
    spread_points: int = 0
    slippage_points: int = 0
    lookback_bars: int = 400
    pred_len: int = 120
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class BacktestTradeLog:
    trade_id: str
    symbol: str
    timeframe: str
    direction: str
    signal_timestamp: str
    entry_timestamp: str
    entry_price: float
    exit_timestamp: str
    exit_price: float
    lot_size: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    risk_percent: float
    profit_loss: float
    exit_reason: str
    signal_score: float
    signal_reasons: str
    duration_seconds: float
    balance_after_trade: float


@dataclass
class BacktestMetrics:
    initial_balance: float = 10000.0
    final_balance: float = 10000.0
    net_profit: float = 0.0
    net_profit_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_pct: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    average_trade_pnl: float = 0.0
    average_win_pnl: float = 0.0
    average_loss_pnl: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_consecutive_losses: int = 0


class ForexBacktester:
    """
    Historical Forex Backtesting Engine for Astraea MT5.
    Reuses existing Astraea trading architecture without duplicating model or business logic.
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        data_engine: Optional[MT5DataEngine] = None,
        kronos_adapter: Optional[KronosAdapter] = None,
        indicator_engine: Optional[TechnicalIndicatorEngine] = None,
        signal_engine: Optional[SignalEngine] = None,
        risk_manager: Optional[RiskManager] = None,
        symbol_spec: Optional[SymbolSpecification] = None,
    ):
        self.config = config or BacktestConfig()
        self.data_engine = data_engine or MT5DataEngine()
        self.kronos_adapter = kronos_adapter or KronosAdapter()
        self.indicator_engine = indicator_engine or TechnicalIndicatorEngine()
        self.signal_engine = signal_engine or SignalEngine()
        self.risk_manager = risk_manager or RiskManager()
        self.symbol_spec = symbol_spec or SymbolSpecification(symbol=self.config.symbol)

        self.account_state = PaperAccountState(
            initial_balance=self.config.initial_balance,
            balance=self.config.initial_balance,
            equity=self.config.initial_balance,
            start_of_day_equity=self.config.initial_balance,
        )
        self.trade_logs: List[BacktestTradeLog] = []

    def run_backtest(self, historical_df: pd.DataFrame) -> Tuple[BacktestMetrics, List[BacktestTradeLog]]:
        """
        Executes event-driven backtest over historical OHLC DataFrame with ZERO look-ahead bias.
        """
        # Reset Backtester State
        self.account_state = PaperAccountState(
            initial_balance=self.config.initial_balance,
            balance=self.config.initial_balance,
            equity=self.config.initial_balance,
            start_of_day_equity=self.config.initial_balance,
        )
        self.trade_logs = []

        # Validate Historical Data
        val_res = self.data_engine.validate_data(historical_df, min_candles=self.config.lookback_bars + 1)
        if not val_res.is_valid:
            logger.error(f"Backtest Data Validation Failed: {val_res.errors}")
            return self.calculate_metrics(), self.trade_logs

        df = historical_df.copy()
        if "timestamps" in df.columns:
            df["timestamps"] = pd.to_datetime(df["timestamps"])
            df = df.sort_values("timestamps").reset_index(drop=True)

        # Date range filtering if configured
        if self.config.start_date:
            df = df[df["timestamps"] >= self.config.start_date].reset_index(drop=True)
        if self.config.end_date:
            df = df[df["timestamps"] <= self.config.end_date].reset_index(drop=True)

        total_bars = len(df)
        lookback = self.config.lookback_bars

        if total_bars < lookback + 1:
            logger.error(f"Insufficient bars for backtesting after filtering ({total_bars} < {lookback + 1}).")
            return self.calculate_metrics(), self.trade_logs

        i = lookback
        while i < total_bars:
            current_bar = df.iloc[i]
            bar_time = current_bar["timestamps"] if "timestamps" in current_bar else datetime.now()

            # Day rollover check for daily loss calculation
            if i > lookback:
                prev_bar_time = df.iloc[i - 1]["timestamps"] if "timestamps" in df.iloc[i - 1] else None
                if prev_bar_time and bar_time.date() != prev_bar_time.date():
                    self.account_state.start_of_day_equity = self.account_state.equity
                    self.account_state.daily_pnl = 0.0

            # 1. Manage existing open position against current bar (SL/TP)
            if self.account_state.open_position is not None:
                single_bar_df = df.iloc[[i]]
                paper_engine = PaperExecutionEngine(
                    db_path=None,
                    initial_balance=self.config.initial_balance,
                    spread_points=self.config.spread_points,
                    slippage_points=self.config.slippage_points,
                )
                paper_engine.account_state = self.account_state

                closed_rec = paper_engine.process_subsequent_bars(single_bar_df, self.symbol_spec)
                if closed_rec is not None:
                    # Convert PaperTradeRecord to BacktestTradeLog
                    log_entry = BacktestTradeLog(
                        trade_id=closed_rec.trade_id,
                        symbol=closed_rec.symbol,
                        timeframe=closed_rec.timeframe,
                        direction=closed_rec.direction,
                        signal_timestamp=closed_rec.entry_timestamp,
                        entry_timestamp=closed_rec.entry_timestamp,
                        entry_price=closed_rec.entry_price,
                        exit_timestamp=closed_rec.exit_timestamp,
                        exit_price=closed_rec.exit_price,
                        lot_size=closed_rec.lot_size,
                        stop_loss=closed_rec.stop_loss,
                        take_profit=closed_rec.take_profit,
                        risk_amount=closed_rec.risk_amount,
                        risk_percent=closed_rec.risk_percent,
                        profit_loss=closed_rec.profit_loss,
                        exit_reason=closed_rec.exit_reason,
                        signal_score=closed_rec.signal_score,
                        signal_reasons=closed_rec.signal_reasons,
                        duration_seconds=closed_rec.duration_seconds,
                        balance_after_trade=self.account_state.balance,
                    )
                    self.trade_logs.append(log_entry)

            # 2. Evaluate new trade entry if no position is open
            if self.account_state.open_position is None:
                # Slice historical context strictly up to bar index i (CLOSED bars only, ZERO future data)
                window_df = df.iloc[i - lookback + 1 : i + 1].copy().reset_index(drop=True)

                # Compute Indicators
                ind_df = self.indicator_engine.calculate_all_indicators(window_df)

                # Compute Kronos Forecast using KronosAdapter.predict_forecast
                try:
                    forecast_res, err_msg = self.kronos_adapter.predict_forecast(
                        window_df,
                        symbol=self.config.symbol,
                        timeframe=self.config.timeframe,
                    )
                    forecast = forecast_res
                except Exception as e:
                    logger.error(f"Kronos prediction failed at bar index {i}: {e}")
                    forecast = None

                # Evaluate Signal Engine
                signal_res = self.signal_engine.evaluate_signal(
                    ind_df,
                    forecast=forecast,
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                )

                # Evaluate Risk Manager
                risk_acc = AccountState(
                    equity=self.account_state.equity,
                    balance=self.account_state.balance,
                    start_of_day_equity=self.account_state.start_of_day_equity,
                    open_positions_count=0,
                    realized_daily_pnl=self.account_state.daily_pnl,
                    unrealized_daily_pnl=0.0,
                    consecutive_losses=self.account_state.consecutive_losses,
                )
                risk_dec = self.risk_manager.evaluate_risk(
                    signal_res,
                    risk_acc,
                    self.symbol_spec,
                    indicator_df=ind_df,
                )

                # Execute Paper Order if Risk Approved
                if risk_dec.approved:
                    paper_engine = PaperExecutionEngine(
                        db_path=None,
                        initial_balance=self.config.initial_balance,
                        spread_points=self.config.spread_points,
                        slippage_points=self.config.slippage_points,
                    )
                    paper_engine.account_state = self.account_state
                    paper_engine.execute_risk_decision(risk_dec, signal_res, self.symbol_spec)

            i += 1

        return self.calculate_metrics(), self.trade_logs

    def calculate_metrics(self) -> BacktestMetrics:
        """
        Computes summary statistics from backtest trade logs.
        """
        init_bal = self.config.initial_balance
        final_bal = self.account_state.balance
        net_profit = final_bal - init_bal
        net_profit_pct = (net_profit / init_bal * 100.0) if init_bal > 0 else 0.0

        total_trades = len(self.trade_logs)
        if total_trades == 0:
            return BacktestMetrics(
                initial_balance=init_bal,
                final_balance=final_bal,
                net_profit=net_profit,
                net_profit_pct=net_profit_pct,
            )

        pnls = [t.profit_loss for t in self.trade_logs]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        avg_trade = net_profit / total_trades
        avg_win = (gross_profit / winning_trades) if winning_trades > 0 else 0.0
        avg_loss = (-gross_loss / losing_trades) if losing_trades > 0 else 0.0

        # Maximum Drawdown calculation
        equity_curve = [init_bal]
        curr = init_bal
        for p in pnls:
            curr += p
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

        # Maximum consecutive losses
        max_cons_losses = 0
        curr_cons = 0
        for p in pnls:
            if p <= 0:
                curr_cons += 1
                if curr_cons > max_cons_losses:
                    max_cons_losses = curr_cons
            else:
                curr_cons = 0

        return BacktestMetrics(
            initial_balance=init_bal,
            final_balance=round(final_bal, 2),
            net_profit=round(net_profit, 2),
            net_profit_pct=round(net_profit_pct, 2),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=round(win_rate, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            profit_factor=round(profit_factor, 2),
            average_trade_pnl=round(avg_trade, 2),
            average_win_pnl=round(avg_win, 2),
            average_loss_pnl=round(avg_loss, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            max_consecutive_losses=max_cons_losses,
        )
