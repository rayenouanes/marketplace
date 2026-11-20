#Les tests du Hook avec de fausses réponses HTTP

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from marketplace.api_hook import MarketplaceAPIHook


def test_get_orders_sends_date():
    hook = MarketplaceAPIHook()
    session = MagicMock()

    expected = [{"order_id": 1}]
    session.get.return_value.json.return_value = expected

    with patch.object(
        hook,
        "get_conn",
        return_value=("http://api-test:5000", session),
    ):
        result = hook.get_orders("2026-04-07")

    session.get.assert_called_once_with(
        "http://api-test:5000/orders",
        params={"date": "2026-04-07"},
        timeout=30,
    )

    assert result == expected


def test_get_conn_sets_bearer_header():
    hook = MarketplaceAPIHook()

    fake_connection = SimpleNamespace(
        host="http://api-test:5000",
        password="fake-token-for-test",
    )

    with patch.object(
        hook,
        "get_connection",
        return_value=fake_connection,
    ):
        base_url, session = hook.get_conn()

    try:
        assert base_url == "http://api-test:5000"
        assert session.headers["Authorization"] == (
            "Bearer fake-token-for-test"
        )
        assert session.get_adapter("http://").max_retries.total == 3
    finally:
        session.close()


def test_http_error_is_not_hidden():
    hook = MarketplaceAPIHook()
    session = MagicMock()

    session.get.return_value.raise_for_status.side_effect = (
        requests.HTTPError("401 Unauthorized")
    )

    with patch.object(
        hook,
        "get_conn",
        return_value=("http://api-test:5000", session),
    ):
        with pytest.raises(requests.HTTPError):
            hook.get_products()


def test_invalid_date_is_rejected():
    hook = MarketplaceAPIHook()

    with pytest.raises(ValueError):
        hook.get_orders("date-invalide")