"""
MetaTrader 5 Connection Module for Astraea MT5.
Provides safe connection handling, state tracking, account/terminal diagnostics,
and dual-mode execution (Native MT5 API on Windows, Authenticated Gateway Client on Linux/Docker).
"""

from enum import Enum
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

# Attempt import of official MetaTrader5 package
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False


logger = logging.getLogger("AstraeaMT5.Connection")


class ConnectionState(Enum):
    NOT_INITIALIZED = "NOT_INITIALIZED"
    INITIALIZED = "INITIALIZED"
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class MT5ConnectionMode(Enum):
    NATIVE = "NATIVE"      # Direct MT5 Python library (Windows)
    GATEWAY = "GATEWAY"    # REST/gRPC Gateway Client (Linux/Docker)


class MT5GatewayClient:
    """
    Client for communicating with a remote Windows-hosted MT5 REST Gateway securely.
    Requires token authentication (X-MT5-API-Key), configurable timeouts, and retries with backoff.
    """

    def __init__(
        self,
        gateway_url: str,
        api_key: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        self.gateway_url = gateway_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.session = requests.Session() if REQUESTS_AVAILABLE else None

    def _headers(self) -> Dict[str, str]:
        return {
            "X-MT5-API-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "AstraeaMT5-GatewayClient/1.0",
        }

    def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, json_data: Optional[Dict] = None) -> Tuple[bool, Any]:
        if not REQUESTS_AVAILABLE or not self.session:
            return False, "Python 'requests' library is not available."

        url = f"{self.gateway_url}/{endpoint.lstrip('/')}"
        headers = self._headers()

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                )
                if response.status_code == 200:
                    data = response.json()
                    return True, data
                elif response.status_code == 401:
                    return False, "Unauthorized: Invalid X-MT5-API-Key."
                elif response.status_code == 403:
                    return False, "Forbidden: IP address or permission restricted by MT5 Gateway."
                else:
                    err_msg = f"HTTP Error {response.status_code}: {response.text}"
                    if attempt == self.max_retries:
                        return False, err_msg

            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries:
                    return False, f"Gateway connection error: {str(e)}"
                time.sleep(self.backoff_factor * (2 ** (attempt - 1)))

        return False, "Max retries exceeded."

    def ping(self) -> Tuple[bool, str]:
        ok, data = self._request("GET", "/api/v1/ping")
        if ok and isinstance(data, dict) and data.get("status") == "ok":
            return True, "Gateway ping successful."
        return False, f"Gateway ping failed: {data}"

    def get_terminal_info(self) -> Optional[Dict[str, Any]]:
        ok, data = self._request("GET", "/api/v1/terminal_info")
        if ok and isinstance(data, dict):
            return data.get("terminal_info")
        return None

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        ok, data = self._request("GET", "/api/v1/account_info")
        if ok and isinstance(data, dict):
            return data.get("account_info")
        return None

    def check_symbol(self, symbol: str) -> bool:
        ok, data = self._request("GET", f"/api/v1/symbol_info/{symbol}")
        if ok and isinstance(data, dict) and data.get("visible", False):
            return True
        return False

    def copy_rates_range(self, symbol: str, timeframe: str, start_ts: int, end_ts: int) -> Optional[List[Dict]]:
        ok, data = self._request(
            "GET",
            "/api/v1/rates",
            params={"symbol": symbol, "timeframe": timeframe, "start": start_ts, "end": end_ts},
        )
        if ok and isinstance(data, dict) and "rates" in data:
            return data["rates"]
        return None


