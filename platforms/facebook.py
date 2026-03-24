import os
import requests

from core.models import AdContent, PostResult
from platforms.base import BaseDistributor


class FacebookDistributor(BaseDistributor):
    """Distribute content via Facebook Graph API."""

    platform_name = "facebook"
    BASE_URL = "https://graph.facebook.com/v18.0"

    def authenticate(self, credentials: dict) -> None:
        self.app_id = credentials.get("app_id") or os.getenv("META_APP_ID")
        self.app_secret = credentials.get("app_secret") or os.getenv("META_APP_SECRET")
        self.page_id = credentials.get("page_id") or os.getenv("FACEBOOK_PAGE_ID")

        tokens = self.oauth.get_tokens("facebook")
        if tokens:
            self.access_token = tokens["access_token"]
        else:
            self.access_token = None

    def authorize(self) -> dict:
        return self.oauth.authorize(
            platform="facebook",
            client_id=self.app_id,
            client_secret=self.app_secret,
            auth_url="https://www.facebook.com/v18.0/dialog/oauth",
            token_url=f"{self.BASE_URL}/oauth/access_token",
            scopes=[
                "pages_manage_posts",
                "pages_read_engagement",
                "pages_show_list",
            ],
        )

    def post(self, content: AdContent) -> PostResult:
        try:
            if not self.access_token:
                return self._failure("Not authenticated. Run: python cli.py auth facebook")
            if not self.page_id:
                return self._failure("FACEBOOK_PAGE_ID not set in .env")

            message = content.full_caption

            if content.media_urls:
                return self._post_with_photo(message, content.media_urls[0])
            else:
                return self._post_text(message)

        except Exception as e:
            return self._failure(str(e))

    def _post_text(self, message: str) -> PostResult:
        resp = requests.post(
            f"{self.BASE_URL}/{self.page_id}/feed",
            params={
                "message": message,
                "access_token": self.access_token,
            },
        )
        resp.raise_for_status()
        post_id = resp.json()["id"]
        return self._success(
            post_id=post_id,
            post_url=f"https://facebook.com/{post_id}",
        )

    def _post_with_photo(self, message: str, image_url: str) -> PostResult:
        resp = requests.post(
            f"{self.BASE_URL}/{self.page_id}/photos",
            params={
                "url": image_url,
                "message": message,
                "access_token": self.access_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        post_id = data.get("post_id") or data.get("id")
        return self._success(
            post_id=post_id,
            post_url=f"https://facebook.com/{post_id}",
        )

    def validate_content(self, content: AdContent) -> list[str]:
        warnings = []
        if len(content.full_caption) > 63206:
            warnings.append("Caption exceeds Facebook's 63,206 character limit")
        return warnings
