from abc import ABC, abstractmethod
from urllib.parse import urlencode, urlparse, parse_qsl

import requests


class AuthStrategy(ABC):
    @abstractmethod
    def apply(self, request: requests.PreparedRequest) -> None:
        """
        Modify the request in place to add necessary auth (headers, query params, etc).
        """
        pass


class BearerAuth(AuthStrategy):
    def __init__(self, token: str):
        self.token = token

    def apply(self, request: requests.PreparedRequest) -> None:
        request.headers["Authorization"] = f"Bearer {self.token}"


class QueryParamAuth(AuthStrategy):
    def __init__(self, token: str, param_name: str = "token"):
        self.token = token
        self.param_name = param_name

    def apply(self, request: requests.PreparedRequest) -> None:
        parse_result = urlparse(request.url)

        query = dict(parse_qsl(parse_result.query))
        query[self.param_name] = self.token

        request.url = parse_result._replace(query=urlencode(query)).geturl()


class NoAuth(AuthStrategy):
    def apply(self, request: requests.PreparedRequest) -> None:
        pass
