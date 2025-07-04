from api.auth import QueryParamAuth
from api.base_client import BaseClient
from api.endpoints import Shops, Products, Auth

AUTH_PARAM_NAME = "sessionId"

class BoskoAPI(BaseClient):
    shops: Shops
    products: Products
    _auth: Auth

    def __init__(self, token: str | None = None, base_url: str | None = None):
        self._base_url = base_url or "https://bosko.getloyalty.me"
        self._token = token

        super().__init__(self._base_url, auth_strategy=QueryParamAuth(self._token, param_name=AUTH_PARAM_NAME))

        self.shops = Shops(self)
        self.products = Products(self)
        self._auth = Auth(self)

    def set_token(self, token: str):
        """
        Set the session token for the API client.
        """
        self._token = token
        self._auth_strategy = QueryParamAuth(self._token, param_name=AUTH_PARAM_NAME)

    def login(self, email: str, password: str):
        """
        Authenticate a user and set a session token.

        Args:
            email (str):
            password (str):
        """
        self.set_token(self._auth.get_session_token(email, password))