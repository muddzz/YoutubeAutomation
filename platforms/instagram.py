import os
import time
import requests

from core.models import AdContent, PostResult
from platforms.base import BaseDistributor


class InstagramDistributor(BaseDistributor):
    """Distribute content via Instagram Graph API (through Facebook)."""

    platform_name = "instagram"
    BASE_URL = "https://graph.facebook.com/v18.0"

    def authenticate(self, credentials: dict) -> None:
        self.app_id = credentials.get("app_id") or os.getenv("META_APP_ID")
        self.app_secret = credentials.get("app_secret") or os.getenv("META_APP_SECRET")
        self.ig_user_id = credentials.get("ig_user_id") or os.getenv("INSTAGRAM_USER_ID")

        tokens = self.oauth.get_tokens("instagram")
        if tokens:
            self.access_token = tokens["access_token"]
        else:
            self.access_token = None

    def authorize(self) -> dict:
        return self.oauth.authorize(
            platform="instagram",
            client_id=self.app_id,
            client_secret=self.app_secret,
            auth_url="https://www.facebook.com/v18.0/dialog/oauth",
            token_url=f"{self.BASE_URL}/oauth/access_token",
            scopes=[
                "instagram_basic",
                "instagram_content_publish",
                "pages_show_list",
                "pages_read_engagement",
            ],
        )

    def post(self, content: AdContent) -> PostResult:
        try:
            if not self.access_token:
                return self._failure("Not authenticated. Run: python cli.py auth instagram")
            if not self.ig_user_id:
                return self._failure("INSTAGRAM_USER_ID not set in .env")

            caption = content.full_caption

            # Determine if posting image or carousel
            if len(content.media_urls) == 1:
                return self._post_single(content.media_urls[0], caption)
            elif len(content.media_urls) > 1:
                return self._post_carousel(content.media_urls[:10], caption)
            else:
                return self._failure("No media URLs provided")

        except Exception as e:
            return self._failure(str(e))

    def _post_single(self, image_url: str, caption: str) -> PostResult:
        # Step 1: Create media container
        container_resp = requests.post(
            f"{self.BASE_URL}/{self.ig_user_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": self.access_token,
            },
        )
        container_resp.raise_for_status()
        container_id = container_resp.json()["id"]

        # Step 2: Publish
        publish_resp = requests.post(
            f"{self.BASE_URL}/{self.ig_user_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
        )
        publish_resp.raise_for_status()
        post_id = publish_resp.json()["id"]

        return self._success(
            post_id=post_id,
            post_url=f"https://www.instagram.com/p/{post_id}/",
        )

    def _post_carousel(self, image_urls: list[str], caption: str) -> PostResult:
        # Create individual containers
        children_ids = []
        for url in image_urls:
            resp = requests.post(
                f"{self.BASE_URL}/{self.ig_user_id}/media",
                params={
                    "image_url": url,
                    "is_carousel_item": True,
                    "access_token": self.access_token,
                },
            )
            resp.raise_for_status()
            children_ids.append(resp.json()["id"])

        # Create carousel container
        carousel_resp = requests.post(
            f"{self.BASE_URL}/{self.ig_user_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption,
                "access_token": self.access_token,
            },
        )
        carousel_resp.raise_for_status()
        carousel_id = carousel_resp.json()["id"]

        # Publish
        publish_resp = requests.post(
            f"{self.BASE_URL}/{self.ig_user_id}/media_publish",
            params={
                "creation_id": carousel_id,
                "access_token": self.access_token,
            },
        )
        publish_resp.raise_for_status()
        post_id = publish_resp.json()["id"]

        return self._success(post_id=post_id)

    def validate_content(self, content: AdContent) -> list[str]:
        warnings = []
        if len(content.full_caption) > 2200:
            warnings.append(f"Caption too long ({len(content.full_caption)}/2200)")
        if not content.media_urls:
            warnings.append("No media URLs - Instagram requires images or video")
        if len(content.hashtags) > 30:
            warnings.append("Too many hashtags (max 30)")
        return warnings
