from platforms.tiktok import TikTokDistributor
from platforms.youtube_shorts import YouTubeShortsDistributor
from platforms.instagram import InstagramDistributor
from platforms.pinterest import PinterestDistributor
from platforms.facebook import FacebookDistributor
from platforms.twitter import TwitterDistributor
from platforms.amazon import AmazonDistributor
from platforms.etsy import EtsyDistributor

PLATFORMS = {
    "tiktok": TikTokDistributor,
    "youtube_shorts": YouTubeShortsDistributor,
    "instagram": InstagramDistributor,
    "pinterest": PinterestDistributor,
    "facebook": FacebookDistributor,
    "twitter": TwitterDistributor,
    "amazon": AmazonDistributor,
    "etsy": EtsyDistributor,
}

__all__ = ["PLATFORMS"]
