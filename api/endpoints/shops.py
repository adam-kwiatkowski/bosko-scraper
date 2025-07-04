from typing import List

from api.base_endpoint import BaseEndpoint
from api.models.shop import Shop
from api.utils import check_response


class Shops(BaseEndpoint):
    def get_all(self, limit: int | None = None, current_page: int | None = None) -> List[Shop]:
        """
        Fetch all stores from the API.

        Args:
            limit (int | None): The maximum number of stores to return. If None, returns all stores.
            current_page (int | None): The page number to return. If None, returns the first page.
        Returns:
            List[Shop]: A list of Shop objects representing the stores.
        """
        endpoint = "/JSON/Shops/getAll"
        params = {
            "limit": limit,
            "currentPage": current_page
        }

        response = self._get(endpoint, params=params)

        check_response(response)

        data = response.json().get("data", [])
        return [Shop(**item) for item in data]