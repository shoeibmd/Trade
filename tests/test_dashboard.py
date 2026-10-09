import json
import pytest
from webui.app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_dashboard_overview_api_endpoint(client):
    res = client.get('/api/overview')
    assert res.status_code == 200
    data = res.get_json()
    assert 'system_mode' in data
    assert data['system_mode'] == 'PAPER'
    assert 'live_trading_enabled' in data
    assert data['live_trading_enabled'] is False
    assert 'balance' in data
    assert 'equity' in data


def test_dashboard_signals_api_endpoint(client):
    res = client.get('/api/signals')
    assert res.status_code == 200
    data = res.get_json()
    assert 'symbol' in data
    assert data['symbol'] == 'EURUSD'
    assert 'signal' in data
    assert 'signal_score' in data
    assert 'reasons' in data
    assert isinstance(data['reasons'], list)


def test_dashboard_positions_api_endpoint(client):
    res = client.get('/api/positions')
    assert res.status_code == 200
    data = res.get_json()
    assert 'open_positions' in data
    assert isinstance(data['open_positions'], list)


def test_dashboard_history_api_endpoint(client):
    res = client.get('/api/history')
    assert res.status_code == 200
    data = res.get_json()
    assert 'total_trades' in data
    assert 'winning_trades' in data
    assert 'net_pnl' in data
    assert 'trades_history' in data


def test_dashboard_health_api_endpoint(client):
    res = client.get('/api/health')
    assert res.status_code == 200
    data = res.get_json()
    assert 'system_name' in data
    assert data['system_name'] == 'Astraea MT5'
    assert 'live_trading' in data
    assert data['live_trading'] == 'DISABLED'


def test_dashboard_frontend_index_route(client):
    res = client.get('/')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Astraea MT5' in html
    assert 'AI-Powered Forex Trading Intelligence' in html
    assert 'PAPER MODE' in html
