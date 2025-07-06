import os
from api.client import BoskoAPI
from dotenv import load_dotenv

load_dotenv()

def main():
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")

    api = BoskoAPI()
    api.login(email, password)

    shops = api.shops.get_all()

    shop = shops[0]
    print(f"Shop ID: {shop.id}")

    products = api.products.get_at_shop(shop.id)
    print(f"Products in {shop.name}:")
    for product in products:
        print(f"- {product.name} (ID: {product.id})")

    query = 'mascarpone'
    results = api.products.search(query=query)
    print(f"Search results for '{query}':")
    for product in results:
        print(f"- {product.name} (ID: {product.id})")

if __name__ == "__main__":
    main()