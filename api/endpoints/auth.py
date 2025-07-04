from api.base_endpoint import BaseEndpoint
from api.utils import check_response


class Auth(BaseEndpoint):
    def get_session_token(self, email: str, password: str, is_mobile: bool = True) -> str:
        """
        Authenticate a user and retrieve a session token.

        Args:
            email (str):
            password (str):
            is_mobile (bool): Whether the request is from a mobile device. Defaults to True.
        Returns:
            str: The session token if login is successful.
        """
        endpoint = "/JSON/Authorization/login"
        params = {
            "email": email,
            "password": password,
            "isMobile": is_mobile,
        }

        response = self._post(endpoint, params=params, auth=False)

        check_response(response)

        data = response.json().get("data", None)

        if not data:
            raise ValueError("Login failed, no data returned.")

        return data