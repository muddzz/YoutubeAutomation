# Multi-Platform Ad Distributor for Shopify Stores

Pull products from your Shopify store and automatically distribute them as ads across **8 platforms**:

| Platform | Type | What it does |
|----------|------|-------------|
| TikTok | Social | Posts product videos via Content Posting API |
| YouTube Shorts | Social | Uploads short-form videos via Data API v3 |
| Instagram | Social | Posts images/carousels/reels via Graph API |
| Pinterest | Social | Creates pins with product images via API v5 |
| Facebook | Social | Posts to your Page via Graph API |
| Twitter/X | Social | Tweets with product images via API v2 |
| Amazon | Marketplace | Creates/updates listings via SP-API |
| Etsy | Marketplace | Creates draft listings via Open API v3 |

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env        # Fill in your Shopify + platform credentials
cp config.yaml.example config.yaml  # Customize hashtags, CTAs, etc.

# 3. Authenticate with platforms
python cli.py auth tiktok
python cli.py auth instagram
python cli.py auth youtube_shorts
# ... repeat for each platform

# 4. List your products
python cli.py products

# 5. Preview before posting
python cli.py preview <product_id> --platforms tiktok,instagram

# 6. Post!
python cli.py post <product_id> --platforms tiktok,instagram,youtube_shorts,pinterest
```

## Commands

```
python cli.py products [--limit N]                          # List Shopify products
python cli.py preview <id> [--platforms x,y]                # Preview generated ad content
python cli.py post <id> --platforms x,y [--schedule TIME]   # Post to platforms
python cli.py post-all --platforms x,y [--limit N]          # Post all products
python cli.py auth <platform>                               # OAuth setup
python cli.py schedule list                                 # View scheduled posts
python cli.py schedule cancel <job_id>                      # Cancel scheduled post
python cli.py daemon                                        # Run scheduler daemon
```

## Configuration

### `.env` — API Credentials

Your Shopify access token + API keys for each platform. See `.env.example`.

### `config.yaml` — Content Settings

Customize per-platform defaults:

```yaml
defaults:
  hashtags: ["#shopify", "#smallbusiness"]
  cta: "Link in bio!"

platforms:
  tiktok:
    default_hashtags: ["#tiktokmademebuyit", "#fyp"]
  instagram:
    ig_user_id: "123456"
  pinterest:
    board_id: "123456"
  facebook:
    page_id: "123456"
```

## Architecture

```
cli.py                      # CLI entry point
core/
  models.py                 # Product, AdContent, PostResult
  shopify_client.py         # Shopify Admin API client
  content_generator.py      # Platform-specific content templates
  scheduler.py              # APScheduler + SQLite persistence
auth/
  oauth.py                  # Shared OAuth2 flow
platforms/
  base.py                   # BaseDistributor ABC
  tiktok.py / youtube_shorts.py / instagram.py / pinterest.py
  facebook.py / twitter.py / amazon.py / etsy.py
```
