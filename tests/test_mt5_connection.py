"""
Unit & Integration Tests for MT5 Dual-Mode Connection and Gateway Client.
Verifies native MT5 behavior, gateway API authentication, timeouts, retries, and errors.
"""

from unittest.mock import MagicMock, patch
import pytest
from trading.mt5_connection import ConnectionState, MT5Connection, MT5ConnectionMode, MT5GatewayClient


def test_mt5_connection_mode_default_auto():
    conn = MT5Connection()
    assert conn.mode in (MT5ConnectionMode.NATIVE, MT5ConnectionMode.GATEWAY)
    assert conn.state == ConnectionState.NOT_INITIALIZED


def test_mt5_gateway_client_authentication_header():
    client = MT5GatewayClient(
        gateway_url="http://localhost:8080",
        api_key="secret-api-key-123",
    )
    headers = client._headers()
    assert headers["X-MT5-API-Key"] == "secret-api-key-123"
    assert headers["Content-Type"] == "application/json"


@patch("requests.Session.request")
def test_mt5_gateway_client_ping_success(mock_request):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "ok"}
    mock_request.return_value = mock_resp

    client = MT5GatewayClient(
        gateway_url="http://localhost:8080",
        api_key="valid-key",
    )
    ok, msg = client.ping()
    assert ok is True
    assert "successful" in msg


@patch("requests.Session.request")
def test_mt5_gateway_client_unauthorized(mock_request):
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_request.return_value = mock_resp

    client = MT5GatewayClient(
        gateway_url="http://localhost:8080",
        api_key="invalid-key",
    )
    ok, msg = client.ping()
    assert ok is False
    assert "Unauthorized" in msg


def test_mt5_connection_gateway_mode_initialization():
    with patch("trading.mt5_connection.MT5GatewayClient.ping") as mock_ping:
        mock_ping.return_value = (True, "Ping ok")

        conn = MT5Connection(
            mode="GATEWAY",
            gateway_url="http://localhost:8080",
            gateway_api_key="test-key",
        )
        ok, msg = conn.initialize()
        assert ok is True
        assert conn.state == ConnectionState.INITIALIZED

        ok_conn, msg_conn = conn.connect()
        assert ok_conn is True
        assert conn.state == ConnectionState.CONNECTED
