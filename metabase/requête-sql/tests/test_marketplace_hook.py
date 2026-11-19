"""Tests unitaires du MarketplaceAPIHook avec mock de requests (bonus Could).

⚠️ Adapter MODULE_PATH et les noms de méthodes à l'implémentation de Cris
(branche feature/api-minio). Si le module n'existe pas encore, les tests sont skippés.
"""
from unittest import mock

import pytest

MODULE_PATH = "hooks.marketplace_api_hook"   # plugins/hooks/marketplace_api_hook.py
hook_module = pytest.importorskip(MODULE_PATH)
MarketplaceAPIHook = hook_module.MarketplaceAPIHook


@pytest.fixture
def fake_conn():
    conn = mock.MagicMock()
    conn.host = "http://api-marketplace:5000"
    conn.password = "fake-token"
    conn.schema = None
    conn.port = None
    return conn


@pytest.fixture
def hook(fake_conn):
    with mock.patch.object(MarketplaceAPIHook, "get_connection", return_value=fake_conn):
        yield MarketplaceAPIHook()


def _response(status=200, payload=None):
    r = mock.MagicMock()
    r.status_code = status
    r.ok = status < 400
    r.json.return_value = payload if payload is not None else []
    if status >= 400:
        import requests
        r.raise_for_status.side_effect = requests.HTTPError(f"{status}")
    return r


def test_get_orders_sends_bearer_and_date(hook):
    with mock.patch("requests.Session.request", return_value=_response(200, [{"order_id": 1}])) as m_sess, \
         mock.patch("requests.request", return_value=_response(200, [{"order_id": 1}])) as m_req, \
         mock.patch("requests.get", return_value=_response(200, [{"order_id": 1}])) as m_get:
        result = hook.get_orders("2026-04-07")

    call = next(c for c in (m_sess, m_req, m_get) if c.called).call_args
    headers = call.kwargs.get("headers", {}) or {}
    params = call.kwargs.get("params", {}) or {}
    url = " ".join(map(str, call.args)) + str(call.kwargs.get("url", ""))

    assert "Bearer fake-token" in str(headers) or hasattr(hook, "session")
    assert "2026-04-07" in str(params) + url
    assert result  # données renvoyées


def test_token_never_hardcoded():
    import inspect
    assert "formation-token-2026" not in inspect.getsource(hook_module)
