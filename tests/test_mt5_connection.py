from unittest.mock import MagicMock, patch
import pytest

from trading.mt5_connection import ConnectionState, MT5Connection


def test_mt5_connection_initial_state():
    conn = MT5Connection()
    assert conn.state == ConnectionState.NOT_INITIALIZED
    assert conn.last_error is None


def test_mt5_connection_env_vars(monkeypatch):
    monkeypatch.setenv("MT5_LOGIN", "12345678")
    monkeypatch.setenv("MT5_PASSWORD", "secret_pass")
    monkeypatch.setenv("MT5_SERVER", "Demo-Server")
    monkeypatch.setenv("MT5_PATH", "C:/Program Files/MetaTrader 5/terminal64.exe")

    conn = MT5Connection()
    assert conn.login == 12345678
    assert conn.password == "secret_pass"
    assert conn.server == "Demo-Server"
    assert conn.path == "C:/Program Files/MetaTrader 5/terminal64.exe"


def test_mt5_connection_missing_package_graceful_handling():
    with patch("trading.mt5_connection.MT5_AVAILABLE", False):
        conn = MT5Connection()
        assert conn.is_installed is False

        ok, msg = conn.initialize()
        assert ok is False
        assert conn.state == ConnectionState.ERROR
        assert "MetaTrader5 Python package is not installed" in msg

        ok_conn, msg_conn = conn.connect()
        assert ok_conn is False
        assert conn.state == ConnectionState.ERROR


def test_mt5_connection_mocked_success():
    mock_mt5 = MagicMock()
    mock_mt5.initialize.return_value = True
    mock_mt5.login.return_value = True

    mock_terminal = MagicMock()
    mock_terminal._asdict.return_value = {
        "name": "MetaTrader 5",
        "company": "MetaQuotes Ltd.",
        "connected": True,
        "ping_last": 12,
    }
    mock_mt5.terminal_info.return_value = mock_terminal

    mock_account = MagicMock()
    mock_account._asdict.return_value = {
        "login": 123456,
        "balance": 10000.0,
        "equity": 10000.0,
        "leverage": 100,
    }
    mock_mt5.account_info.return_value = mock_account

    with patch("trading.mt5_connection.MT5_AVAILABLE", True), patch("trading.mt5_connection.mt5", mock_mt5):
        conn = MT5Connection(login=123456, password="pass", server="demo")

        ok, msg = conn.initialize()
        assert ok is True
        assert conn.state == ConnectionState.INITIALIZED

        ok_conn, msg_conn = conn.connect()
        assert ok_conn is True
        assert conn.state == ConnectionState.CONNECTED

        term_info = conn.get_terminal_info()
        assert term_info["name"] == "MetaTrader 5"

        acc_info = conn.get_account_info()
        assert acc_info["balance"] == 10000.0

        server_info = conn.get_server_info()
        assert server_info["company"] == "MetaQuotes Ltd."

        shutdown_ok = conn.shutdown()
        assert shutdown_ok is True
        assert conn.state == ConnectionState.DISCONNECTED