class MT5Connection:
    """
    Manages connection lifecycle with MetaTrader 5 terminal across Native (Windows) and Gateway (Linux/Docker) modes.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        login: Optional[int] = None,
        password: Optional[str] = None,
        server: Optional[str] = None,
        path: Optional[str] = None,
        mode: Optional[str] = None,
        gateway_url: Optional[str] = None,
        gateway_api_key: Optional[str] = None,
    ):
        self.state = ConnectionState.NOT_INITIALIZED
        self.last_error: Optional[str] = None
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self.gateway_url = gateway_url
        self.gateway_api_key = gateway_api_key

        # Mode auto-detection: Windows default NATIVE, Non-Windows default GATEWAY
        if mode:
            self.mode = MT5ConnectionMode(mode.upper())
        else:
            self.mode = MT5ConnectionMode.NATIVE if sys.platform.startswith("win") and MT5_AVAILABLE else MT5ConnectionMode.GATEWAY

        self.gateway_client: Optional[MT5GatewayClient] = None

        # Load environment overrides
        self._load_env_credentials()

        # Load config file if specified
        if config_path:
            self._load_config(config_path)

        # Instantiate gateway client if in GATEWAY mode and credentials present
        if self.mode == MT5ConnectionMode.GATEWAY and self.gateway_url and self.gateway_api_key:
            self.gateway_client = MT5GatewayClient(
                gateway_url=self.gateway_url,
                api_key=self.gateway_api_key,
            )

    def _load_env_credentials(self) -> None:
        env_mode = os.getenv("MT5_MODE")
        if env_mode:
            try:
                self.mode = MT5ConnectionMode(env_mode.upper())
            except ValueError:
                logger.warning(f"Invalid MT5_MODE env variable: {env_mode}")

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

        env_gw_url = os.getenv("MT5_GATEWAY_URL")
        if env_gw_url:
            self.gateway_url = env_gw_url

        env_gw_key = os.getenv("MT5_GATEWAY_API_KEY")
        if env_gw_key:
            self.gateway_api_key = env_gw_key

    def _load_config(self, config_path: str) -> None:
        p = Path(config_path)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and "mt5" in cfg:
                        mt5_cfg = cfg["mt5"]
                        if "mode" in mt5_cfg and not os.getenv("MT5_MODE"):
                            self.mode = MT5ConnectionMode(mt5_cfg["mode"].upper())
                        if not self.path and "path" in mt5_cfg:
                            self.path = mt5_cfg["path"]
                        if not self.gateway_url and "gateway_url" in mt5_cfg:
                            self.gateway_url = mt5_cfg["gateway_url"]
                        if not self.gateway_api_key and "gateway_api_key" in mt5_cfg:
                            self.gateway_api_key = mt5_cfg["gateway_api_key"]
            except Exception as e:
                logger.error(f"Error loading config file {config_path}: {e}")

    @property
    def is_installed(self) -> bool:
        """Returns True if Native MT5 or Gateway Client prerequisites are met."""
        if self.mode == MT5ConnectionMode.NATIVE:
            return MT5_AVAILABLE
        else:
            return REQUESTS_AVAILABLE

    def initialize(self) -> Tuple[bool, str]:
        """Initializes connection according to configured mode (NATIVE or GATEWAY)."""
        if self.mode == MT5ConnectionMode.NATIVE:
            if not MT5_AVAILABLE:
                msg = (
                    "MetaTrader5 Python package is not installed natively on this system. "
                    "Use MT5ConnectionMode.GATEWAY or run on a compatible Windows environment."
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
                msg = f"Failed to initialize native MetaTrader5 terminal. Error [{err_code}]: {err_msg}"
                self.state = ConnectionState.ERROR
                self.last_error = msg
                logger.error(msg)
                return False, msg

            self.state = ConnectionState.INITIALIZED
            logger.info("Native MetaTrader5 terminal initialized successfully.")
            return True, "Native MetaTrader5 terminal initialized successfully."

        else:
            # GATEWAY Mode
            if not REQUESTS_AVAILABLE:
                msg = "Python 'requests' package is required for MT5GatewayClient in GATEWAY mode."
                self.state = ConnectionState.ERROR
                self.last_error = msg
                return False, msg

            if not self.gateway_url or not self.gateway_api_key:
                msg = "MT5 Gateway URL and API key are required for GATEWAY connection mode."
                self.state = ConnectionState.ERROR
                self.last_error = msg
                return False, msg

            if not self.gateway_client:
                self.gateway_client = MT5GatewayClient(
                    gateway_url=self.gateway_url,
                    api_key=self.gateway_api_key,
                )

            ok, ping_msg = self.gateway_client.ping()
            if not ok:
                msg = f"Failed to connect to MT5 Gateway at {self.gateway_url}: {ping_msg}"
                self.state = ConnectionState.ERROR
                self.last_error = msg
                logger.error(msg)
                return False, msg

            self.state = ConnectionState.INITIALIZED
            logger.info(f"MT5 Gateway Client initialized successfully at {self.gateway_url}.")
            return True, f"MT5 Gateway Client initialized successfully at {self.gateway_url}."

    def connect(self) -> Tuple[bool, str]:
        """Connects and authorizes MT5 account or gateway session."""
        if self.state == ConnectionState.NOT_INITIALIZED:
            ok, msg = self.initialize()
            if not ok:
                return False, msg

        if self.mode == MT5ConnectionMode.NATIVE:
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
                logger.info(f"Successfully logged in to native MT5 account {self.login} on server {self.server}.")

        self.state = ConnectionState.CONNECTED
        return True, f"Connected to MT5 ({self.mode.value} mode)."

    def get_terminal_info(self) -> Optional[Dict[str, Any]]:
        """Retrieves terminal build and configuration information."""
        if self.state not in (ConnectionState.INITIALIZED, ConnectionState.CONNECTED):
            return None

        if self.mode == MT5ConnectionMode.NATIVE and MT5_AVAILABLE:
            info = mt5.terminal_info()
            return info._asdict() if info else None
        elif self.mode == MT5ConnectionMode.GATEWAY and self.gateway_client:
            return self.gateway_client.get_terminal_info()

        return None

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Retrieves active account leverage, balance, equity, and margin information."""
        if self.state != ConnectionState.CONNECTED:
            return None

        if self.mode == MT5ConnectionMode.NATIVE and MT5_AVAILABLE:
            info = mt5.account_info()
            return info._asdict() if info else None
        elif self.mode == MT5ConnectionMode.GATEWAY and self.gateway_client:
            return self.gateway_client.get_account_info()

        return None

    def check_symbol(self, symbol: str) -> bool:
        """Checks if a Forex symbol is available in market watch."""
        if self.state not in (ConnectionState.INITIALIZED, ConnectionState.CONNECTED):
            return False

        if self.mode == MT5ConnectionMode.NATIVE and MT5_AVAILABLE:
            sym_info = mt5.symbol_info(symbol)
            if sym_info is None:
                return False
            if not sym_info.visible:
                if not mt5.symbol_select(symbol, True):
                    return False
            return True

        elif self.mode == MT5ConnectionMode.GATEWAY and self.gateway_client:
            return self.gateway_client.check_symbol(symbol)

        return False

    def shutdown(self) -> bool:
        """Disconnects and shuts down MT5 session."""
        if self.mode == MT5ConnectionMode.NATIVE and MT5_AVAILABLE and self.state != ConnectionState.DISCONNECTED:
            mt5.shutdown()

        self.state = ConnectionState.DISCONNECTED
        logger.info(f"MetaTrader5 connection ({self.mode.value} mode) shut down.")
        return True
