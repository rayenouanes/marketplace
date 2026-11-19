#La classe MarketplaceAPIHook, qui appelle l’API
from datetime import date

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from airflow.sdk import BaseHook


class MarketplaceAPIHook(BaseHook):
    """Client de l'API Marketplace utilisant une Connection Airflow."""

    def __init__(
        self,
        conn_id="marketplace_api",
        timeout=30,
        retries=3,
    ):
        super().__init__()
        self.conn_id = conn_id
        self.timeout = timeout
        self.retries = retries

    def get_conn(self):
        connection = self.get_connection(self.conn_id)

        base_url = (connection.host or "").rstrip("/")
        token = connection.password

        if not base_url.startswith(("http://", "https://")):
            raise ValueError(
                "Le host de marketplace_api doit contenir "
                "une URL complète : http://service:port"
            )

        if not token:
            raise ValueError(
                "Le token API est absent du champ Password "
                "de la Connection marketplace_api."
            )

        retry_policy = Retry(
            total=self.retries,
            connect=self.retries,
            read=self.retries,
            status=self.retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            respect_retry_after_header=True,
            raise_on_status=False,
        )

        session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_policy)

        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

        return base_url, session

    def _get(self, endpoint, params=None):
        base_url, session = self.get_conn()

        with session:
            response = session.get(
                f"{base_url}/{endpoint.lstrip('/')}",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()

    def get_orders(self, requested_date):
        date.fromisoformat(requested_date)

        return self._get(
            "/orders",
            params={"date": requested_date},
        )

    def get_sellers(self):
        return self._get("/sellers")

    def get_products(self):
        return self._get("/products")