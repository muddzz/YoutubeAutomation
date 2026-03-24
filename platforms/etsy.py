import os
import requests

from core.models import AdContent, PostResult
from platforms.base import BaseDistributor


class EtsyDistributor(BaseDistributor):
    """Distribute content via Etsy Open API v3.

    Creates draft listings on Etsy from Shopify products.
    """

    platform_name = "etsy"
    BASE_URL = "https://openapi.etsy.com/v3/application"

    def authenticate(self, credentials: dict) -> None:
        self.api_key = credentials.get("api_key") or os.getenv("ETSY_API_KEY")
        self.api_secret = credentials.get("api_secret") or os.getenv("ETSY_API_SECRET")
        self.shop_id = credentials.get("shop_id") or os.getenv("ETSY_SHOP_ID")

        tokens = self.oauth.get_tokens("etsy")
        if tokens:
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"
            self.session.headers["x-api-key"] = self.api_key

    def authorize(self) -> dict:
        return self.oauth.authorize(
            platform="etsy",
            client_id=self.api_key,
            client_secret=self.api_secret,
            auth_url="https://www.etsy.com/oauth/connect",
            token_url="https://api.etsy.com/v3/public/oauth/token",
            scopes=["listings_w", "listings_r"],
            use_pkce=True,
        )

    def post(self, content: AdContent) -> PostResult:
        try:
            tokens = self.oauth.get_tokens("etsy")
            if not tokens:
                return self._failure("Not authenticated. Run: python cli.py auth etsy")
            if not self.shop_id:
                return self._failure("ETSY_SHOP_ID not set in .env")

            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"
            self.session.headers["x-api-key"] = self.api_key

            # Create a draft listing
            listing_data = {
                "quantity": 999,
                "title": content.title[:140],
                "description": content.description[:2000],
                "price": 0.00,  # Will need to be updated
                "who_made": "i_did",
                "when_made": "made_to_order",
                "taxonomy_id": 1,
                "tags": [h.lstrip("#")[:20] for h in content.hashtags[:13]],
                "state": "draft",
            }

            resp = self.session.post(
                f"{self.BASE_URL}/shops/{self.shop_id}/listings",
                json=listing_data,
            )

            if resp.status_code == 401:
                self._refresh()
                resp = self.session.post(
                    f"{self.BASE_URL}/shops/{self.shop_id}/listings",
                    json=listing_data,
                )

            resp.raise_for_status()
            data = resp.json()
            listing_id = data.get("listing_id")

            # Upload images
            if content.media_urls and listing_id:
                self._upload_images(listing_id, content.media_urls[:10])

            return self._success(
                post_id=str(listing_id),
                post_url=f"https://www.etsy.com/listing/{listing_id}",
            )

        except Exception as e:
            return self._failure(str(e))

    def _upload_images(self, listing_id: str, image_urls: list[str]):
        for rank, url in enumerate(image_urls, 1):
            try:
                img_resp = requests.get(url)
                img_resp.raise_for_status()

                self.session.post(
                    f"{self.BASE_URL}/shops/{self.shop_id}/listings/{listing_id}/images",
                    files={"image": ("product.jpg", img_resp.content, "image/jpeg")},
                    data={"rank": rank},
                )
            except Exception:
                continue

    def _refresh(self):
        tokens = self.oauth.refresh_token(
            "etsy",
            self.api_key,
            self.api_secret,
            "https://api.etsy.com/v3/public/oauth/token",
        )
        self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def validate_content(self, content: AdContent) -> list[str]:
        warnings = []
        if len(content.title) > 140:
            warnings.append(f"Title too long for Etsy ({len(content.title)}/140)")
        if len(content.description) > 2000:
            warnings.append(f"Description too long ({len(content.description)}/2000)")
        if len(content.hashtags) > 13:
            warnings.append(f"Too many tags ({len(content.hashtags)}/13)")
        return warnings
