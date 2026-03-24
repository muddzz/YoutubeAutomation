import os
import re
import requests
from core.models import Product


class ShopifyClient:
    def __init__(self, store: str = None, access_token: str = None):
        self.store = store or os.getenv("SHOPIFY_STORE")
        self.access_token = access_token or os.getenv("SHOPIFY_ACCESS_TOKEN")
        if not self.store or not self.access_token:
            raise ValueError(
                "SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN must be set in .env"
            )
        self.base_url = f"https://{self.store}.myshopify.com/admin/api/2024-01"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-Shopify-Access-Token": self.access_token,
                "Content-Type": "application/json",
            }
        )

    def _get(self, endpoint: str, params: dict = None) -> dict:
        resp = self.session.get(f"{self.base_url}/{endpoint}.json", params=params)
        resp.raise_for_status()
        return resp.json()

    def _parse_product(self, data: dict) -> Product:
        images = [img["src"] for img in data.get("images", [])]
        variants = [
            {
                "title": v.get("title", ""),
                "price": v.get("price", "0.00"),
                "sku": v.get("sku", ""),
                "inventory_quantity": v.get("inventory_quantity", 0),
            }
            for v in data.get("variants", [])
        ]
        tags = [t.strip() for t in data.get("tags", "").split(",") if t.strip()]
        return Product(
            id=str(data["id"]),
            title=data.get("title", ""),
            description=self._strip_html(data.get("body_html", "") or ""),
            price=data["variants"][0]["price"] if data.get("variants") else "0.00",
            currency="USD",
            images=images,
            variants=variants,
            url=f"https://{self.store}.myshopify.com/products/{data.get('handle', '')}",
            tags=tags,
        )

    @staticmethod
    def _strip_html(html: str) -> str:
        clean = re.sub(r"<[^>]+>", "", html)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def get_products(self, limit: int = 50, collection_id: str = None) -> list[Product]:
        params = {"limit": min(limit, 250)}
        if collection_id:
            params["collection_id"] = collection_id

        products = []
        endpoint = "products"
        resp = self.session.get(
            f"{self.base_url}/{endpoint}.json", params=params
        )
        resp.raise_for_status()
        data = resp.json()

        for p in data.get("products", []):
            products.append(self._parse_product(p))

        # Handle pagination
        while len(products) < limit and "link" in resp.headers:
            link = resp.headers["link"]
            next_match = re.search(r'<([^>]+)>;\s*rel="next"', link)
            if not next_match:
                break
            resp = self.session.get(next_match.group(1))
            resp.raise_for_status()
            data = resp.json()
            for p in data.get("products", []):
                products.append(self._parse_product(p))

        return products[:limit]

    def get_product(self, product_id: str) -> Product:
        data = self._get(f"products/{product_id}")
        return self._parse_product(data["product"])

    def download_image(self, url: str, dest_dir: str = "/tmp") -> str:
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        filename = url.split("/")[-1].split("?")[0]
        path = os.path.join(dest_dir, filename)
        with open(path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return path
