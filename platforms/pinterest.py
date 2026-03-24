import os
import requests

from core.models import AdContent, PostResult
from platforms.base import BaseDistributor


class PinterestDistributor(BaseDistributor):
    """Distribute content via Pinterest API v5."""

    platform_name = "pinterest"
    BASE_URL = "https://api.pinterest.com/v5"

    def authenticate(self, credentials: dict) -> None:
        self.app_id = credentials.get("app_id") or os.getenv("PINTEREST_APP_ID")
        self.app_secret = credentials.get("app_secret") or os.getenv("PINTEREST_APP_SECRET")
        self.board_id = credentials.get("board_id") or os.getenv("PINTEREST_BOARD_ID")

        tokens = self.oauth.get_tokens("pinterest")
        if tokens:
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def authorize(self) -> dict:
        return self.oauth.authorize(
            platform="pinterest",
            client_id=self.app_id,
            client_secret=self.app_secret,
            auth_url="https://www.pinterest.com/oauth/",
            token_url="https://api.pinterest.com/v5/oauth/token",
            scopes=["boards:read", "pins:read", "pins:write"],
        )

    def post(self, content: AdContent) -> PostResult:
        try:
            tokens = self.oauth.get_tokens("pinterest")
            if not tokens:
                return self._failure("Not authenticated. Run: python cli.py auth pinterest")
            if not self.board_id:
                return self._failure("PINTEREST_BOARD_ID not set in .env")

            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

            pin_data = {
                "board_id": self.board_id,
                "title": content.title[:100],
                "description": content.description[:800],
                "link": content.cta if content.cta.startswith("http") else None,
                "media_source": {
                    "source_type": "image_url",
                    "url": content.media_urls[0] if content.media_urls else "",
                },
            }
            # Remove None values
            pin_data = {k: v for k, v in pin_data.items() if v is not None}

            resp = self.session.post(f"{self.BASE_URL}/pins", json=pin_data)

            if resp.status_code == 401:
                self._refresh()
                resp = self.session.post(f"{self.BASE_URL}/pins", json=pin_data)

            resp.raise_for_status()
            data = resp.json()
            pin_id = data.get("id")

            return self._success(
                post_id=pin_id,
                post_url=f"https://www.pinterest.com/pin/{pin_id}/",
            )

        except Exception as e:
            return self._failure(str(e))

    def _refresh(self):
        tokens = self.oauth.refresh_token(
            "pinterest",
            self.app_id,
            self.app_secret,
            "https://api.pinterest.com/v5/oauth/token",
        )
        self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def validate_content(self, content: AdContent) -> list[str]:
        warnings = []
        if not content.media_urls:
            warnings.append("No image URL - Pinterest requires an image")
        if len(content.title) > 100:
            warnings.append(f"Title too long ({len(content.title)}/100)")
        if len(content.description) > 800:
            warnings.append(f"Description too long ({len(content.description)}/800)")
        return warnings
