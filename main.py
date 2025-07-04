import os
from api.client import BoskoAPI
from dotenv import load_dotenv

load_dotenv()


def main():
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")

    api = BoskoAPI()
    api.login(email, password)

    shops = api.shops.get_shops()

    shop = shops[0]
    print(f"Shop ID: {shop.id}")

    products = api.products.get_products(shop.id)
    print(f"Products in {shop.name}:")
    for product in products:
        print(f"- {product.name} (ID: {product.id})")

if __name__ == "__main__":
    main()