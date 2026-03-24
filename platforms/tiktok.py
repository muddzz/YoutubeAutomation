import os
import requests

from core.models import AdContent, PostResult
from platforms.base import BaseDistributor


class TikTokDistributor(BaseDistributor):
    """Distribute content via TikTok Content Posting API."""

    platform_name = "tiktok"
    BASE_URL = "https://open.tiktokapis.com/v2"

    def authenticate(self, credentials: dict) -> None:
        self.client_key = credentials.get("client_key") or os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = credentials.get("client_secret") or os.getenv("TIKTOK_CLIENT_SECRET")

        tokens = self.oauth.get_tokens("tiktok")
        if tokens:
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def authorize(self) -> dict:
        return self.oauth.authorize(
            platform="tiktok",
            client_id=self.client_key,
            client_secret=self.client_secret,
            auth_url="https://www.tiktok.com/v2/auth/authorize/",
            token_url=f"{self.BASE_URL}/oauth/token/",
            scopes=["video.publish", "video.upload"],
            use_pkce=True,
            extra_params={"response_type": "code"},
        )

    def post(self, content: AdContent) -> PostResult:
        try:
            tokens = self.oauth.get_tokens("tiktok")
            if not tokens:
                return self._failure("Not authenticated. Run: python cli.py auth tiktok")

            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

            # Step 1: Initialize video upload
            init_resp = self.session.post(
                f"{self.BASE_URL}/post/publish/inbox/video/init/",
                json={
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "video_url": content.media_urls[0] if content.media_urls else "",
                    }
                },
            )

            if init_resp.status_code == 401:
                self._refresh_and_retry(content)

            init_resp.raise_for_status()
            init_data = init_resp.json()

            publish_id = init_data.get("data", {}).get("publish_id")
            if not publish_id:
                return self._failure(f"Failed to init upload: {init_data}")

            # Step 2: Publish with caption
            caption = content.caption
            tags = " ".join(content.hashtags[:5])
            full_caption = f"{caption} {tags}"[:2200]

            publish_resp = self.session.post(
                f"{self.BASE_URL}/post/publish/",
                json={
                    "publish_id": publish_id,
                    "post_info": {
                        "title": full_caption,
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                        "disable_comment": False,
                        "disable_duet": False,
                        "disable_stitch": False,
                    },
                },
            )
            publish_resp.raise_for_status()
            pub_data = publish_resp.json()

            post_id = pub_data.get("data", {}).get("publish_id", publish_id)
            return self._success(post_id=post_id)

        except Exception as e:
            return self._failure(str(e))

    def _refresh_and_retry(self, content: AdContent):
        tokens = self.oauth.refresh_token(
            "tiktok",
            self.client_key,
            self.client_secret,
            f"{self.BASE_URL}/oauth/token/",
        )
        self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def validate_content(self, content: AdContent) -> list[str]:
        warnings = []
        full_text = content.full_caption
        if len(full_text) > 2200:
            warnings.append(f"Caption too long ({len(full_text)}/2200 chars)")
        if not content.media_urls:
            warnings.append("No media URLs - TikTok requires a video")
        return warnings
