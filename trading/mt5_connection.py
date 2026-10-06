"""
MetaTrader 5 Connection Module for Astraea MT5.
Provides safe connection handling, state tracking, and account/terminal diagnostics.
"""

from enum import Enum
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import yaml

# Safe import of official MetaTrader5 package
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False


logger = logging.getLogger("AstraeaMT5.Connection")


class ConnectionState(Enum):
    NOT_INITIALIZED = "NOT_INITIALIZED"
    INITIALIZED = "INITIALIZED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class MT5Connection:
    """
    Manages connection lifecycle with MetaTrader 5 terminal.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        path: Optional[str] = None,
    ):
        self.state = ConnectionState.NOT_INITIALIZED
        self.last_error: Optional[str] = None
        self.login = login
        self.password = password
        self.server = server
        self.path = path

        # Load environment overrides if present
        self._load_env_credentials()

        # Load config file if specified
        if config_path:
            self._load_config(config_path)

    def _load_env_credentials(self) -> None:
        env_login = os.getenv("MT5_LOGIN")
        if env_login:
            try:
                self.login = int(env_login)
            except ValueError:
                logger.warning(f"Invalid MT5_LOGIN env variable: {env_login}")

        env_password = os.getenv("MT5_PASSWORD")
        if env_password:
            self.password = env_password

        env_server = os.getenv("MT5_SERVER")
        if env_server:
            self.server = env_server

        env_path = os.getenv("MT5_PATH")
        if env_path:
            self.path = env_path

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "mt5" in cfg:
                        mt5_cfg = cfg["mt5"]
                        if not self.path and "path" in mt5_cfg:
                            self.path = mt5_cfg["path"]
            except Exception as e:
                logger.error(f"Error loading config file {config_path}: {e}")

    @property
    def is_installed(self) -> bool:
        """Returns True if the MetaTrader5 Python package is available."""
        return MT5_AVAILABLE

    def initialize(self) -> Tuple[bool, str]:
        """
        Initializes the MT5 terminal API connection.
        """
        if not MT5_AVAILABLE:
            msg = (
                "MetaTrader5 Python package is not installed. "
                "Please install the MetaTrader5 package on a compatible Windows environment before connecting."
            )
            self.state = ConnectionState.ERROR
            self.last_error = msg
            logger.error(msg)
            return False, msg

        init_args = {}
        if self.path:
            init_args["path"] = self.path

        success = mt5.initialize(**init_args)
        if not success:
            err_code, err_msg = mt5.last_error()
            msg = f"Failed to initialize MetaTrader5 terminal. Error [{err_code}]: {err_msg}"
            self.state = ConnectionState.ERROR
            self.last_error = msg
            logger.error(msg)
            return False, msg

        self.state = ConnectionState.INITIALIZED
        logger.info("MetaTrader5 terminal initialized successfully.")
        return True, "MetaTrader5 terminal initialized successfully."

    def connect(self) -> Tuple[bool, str]:
        """
        Connects and logs into the MT5 terminal account if credentials are provided.
        """
        if self.state == ConnectionState.NOT_INITIALIZED or not MT5_AVAILABLE:
            ok, msg = self.initialize()
            if not ok:
                return False, msg

        if self.login and self.password and self.server:
            authorized = mt5.login(
                login=self.login,
                password=self.password,
                server=self.server,
            )
            if not authorized:
                err_code, err_msg = mt5.last_error()
                msg = f"Failed to log in to MT5 account {self.login} on {self.server}. Error [{err_code}]: {err_msg}"
                self.state = ConnectionState.ERROR
                self.last_error = msg
                logger.error(msg)
                return False, msg
            logger.info(f"Successfully logged in to MT5 account {self.login} on server {self.server}.")

        self.state = ConnectionState.CONNECTED
        return True, "Connected to MetaTrader5 terminal."

    def get_terminal_info(self) -> Optional[Dict[str, Any]]:
        """Retrieves terminal build and configuration information."""
        if not MT5_AVAILABLE or self.state not in (ConnectionState.INITIALIZED, ConnectionState.CONNECTED):
            return None

        info = mt5.terminal_info()
        if info is None:
            return None
        return info._asdict()

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Retrieves active account leverage, balance, equity, and margin information."""
        if not MT5_AVAILABLE or self.state != ConnectionState.CONNECTED:
            return None

        info = mt5.account_info()
        if info is None:
            return None
        return info._asdict()

    def get_server_info(self) -> Optional[Dict[str, Any]]:
        """Retrieves connected trade server details."""
        terminal_info = self.get_terminal_info()
        if not terminal_info:
            return None
        return {
            "name": terminal_info.get("name"),
            "company": terminal_info.get("company"),
            "connected": terminal_info.get("connected"),
            "ping_last": terminal_info.get("ping_last"),
        }

    def check_symbol(self, symbol: str) -> bool:
        """Checks if a Forex symbol is available in the market watch."""
        if not MT5_AVAILABLE or self.state not in (ConnectionState.INITIALIZED, ConnectionState.CONNECTED):
            return False

        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            logger.warning(f"Symbol {symbol} not found in MT5 terminal.")
            return False

        if not sym_info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.warning(f"Failed to enable symbol {symbol} in Market Watch.")
                return False

        return True

    def shutdown(self) -> bool:
        """Disconnects and shuts down the MT5 terminal interface."""
        if MT5_AVAILABLE and self.state != ConnectionState.DISCONNECTED:
            mt5.shutdown()

        self.state = ConnectionState.DISCONNECTED
        logger.info("MetaTrader5 connection shut down.")
        return True
