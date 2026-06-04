"""
config_advanced.py — Multi-profile configuration
=================================================
Define multiple named profiles and switch between them without editing .env.

Usage:
    python config_advanced.py --profile tech
    python config_advanced.py --profile crypto --dry-run
    python config_advanced.py --list

Each profile overrides the values in .env for that run.
"""

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Profile:
    name: str
    description: str
    keywords: list[str]
    interval_minutes: int = 30
    max_articles_per_cycle: int = 5
    # Set to a NewsAPI category string to enable category mode alongside keywords
    news_category: str = ""
    news_country: str = "us"


# ── Define your profiles here ─────────────────────────────────────────────────

PROFILES: dict[str, Profile] = {
    "crypto": Profile(
        name="crypto",
        description="Cryptocurrency and blockchain news",
        keywords=["Bitcoin", "Ethereum", "crypto", "blockchain", "DeFi", "altcoin"],
        interval_minutes=15,
        max_articles_per_cycle=5,
    ),
    "tech": Profile(
        name="tech",
        description="Big Tech companies and product launches",
        keywords=["Apple", "MSFT", "Google", "Meta", "Amazon", "NVIDIA", "OpenAI"],
        interval_minutes=30,
        max_articles_per_cycle=5,
        news_category="technology",
    ),
    "markets": Profile(
        name="markets",
        description="Stock market, macro, and financial news",
        keywords=["S&P 500", "Federal Reserve", "inflation", "earnings", "IPO", "bonds"],
        interval_minutes=20,
        max_articles_per_cycle=6,
        news_category="business",
    ),
    "ai": Profile(
        name="ai",
        description="Artificial intelligence research and products",
        keywords=["AI", "LLM", "ChatGPT", "Claude", "Gemini", "machine learning", "AGI"],
        interval_minutes=30,
        max_articles_per_cycle=5,
    ),
    "general": Profile(
        name="general",
        description="Top headlines — broad coverage",
        keywords=[],
        interval_minutes=60,
        max_articles_per_cycle=5,
        news_category="general",
        news_country="us",
    ),
}


def apply_profile(profile: Profile, dry_run: bool = False) -> None:
    """Inject profile values into environment variables, then run the bot."""
    print(f"\n[Profile: {profile.name}] {profile.description}")
    print(f"  Keywords:  {', '.join(profile.keywords) or '(none — category mode)'}")
    print(f"  Category:  {profile.news_category or 'disabled'}")
    print(f"  Interval:  {profile.interval_minutes} minutes")
    print(f"  Max posts: {profile.max_articles_per_cycle} per cycle")

    if dry_run:
        print("\n  [dry-run] Would set these env vars and start the bot.")
        return

    # Override env vars for this process
    os.environ["KEYWORDS"] = ",".join(profile.keywords)
    os.environ["INTERVAL_MINUTES"] = str(profile.interval_minutes)
    os.environ["MAX_ARTICLES_PER_CYCLE"] = str(profile.max_articles_per_cycle)
    os.environ["NEWS_CATEGORY"] = profile.news_category
    os.environ["NEWS_COUNTRY"] = profile.news_country

    # Import here to pick up the modified environment
    from telegram_news_bot import TelegramNewsBot
    bot = TelegramNewsBot()
    asyncio.run(bot.run())


def list_profiles() -> None:
    print("\nAvailable profiles:\n")
    for name, p in PROFILES.items():
        kw_preview = ", ".join(p.keywords[:4])
        if len(p.keywords) > 4:
            kw_preview += f", +{len(p.keywords) - 4} more"
        print(f"  {name:<12} {p.description}")
        print(f"             keywords: {kw_preview or '(category mode)'}")
        print(f"             interval: {p.interval_minutes}m  max: {p.max_articles_per_cycle}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Run the news bot with a named profile")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profile", "-p", choices=PROFILES.keys(), help="Profile to run")
    group.add_argument("--list", "-l", action="store_true", help="List available profiles")
    parser.add_argument("--dry-run", action="store_true", help="Print config without starting")
    args = parser.parse_args()

    if args.list:
        list_profiles()
        return

    apply_profile(PROFILES[args.profile], dry_run=args.dry_run)


if __name__ == "__main__":
    main()
