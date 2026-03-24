import os
import requests

from core.models import AdContent, PostResult
from platforms.base import BaseDistributor


class TwitterDistributor(BaseDistributor):
    """Distribute content via Twitter/X API v2."""

    platform_name = "twitter"
    API_URL = "https://api.twitter.com/2"
    UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"

    def authenticate(self, credentials: dict) -> None:
        self.client_id = credentials.get("client_id") or os.getenv("TWITTER_CLIENT_ID")
        self.client_secret = credentials.get("client_secret") or os.getenv("TWITTER_CLIENT_SECRET")

        tokens = self.oauth.get_tokens("twitter")
        if tokens:
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def authorize(self) -> dict:
        return self.oauth.authorize(
            platform="twitter",
            client_id=self.client_id,
            client_secret=self.client_secret,
            auth_url="https://twitter.com/i/oauth2/authorize",
            token_url="https://api.twitter.com/2/oauth2/token",
            scopes=["tweet.read", "tweet.write", "users.read", "offline.access"],
            use_pkce=True,
        )

    def post(self, content: AdContent) -> PostResult:
        try:
            tokens = self.oauth.get_tokens("twitter")
            if not tokens:
                return self._failure("Not authenticated. Run: python cli.py auth twitter")

            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

            tweet_data = {"text": content.caption[:280]}

            # Upload media if available
            if content.media_urls:
                media_ids = self._upload_media(content.media_urls[:4])
                if media_ids:
                    tweet_data["media"] = {"media_ids": media_ids}

            resp = self.session.post(
                f"{self.API_URL}/tweets",
                json=tweet_data,
            )

            if resp.status_code == 401:
                self._refresh()
                resp = self.session.post(
                    f"{self.API_URL}/tweets",
                    json=tweet_data,
                )

            resp.raise_for_status()
            data = resp.json()
            tweet_id = data["data"]["id"]

            return self._success(
                post_id=tweet_id,
                post_url=f"https://twitter.com/i/status/{tweet_id}",
            )

        except Exception as e:
            return self._failure(str(e))

    def _upload_media(self, urls: list[str]) -> list[str]:
        media_ids = []
        for url in urls:
            try:
                img_resp = requests.get(url)
                img_resp.raise_for_status()

                upload_resp = self.session.post(
                    self.UPLOAD_URL,
                    files={"media": ("image.jpg", img_resp.content, "image/jpeg")},
                )
                upload_resp.raise_for_status()
                media_ids.append(upload_resp.json()["media_id_string"])
            except Exception:
                continue
        return media_ids

    def _refresh(self):
        tokens = self.oauth.refresh_token(
            "twitter",
            self.client_id,
            self.client_secret,
            "https://api.twitter.com/2/oauth2/token",
        )
        self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def validate_content(self, content: AdContent) -> list[str]:
        warnings = []
        if len(content.caption) > 280:
            warnings.append(f"Tweet too long ({len(content.caption)}/280 chars)")
        return warnings
