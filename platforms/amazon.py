import os
import json
import datetime
import hashlib
import hmac
import requests

from core.models import AdContent, PostResult
from platforms.base import BaseDistributor


class AmazonDistributor(BaseDistributor):
    """Distribute content via Amazon Selling Partner API.

    This creates/updates product listings on Amazon from Shopify products.
    """

    platform_name = "amazon"
    BASE_URL = "https://sellingpartnerapi-na.amazon.com"

    def authenticate(self, credentials: dict) -> None:
        self.client_id = credentials.get("client_id") or os.getenv("AMAZON_CLIENT_ID")
        self.client_secret = credentials.get("client_secret") or os.getenv("AMAZON_CLIENT_SECRET")
        self.refresh_token = credentials.get("refresh_token") or os.getenv("AMAZON_REFRESH_TOKEN")
        self.marketplace_id = credentials.get("marketplace_id") or os.getenv("AMAZON_MARKETPLACE_ID", "ATVPDKIKX0DER")

        if self.refresh_token:
            self._get_access_token()

    def _get_access_token(self):
        resp = requests.post(
            "https://api.amazon.com/auth/o2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
        )
        resp.raise_for_status()
        tokens = resp.json()
        self.access_token = tokens["access_token"]
        self.session.headers["x-amz-access-token"] = self.access_token

    def authorize(self) -> dict:
        print("\nAmazon SP-API uses Login with Amazon (LWA).")
        print("Set AMAZON_REFRESH_TOKEN in your .env file.")
        print("Get it from Amazon Seller Central > Apps & Services > Develop Apps")
        return {}

    def post(self, content: AdContent) -> PostResult:
        try:
            if not self.refresh_token:
                return self._failure(
                    "Amazon requires AMAZON_REFRESH_TOKEN in .env. "
                    "Get it from Amazon Seller Central."
                )

            self._get_access_token()

            # Create a product listing feed
            feed_data = {
                "feedType": "JSON_LISTINGS_FEED",
                "marketplaceIds": [self.marketplace_id],
            }

            # Create feed document
            doc_resp = self.session.post(
                f"{self.BASE_URL}/feeds/2021-06-30/documents",
                json={"contentType": "application/json"},
            )
            doc_resp.raise_for_status()
            doc = doc_resp.json()

            # Upload listing data
            listing = {
                "header": {
                    "sellerId": "SELLER_ID",
                    "version": "2.0",
                },
                "messages": [
                    {
                        "messageId": 1,
                        "sku": content.title.replace(" ", "-").lower()[:40],
                        "operationType": "UPDATE",
                        "productType": "PRODUCT",
                        "attributes": {
                            "item_name": [
                                {"value": content.title, "marketplace_id": self.marketplace_id}
                            ],
                            "product_description": [
                                {"value": content.description[:2000], "marketplace_id": self.marketplace_id}
                            ],
                        },
                    }
                ],
            }

            upload_resp = requests.put(
                doc["url"],
                data=json.dumps(listing),
                headers={"Content-Type": "application/json"},
            )
            upload_resp.raise_for_status()

            # Create feed
            feed_resp = self.session.post(
                f"{self.BASE_URL}/feeds/2021-06-30/feeds",
                json={
                    "feedType": "JSON_LISTINGS_FEED",
                    "marketplaceIds": [self.marketplace_id],
                    "inputFeedDocumentId": doc["feedDocumentId"],
                },
            )
            feed_resp.raise_for_status()
            feed_id = feed_resp.json().get("feedId")

            return self._success(
                post_id=feed_id,
                post_url=f"https://sellercentral.amazon.com/feeds/{feed_id}",
            )

        except Exception as e:
            return self._failure(str(e))

    def validate_content(self, content: AdContent) -> list[str]:
        warnings = []
        if len(content.title) > 200:
            warnings.append(f"Title too long for Amazon ({len(content.title)}/200)")
        if len(content.description) > 2000:
            warnings.append(f"Description too long ({len(content.description)}/2000)")
        return warnings
