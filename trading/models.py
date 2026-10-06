"""
Core data models and type definitions for Kronos MT5 Forex Trader.
Provides standard schemas for ticks, candles, predictions, signals, and positions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TradingMode(Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"


@dataclass
class TickData:
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    volume: float = 0.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass
class BarData:
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    amount: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamps": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount,
        }


@dataclass
class PredictionResult:
    symbol: str
    timestamp: datetime
    pred_len: int
    predicted_close: List[float]
    predicted_open: Optional[List[float]] = None
    predicted_high: Optional[List[float]] = None
    predicted_low: Optional[List[float]] = None
    predicted_volume: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradingSignal:
    symbol: str
    timestamp: datetime
    signal_type: SignalType
    score: float
    predicted_change_pct: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    position_id: str
    symbol: str
    signal_type: SignalType
    volume: float
    open_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    open_time: Optional[datetime] = None
    unrealized_pnl: float = 0.0
