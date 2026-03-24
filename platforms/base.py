from abc import ABC, abstractmethod
from datetime import datetime

import requests

from core.models import AdContent, PostResult
from auth.oauth import OAuthManager


class BaseDistributor(ABC):
    """Base class for all platform distributors."""

    platform_name: str = "unknown"

    def __init__(self, credentials: dict = None):
        self.session = requests.Session()
        self.oauth = OAuthManager()
        self.credentials = credentials or {}
        self.authenticate(self.credentials)

    @abstractmethod
    def authenticate(self, credentials: dict) -> None:
        """Set up authentication for API calls."""
        ...

    @abstractmethod
    def post(self, content: AdContent) -> PostResult:
        """Publish content to the platform."""
        ...

    def validate_content(self, content: AdContent) -> list[str]:
        """Return list of validation warnings."""
        return []

    def _success(self, post_id: str = None, post_url: str = None) -> PostResult:
        return PostResult(
            platform=self.platform_name,
            success=True,
            post_id=post_id,
            post_url=post_url,
            timestamp=datetime.now(),
        )

    def _failure(self, error: str) -> PostResult:
        return PostResult(
            platform=self.platform_name,
            success=False,
            error=error,
            timestamp=datetime.now(),
        )
