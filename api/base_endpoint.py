from api.base_client import BaseClient


class BaseEndpoint:
    _client: BaseClient
    """
    A base class for interacting with API endpoints.
    """

    def __init__(self, client: BaseClient):
        self._client = client

        self._get = client.get
        self._post = client.post
