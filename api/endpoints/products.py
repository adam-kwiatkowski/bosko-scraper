from typing import List

from api.base_endpoint import BaseEndpoint
from api.models.product import Product, BaseProduct
from api.utils import check_response


class Products(BaseEndpoint):
    def get_at_shop(self, shop_id: int, limit: int | None = None, current_page: int | None = None) -> List[
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

    def search(self, query: str | None = None, limit: int | None = None, current_page: int | None = None) -> List[
        BaseProduct]:
        """
        Search for products based on a query.

        Args:
            query (str | None): The search query. If None, returns all products.
            limit (int | None): The maximum number of products to return. If None, returns all products.
            current_page (int | None): The page number to return. If None, returns the first page.
        Returns:
            List[BaseProduct]: A list of BaseProduct objects matching the search criteria.
        """
        endpoint = "/JSON/Products/search"
        params = {
            "phrase": query,
            "limit": limit,
            "current_page": current_page
        }
        response = self._get(endpoint, params=params)

        check_response(response)

        data = response.json().get("data", [])
        return [BaseProduct(**item) for item in data]

    def mark_as_favourite(self, product_id: int, is_favourite: bool = True) -> None:
        """
        Mark a product as favourite or remove it from favourites.

        Args:
            product_id (int): The ID of the product to mark as favourite.
            is_favourite (bool): Whether to mark the product as favourite. Defaults to True.
        """
        endpoint = "/JSON/Product/markAsFavourite"
        params = {
            "id": product_id,
            "state": is_favourite
        }
        response = self._post(endpoint, params=params)

        check_response(response)