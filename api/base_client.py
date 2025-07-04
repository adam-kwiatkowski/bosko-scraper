import logging
from typing import Optional

import requests

from api.auth import AuthStrategy, NoAuth


class BaseClient:
    def __init__(self, base_url: str, auth_strategy: Optional[AuthStrategy] = None):
        self._base_url = base_url
        self._auth_strategy = auth_strategy or NoAuth()
        self._default_headers = {"Accept": "application/json", }

    @property
    def base_url(self):
        return self._base_url

    def _make_request(self, method: str, path: str, headers: dict | None = None, auth: bool = True, **kwargs):
        """
        Handles HTTP requests.
        """
        url = f"{self._base_url}{path}"

        request_headers = {**self._default_headers, **(headers or {})}

        session = requests.Session()
        req = requests.Request(method, url, headers=request_headers, **kwargs)

        prepared_request = session.prepare_request(req)
        if auth:
            self._auth_strategy.apply(prepared_request)

        logging.debug(f"Making a {method.upper()} request to {prepared_request.url}"
                      f"\n\tHeaders: {prepared_request.headers}"
                      f"\n\tData: {kwargs}")

        response = session.send(prepared_request)

        response.raise_for_status()
        return response

    def get(self, url, params: dict = None, auth: bool = True):
        """
        Makes a GET request.
        """
        return self._make_request("get", url, params=params, auth=auth)

    def post(self, url, params: dict = None, auth: bool = True):
        """
        Makes a POST request.
        """
        return self._make_request("post", url, params=params, auth=auth)
