"""
Compatibility alias module for trading.kronos_adapter.
Re-exports KronosAdapter, AstraeaForecastingEngine, and KronosAdapterError from trading.forex_adapter.
"""

from trading.forex_adapter import KronosAdapter, AstraeaForecastingEngine, KronosAdapterError

__all__ = ["KronosAdapter", "AstraeaForecastingEngine", "KronosAdapterError"]
