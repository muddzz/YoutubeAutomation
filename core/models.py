from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Product:
    id: str
    title: str
    description: str
    price: str
    currency: str
    images: list[str]
    variants: list[dict]
    url: str
    tags: list[str] = field(default_factory=list)

    @property
    def primary_image(self) -> str | None:
        return self.images[0] if self.images else None

    @property
    def price_display(self) -> str:
        symbols = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "C$", "AUD": "A$"}
        symbol = symbols.get(self.currency, self.currency + " ")
        return f"{symbol}{self.price}"


@dataclass
class AdContent:
    caption: str
    hashtags: list[str]
    description: str
    cta: str
    media_urls: list[str]
    title: str = ""

    @property
    def full_caption(self) -> str:
        tags = " ".join(self.hashtags)
        return f"{self.caption}\n\n{self.cta}\n\n{tags}"


@dataclass
class PostResult:
    platform: str
    success: bool
    post_id: str | None = None
    post_url: str | None = None
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        url_info = f" -> {self.post_url}" if self.post_url else ""
        err_info = f" ({self.error})" if self.error else ""
        return f"[{status}] {self.platform}{url_info}{err_info}"
