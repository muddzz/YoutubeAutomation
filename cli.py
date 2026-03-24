#!/usr/bin/env python3
"""
Multi-Platform Ad Distributor for Shopify Stores

Pulls products from your Shopify store and distributes them as ads
across TikTok, YouTube Shorts, Instagram, Pinterest, Facebook,
Twitter/X, Amazon, and Etsy.
"""

import argparse
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from core.shopify_client import ShopifyClient
from core.content_generator import ContentGenerator
from core.scheduler import PostScheduler
from platforms import PLATFORMS


def cmd_products(args):
    """List products from Shopify store."""
    client = ShopifyClient()
    products = client.get_products(limit=args.limit)

    if not products:
        print("No products found.")
        return

    print(f"\n{'ID':<15} {'Price':<10} {'Title'}")
    print("-" * 60)
    for p in products:
        print(f"{p.id:<15} {p.price_display:<10} {p.title}")
    print(f"\nTotal: {len(products)} products")


def cmd_preview(args):
    """Preview generated ad content for a product."""
    client = ShopifyClient()
    generator = ContentGenerator()

    product = client.get_product(args.product_id)
    platforms = args.platforms.split(",") if args.platforms else list(PLATFORMS.keys())

    for platform in platforms:
        platform = platform.strip()
        if platform not in PLATFORMS:
            print(f"\nUnknown platform: {platform}")
            continue

        content = generator.generate(product, platform)

        # Validate
        distributor_cls = PLATFORMS[platform]
        try:
            distributor = distributor_cls.__new__(distributor_cls)
            distributor.platform_name = platform
            warnings = distributor.validate_content(content)
        except Exception:
            warnings = []

        print(f"\n{'=' * 60}")
        print(f"  PLATFORM: {platform.upper()}")
        print(f"{'=' * 60}")
        if content.title:
            print(f"  Title: {content.title}")
        print(f"  Caption:\n    {content.caption[:200]}...")
        if content.hashtags:
            print(f"  Hashtags: {' '.join(content.hashtags[:8])}")
        print(f"  CTA: {content.cta}")
        print(f"  Media: {len(content.media_urls)} file(s)")
        if warnings:
            print(f"  Warnings: {', '.join(warnings)}")


def cmd_post(args):
    """Post a product to specified platforms."""
    client = ShopifyClient()
    generator = ContentGenerator()

    product = client.get_product(args.product_id)
    platforms = args.platforms.split(",")

    if args.schedule:
        scheduler = PostScheduler()
        run_at = datetime.fromisoformat(args.schedule)
        job_id = scheduler.schedule_post(
            post_func=_execute_post,
            product_id=args.product_id,
            platforms=platforms,
            run_at=run_at,
        )
        print(f"\nScheduled post for {run_at}")
        print(f"Job ID: {job_id}")
        print("Run 'python cli.py daemon' to start the scheduler.")
        return

    _execute_post(args.product_id, platforms)


def _execute_post(product_id: str, platforms: list[str]):
    """Execute posting to platforms."""
    client = ShopifyClient()
    generator = ContentGenerator()

    product = client.get_product(product_id)

    print(f"\nPosting: {product.title}")
    print(f"Platforms: {', '.join(platforms)}")
    print("-" * 40)

    results = []
    for platform_name in platforms:
        platform_name = platform_name.strip()
        if platform_name not in PLATFORMS:
            print(f"  Unknown platform: {platform_name}")
            continue

        content = generator.generate(product, platform_name)
        distributor = PLATFORMS[platform_name]()

        # Validate first
        warnings = distributor.validate_content(content)
        if warnings:
            print(f"  [{platform_name}] Warnings: {', '.join(warnings)}")

        print(f"  Posting to {platform_name}...", end=" ")
        result = distributor.post(content)
        results.append(result)
        print(result)

    # Summary
    success = sum(1 for r in results if r.success)
    failed = sum(1 for r in results if not r.success)
    print(f"\nDone: {success} succeeded, {failed} failed")


