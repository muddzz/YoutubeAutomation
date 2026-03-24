import os
import requests

from core.models import AdContent, PostResult
from platforms.base import BaseDistributor


class YouTubeShortsDistributor(BaseDistributor):
    """Distribute content via YouTube Data API v3 as Shorts."""

    platform_name = "youtube_shorts"
    UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
    API_URL = "https://www.googleapis.com/youtube/v3"

    def authenticate(self, credentials: dict) -> None:
        self.client_id = credentials.get("client_id") or os.getenv("YOUTUBE_CLIENT_ID")
        self.client_secret = credentials.get("client_secret") or os.getenv("YOUTUBE_CLIENT_SECRET")

        tokens = self.oauth.get_tokens("youtube")
        if tokens:
            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def authorize(self) -> dict:
        return self.oauth.authorize(
            platform="youtube",
            client_id=self.client_id,
            client_secret=self.client_secret,
            auth_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            scopes=[
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube",
            ],
            extra_params={"access_type": "offline", "prompt": "consent"},
        )

    def post(self, content: AdContent) -> PostResult:
        try:
            tokens = self.oauth.get_tokens("youtube")
            if not tokens:
                return self._failure("Not authenticated. Run: python cli.py auth youtube_shorts")

            self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

            # Ensure #Shorts is in the title
            title = content.title
            if "#Shorts" not in title:
                title = f"{title} #Shorts"
            title = title[:100]

            tags = [h.lstrip("#") for h in content.hashtags]
            description = content.full_caption

            # Download video first if it's a URL
            video_path = None
            if content.media_urls:
                video_url = content.media_urls[0]
                resp = requests.get(video_url, stream=True)
                resp.raise_for_status()
                video_path = "/tmp/yt_upload_video.mp4"
                with open(video_path, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)

            if not video_path:
                return self._failure("No video to upload")

            # Upload video
            metadata = {
                "snippet": {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "categoryId": "22",  # People & Blogs
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                },
            }

            import json

            upload_resp = self.session.post(
                f"{self.UPLOAD_URL}?uploadType=multipart&part=snippet,status",
                files={
                    "metadata": (
                        "metadata.json",
                        json.dumps(metadata),
                        "application/json",
                    ),
                    "file": ("video.mp4", open(video_path, "rb"), "video/mp4"),
                },
            )

            if upload_resp.status_code == 401:
                self._refresh_tokens()
                upload_resp = self.session.post(
                    f"{self.UPLOAD_URL}?uploadType=multipart&part=snippet,status",
                    files={
                        "metadata": (
                            "metadata.json",
                            json.dumps(metadata),
                            "application/json",
                        ),
                        "file": ("video.mp4", open(video_path, "rb"), "video/mp4"),
                    },
                )

            upload_resp.raise_for_status()
            video_data = upload_resp.json()
            video_id = video_data["id"]

            return self._success(
                post_id=video_id,
                post_url=f"https://youtube.com/shorts/{video_id}",
            )

        except Exception as e:
            return self._failure(str(e))
        finally:
            if video_path and os.path.exists(video_path):
                os.remove(video_path)

    def _refresh_tokens(self):
        tokens = self.oauth.refresh_token(
            "youtube",
            self.client_id,
            self.client_secret,
            "https://oauth2.googleapis.com/token",
        )
        self.session.headers["Authorization"] = f"Bearer {tokens['access_token']}"

    def validate_content(self, content: AdContent) -> list[str]:
        warnings = []
        if len(content.title) > 100:
            warnings.append(f"Title too long ({len(content.title)}/100 chars)")
        if not content.media_urls:
            warnings.append("No video URL provided")
        return warnings
