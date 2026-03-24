import os
import yaml
from core.models import Product, AdContent


class ContentGenerator:
    def __init__(self, config_path: str = "config.yaml"):
        self.config = {}
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = yaml.safe_load(f) or {}

    def _get_platform_config(self, platform: str) -> dict:
        return self.config.get("platforms", {}).get(platform, {})

    def _get_default_hashtags(self, platform: str) -> list[str]:
        platform_conf = self._get_platform_config(platform)
        platform_tags = platform_conf.get("default_hashtags", [])
        default_tags = self.config.get("defaults", {}).get("hashtags", [])
        return platform_tags + default_tags

    def _get_cta(self) -> str:
        return self.config.get("defaults", {}).get("cta", "Shop now!")

    def generate(self, product: Product, platform: str) -> AdContent:
        generators = {
            "tiktok": self._tiktok,
            "youtube_shorts": self._youtube_shorts,
            "instagram": self._instagram,
            "pinterest": self._pinterest,
            "facebook": self._facebook,
            "twitter": self._twitter,
            "amazon": self._amazon,
            "etsy": self._etsy,
        }
        generator = generators.get(platform)
        if not generator:
            raise ValueError(f"Unknown platform: {platform}")
        return generator(product)

    def _tiktok(self, product: Product) -> AdContent:
        caption = f"You NEED this! {product.title} - only {product.price_display}!"
        hashtags = self._get_default_hashtags("tiktok")
        product_tags = [f"#{tag.replace(' ', '')}" for tag in product.tags[:3]]
        return AdContent(
            caption=caption,
            hashtags=hashtags + product_tags,
            description=product.description[:300],
            cta=self._get_cta(),
            media_urls=product.images[:1],
            title=product.title,
        )

    def _youtube_shorts(self, product: Product) -> AdContent:
        title = f"{product.title} - {product.price_display} #Shorts"
        description = (
            f"{product.description[:200]}\n\n"
            f"Shop now: {product.url}\n\n"
            f"{product.price_display}"
        )
        hashtags = self._get_default_hashtags("youtube_shorts")
        return AdContent(
            caption=description,
            hashtags=hashtags,
            description=description,
            cta=f"Shop now: {product.url}",
            media_urls=product.images[:1],
            title=title,
        )

    def _instagram(self, product: Product) -> AdContent:
        caption = (
            f"NEW DROP! {product.title}\n\n"
            f"{product.description[:200]}\n\n"
            f"Only {product.price_display}"
        )
        hashtags = self._get_default_hashtags("instagram")
        product_tags = [f"#{tag.replace(' ', '')}" for tag in product.tags[:5]]
        return AdContent(
            caption=caption,
            hashtags=hashtags + product_tags,
            description=product.description,
            cta=self._get_cta(),
            media_urls=product.images[:10],
            title=product.title,
        )

    def _pinterest(self, product: Product) -> AdContent:
        description = (
            f"{product.title} - {product.price_display}\n\n"
            f"{product.description[:500]}\n\n"
            f"Shop this product and more at our store!"
        )
        hashtags = self._get_default_hashtags("pinterest")
        product_tags = [f"#{tag.replace(' ', '')}" for tag in product.tags[:5]]
        return AdContent(
            caption=product.title,
            hashtags=hashtags + product_tags,
            description=description,
            cta=product.url,
            media_urls=product.images[:1],
            title=product.title,
        )

    def _facebook(self, product: Product) -> AdContent:
        caption = (
            f"Check out {product.title}!\n\n"
            f"{product.description[:300]}\n\n"
            f"Price: {product.price_display}\n"
            f"Shop here: {product.url}"
        )
        hashtags = self._get_default_hashtags("facebook")
        return AdContent(
            caption=caption,
            hashtags=hashtags,
            description=product.description,
            cta=f"Shop now: {product.url}",
            media_urls=product.images[:4],
            title=product.title,
        )

    def _twitter(self, product: Product) -> AdContent:
        hashtags = self._get_default_hashtags("twitter")
        tags_str = " ".join(hashtags[:2])
        max_text_len = 280 - len(tags_str) - len(product.url) - 4
        text = f"{product.title} - {product.price_display}"
        if len(text) > max_text_len:
            text = text[: max_text_len - 3] + "..."
        caption = f"{text}\n{product.url}\n{tags_str}"
        return AdContent(
            caption=caption,
            hashtags=hashtags,
            description=product.description[:200],
            cta=product.url,
            media_urls=product.images[:4],
            title=product.title,
        )

    def _amazon(self, product: Product) -> AdContent:
        bullets = product.description.split(". ")[:5]
        bullet_list = "\n".join(f"- {b.strip()}" for b in bullets if b.strip())
        description = (
            f"{product.title}\n\n"
            f"Key Features:\n{bullet_list}\n\n"
            f"Price: {product.price_display}"
        )
        return AdContent(
            caption=product.title,
            hashtags=[],
            description=description,
            cta="Add to Cart",
            media_urls=product.images,
            title=product.title,
        )

    def _etsy(self, product: Product) -> AdContent:
        tags = product.tags[:13]  # Etsy allows up to 13 tags
        description = (
            f"{product.description}\n\n"
            f"Price: {product.price_display}\n\n"
            f"Visit our Shopify store for more: {product.url}"
        )
        return AdContent(
            caption=product.title,
            hashtags=[f"#{t.replace(' ', '')}" for t in tags],
            description=description,
            cta="Buy Now",
            media_urls=product.images,
            title=product.title,
        )