def cmd_post_all(args):
    """Post all products to specified platforms."""
    client = ShopifyClient()
    products = client.get_products(limit=args.limit)
    platforms = args.platforms.split(",")

    print(f"\nPosting {len(products)} products to: {', '.join(platforms)}")
    print("=" * 60)

    for product in products:
        _execute_post(product.id, platforms)
        print()


def cmd_auth(args):
    """Authenticate with a platform."""
    platform = args.platform.strip()
    if platform not in PLATFORMS:
        print(f"Unknown platform: {platform}")
        print(f"Available: {', '.join(PLATFORMS.keys())}")
        return

    distributor = PLATFORMS[platform]()
    distributor.authorize()


def cmd_schedule_list(args):
    """List scheduled posts."""
    scheduler = PostScheduler()
    jobs = scheduler.list_scheduled()

    if not jobs:
        print("No scheduled posts.")
        return

    print(f"\n{'Job ID':<40} {'Scheduled For'}")
    print("-" * 70)
    for job in jobs:
        print(f"{job['id']:<40} {job['next_run']}")


def cmd_schedule_cancel(args):
    """Cancel a scheduled post."""
    scheduler = PostScheduler()
    if scheduler.cancel(args.job_id):
        print(f"Cancelled job: {args.job_id}")
    else:
        print(f"Job not found: {args.job_id}")


def cmd_daemon(args):
    """Run the scheduler daemon."""
    scheduler = PostScheduler()
    scheduler.start()
    print("Scheduler daemon running. Press Ctrl+C to stop.")
    try:
        import time

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("\nScheduler stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Platform Ad Distributor for Shopify Stores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py products                                    # List your Shopify products
  python cli.py preview 12345 --platforms tiktok,instagram  # Preview ad content
  python cli.py post 12345 --platforms tiktok,youtube_shorts,instagram
  python cli.py post 12345 --platforms twitter --schedule "2026-04-01 10:00"
  python cli.py post-all --platforms pinterest,facebook --limit 10
  python cli.py auth tiktok                                 # Set up TikTok OAuth
  python cli.py schedule list                               # View scheduled posts
  python cli.py daemon                                      # Run scheduler
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # products
    p_products = subparsers.add_parser("products", help="List Shopify products")
    p_products.add_argument("--limit", type=int, default=50, help="Max products to fetch")
    p_products.set_defaults(func=cmd_products)

    # preview
    p_preview = subparsers.add_parser("preview", help="Preview ad content for a product")
    p_preview.add_argument("product_id", help="Shopify product ID")
    p_preview.add_argument("--platforms", help="Comma-separated platforms (default: all)")
    p_preview.set_defaults(func=cmd_preview)

    # post
    p_post = subparsers.add_parser("post", help="Post a product to platforms")
    p_post.add_argument("product_id", help="Shopify product ID")
    p_post.add_argument("--platforms", required=True, help="Comma-separated platforms")
    p_post.add_argument("--schedule", help="Schedule for later (ISO format: 2026-04-01T10:00)")
    p_post.set_defaults(func=cmd_post)

    # post-all
    p_post_all = subparsers.add_parser("post-all", help="Post all products to platforms")
    p_post_all.add_argument("--platforms", required=True, help="Comma-separated platforms")
    p_post_all.add_argument("--limit", type=int, default=50, help="Max products")
    p_post_all.set_defaults(func=cmd_post_all)

    # auth
    p_auth = subparsers.add_parser("auth", help="Authenticate with a platform")
    p_auth.add_argument("platform", help="Platform name")
    p_auth.set_defaults(func=cmd_auth)

    # schedule
    p_schedule = subparsers.add_parser("schedule", help="Manage scheduled posts")
    schedule_sub = p_schedule.add_subparsers(dest="schedule_command")

    p_sched_list = schedule_sub.add_parser("list", help="List scheduled posts")
    p_sched_list.set_defaults(func=cmd_schedule_list)

    p_sched_cancel = schedule_sub.add_parser("cancel", help="Cancel a scheduled post")
    p_sched_cancel.add_argument("job_id", help="Job ID to cancel")
    p_sched_cancel.set_defaults(func=cmd_schedule_cancel)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run scheduler daemon")
    p_daemon.set_defaults(func=cmd_daemon)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
