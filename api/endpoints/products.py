from typing import List

from api.base_endpoint import BaseEndpoint
from api.models.product import Product
from api.utils import check_response


class Products(BaseEndpoint):
    def get_products(self, shop_id: int, limit: int | None = None, current_page: int | None = None) -> List[
        Product]:
        """
        Fetch all products available at a specific shop.

        Args:
            shop_id (int): The ID of the shop to fetch products from.
            limit (int | None): The maximum number of products to return. If None, returns all products.
            current_page (int | None): The page number to return. If None, returns the first page.
        Returns:
            List[Product]: A list of Product objects representing the products at the specified shop.
        """
        endpoint = "/JSON/Products/getAll"
        params = {
            "shopId": shop_id,
            "limit": limit,
            "current_page": current_page
        }
        response = self._get(endpoint, params=params)

        check_response(response)

        data = response.json().get("data", [])
        return [Product(**item) for item in data]
