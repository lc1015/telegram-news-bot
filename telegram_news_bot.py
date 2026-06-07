"""
Telegram News Bot
=================
Fetches news from NewsAPI and posts articles to a Telegram channel on a schedule.
Each article is tagged with a section label based on its content.

Usage:
    python telegram_news_bot.py
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

# Load .env for local development only; on Railway env vars are injected directly
import os as _os
if _os.path.exists(".env"):
    load_dotenv(override=False)

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
NEWSAPI_BASE = "https://newsapi.org/v2"
POST_DELAY = 3           # seconds between Telegram posts (flood limit safety)
SEEN_TITLES_FILE = Path("seen_titles.txt")
MAX_SEEN_TITLES = 5000

# ── Section definitions ───────────────────────────────────────────────────────
# Each section has an emoji label and a set of trigger keywords (lowercased).
# Articles are matched top-to-bottom; first match wins.
SECTIONS = [
    {
        "label": "📈 Stock Market",
        "keywords": {
            "stocks", "stock market", "s&p", "s&p 500", "nasdaq", "dow jones",
            "dow", "wall street", "fed", "federal reserve", "inflation",
            "interest rate", "rate cut", "rate hike", "earnings", "ipo",
            "bonds", "treasury", "recession", "gdp", "selloff", "sell-off",
            "rally", "bear market", "bull market", "volatility", "vix",
            "hedge fund", "etf", "futures", "yields",
        },
    },
    {
        "label": "💰 Crypto",
        "keywords": {
            "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency",
            "blockchain", "defi", "altcoin", "nft", "web3", "binance",
            "coinbase", "solana", "ripple", "xrp", "stablecoin",
            "spot etf", "halving",
        },
    },
    {
        "label": "🤖 AI",
        "keywords": {
            "ai", "artificial intelligence", "chatgpt", "openai", "claude",
            "gemini", "llm", "machine learning", "deep learning", "generative",
            "anthropic", "gpt", "neural network", "agi", "copilot", "nvidia",
        },
    },
]


def _word_match(keyword: str, text: str) -> bool:
    """True if keyword appears as a whole word (or phrase) in text."""
    pattern = r"(?<![a-z])" + re.escape(keyword) + r"(?![a-z])"
    return bool(re.search(pattern, text))


def detect_section(article: dict) -> dict | None:
    """
    Return the matching SECTIONS entry, or None if the article doesn't
    belong to any of our 3 topics (Stock Market / Crypto / AI).
    Articles returning None are skipped — keeps the channel on-topic.
    """
    text = " ".join([
        (article.get("title") or ""),
        (article.get("description") or ""),
    ]).lower()

    for section in SECTIONS:
        if any(_word_match(kw, text) for kw in section["keywords"]):
            return section

    return None  # off-topic — will be filtered out


class TelegramNewsBot:
    """Fetches news from NewsAPI and publishes labelled articles to a Telegram channel."""

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
        self.newsapi_key = os.getenv("NEWSAPI_KEY", "").strip()

        if not all([self.token, self.channel_id, self.newsapi_key]):
            missing = [k for k, v in {
                "TELEGRAM_BOT_TOKEN": self.token,
                "TELEGRAM_CHANNEL_ID": self.channel_id,
                "NEWSAPI_KEY": self.newsapi_key,
            }.items() if not v]
            raise ValueError(f"Missing credentials: {missing}. Set them in your .env or Railway Variables.")

        raw_keywords = os.getenv("KEYWORDS", "Bitcoin,MSFT,Apple")
        self.keywords = [k.strip() for k in raw_keywords.split(",") if k.strip()]
        self.interval_minutes = int(os.getenv("INTERVAL_MINUTES", "30"))
        self.max_articles = int(os.getenv("MAX_ARTICLES_PER_CYCLE", "5"))
        self.news_category = os.getenv("NEWS_CATEGORY", "").strip()
        self.news_country = os.getenv("NEWS_COUNTRY", "us").strip()

        self.bot = Bot(token=self.token)
        self.seen_titles: set[str] = self._load_seen_titles()

        log.info(
            "Bot initialised | channel=%s | keywords=%s | interval=%dm",
            self.channel_id, self.keywords, self.interval_minutes,
        )

    # ── Deduplication ─────────────────────────────────────────────────────────

    def _load_seen_titles(self) -> set[str]:
        if not SEEN_TITLES_FILE.exists():
            return set()
        lines = SEEN_TITLES_FILE.read_text(encoding="utf-8").splitlines()
        return set(lines[-MAX_SEEN_TITLES:])

    def _save_seen_titles(self) -> None:
        titles = list(self.seen_titles)[-MAX_SEEN_TITLES:]
        SEEN_TITLES_FILE.write_text("\n".join(titles), encoding="utf-8")

    def _is_duplicate(self, title: str) -> bool:
        return title.lower().strip() in self.seen_titles

    def _mark_seen(self, title: str) -> None:
        self.seen_titles.add(title.lower().strip())

    # ── NewsAPI fetching ──────────────────────────────────────────────────────

    def _build_keyword_queries(self) -> list[str]:
        """
        Combine all keywords into as few OR-queries as possible.
        NewsAPI limits the q parameter to 500 chars, so we chunk if needed.
        This keeps us well under the free-tier 100 requests/day limit.
        """
        queries: list[str] = []
        current: list[str] = []
        for kw in self.keywords:
            # Quote multi-word keywords so they match as phrases
            term = f'"{kw}"' if " " in kw else kw
            candidate = " OR ".join(current + [term])
            if len(candidate) > 450:  # leave headroom under the 500-char limit
                queries.append(" OR ".join(current))
                current = [term]
            else:
                current.append(term)
        if current:
            queries.append(" OR ".join(current))
        return queries

    def _fetch_by_query(self, query: str) -> list[dict]:
        """Fetch articles for a combined OR-query (one HTTP request)."""
        params = {
            "q": query,
            "apiKey": self.newsapi_key,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 30,
        }
        try:
            resp = requests.get(f"{NEWSAPI_BASE}/everything", params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except requests.RequestException as exc:
            log.warning("NewsAPI query fetch failed: %s", exc)
            return []

    def _fetch_by_category(self) -> list[dict]:
        params = {
            "apiKey": self.newsapi_key,
            "country": self.news_country,
            "category": self.news_category,
            "pageSize": 10,
        }
        try:
            resp = requests.get(f"{NEWSAPI_BASE}/top-headlines", params=params, timeout=10)
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except requests.RequestException as exc:
            log.warning("NewsAPI category fetch failed: %s", exc)
            return []

    def _collect_articles(self) -> list[dict]:
        raw: list[dict] = []

        if self.news_category:
            raw.extend(self._fetch_by_category())

        # One request per combined OR-query (instead of one per keyword)
        for query in self._build_keyword_queries():
            raw.extend(self._fetch_by_query(query))

        fresh = []
        seen_this_cycle: set[str] = set()
        skipped_offtopic = 0
        for article in raw:
            title = (article.get("title") or "").strip()
            url = (article.get("url") or "").strip()
            if not title or not url or title == "[Removed]":
                continue
            norm = title.lower()
            if norm in seen_this_cycle or self._is_duplicate(title):
                continue

            # Only keep articles that match one of our 3 topics
            section = detect_section(article)
            if section is None:
                skipped_offtopic += 1
                continue

            seen_this_cycle.add(norm)
            article["_section"] = section  # cache for posting
            fresh.append(article)
            if len(fresh) >= self.max_articles:
                break

        log.info(
            "Collected %d on-topic articles (from %d raw, %d off-topic skipped)",
            len(fresh), len(raw), skipped_offtopic,
        )
        return fresh

    # ── Message formatting ────────────────────────────────────────────────────

    @staticmethod
    def _format_message(article: dict, section: dict) -> str:
        """Build an HTML message with a section label header."""
        title = article.get("title", "No title").strip()
        description = (article.get("description") or "").strip()
        url = article.get("url", "")
        source = (article.get("source") or {}).get("name", "Unknown source")

        published_at = article.get("publishedAt", "")
        try:
            dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            time_str = dt.strftime("%b %d, %Y %H:%M UTC")
        except (ValueError, AttributeError):
            time_str = published_at or "Unknown time"

        lines = [
            # Section label bar at the top
            f"<b>{section['label']}</b>",
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
            f"<b>{title}</b>",
            "",
        ]
        if description:
            desc = description[:300] + "…" if len(description) > 300 else description
            lines.append(desc)
            lines.append("")

        lines += [
            f"<i>🗞 {source}  •  {time_str}</i>",
            f'<a href="{url}">Read full article →</a>',
        ]
        return "\n".join(lines)

    # ── Telegram posting ──────────────────────────────────────────────────────

    async def _post_article(self, article: dict) -> bool:
        # Use the section detected during collection, or detect on the fly
        section = article.get("_section") or detect_section(article)
        if section is None:  # safety guard — shouldn't happen after filtering
            return False
        message_text = self._format_message(article, section)
        image_url = article.get("urlToImage", "")

        try:
            if image_url and image_url.startswith("http"):
                try:
                    await self.bot.send_photo(
                        chat_id=self.channel_id,
                        photo=image_url,
                        caption=message_text,
                        parse_mode=ParseMode.HTML,
                    )
                    log.info("Posted [%s]: %s", section["label"], article.get("title", "")[:60])
                    return True
                except TelegramError as img_err:
                    log.debug("Image send failed, falling back to text: %s", img_err)

            await self.bot.send_message(
                chat_id=self.channel_id,
                text=message_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
            log.info("Posted [%s]: %s", section["label"], article.get("title", "")[:60])
            return True

        except TelegramError as exc:
            log.error("Failed to post article '%s': %s", article.get("title"), exc)
            return False

    # ── Main job ──────────────────────────────────────────────────────────────

    async def fetch_and_post(self) -> None:
        log.info("── Fetch cycle started ──────────────────────────────────────")
        articles = self._collect_articles()

        if not articles:
            log.info("No new articles found this cycle.")
            return

        posted = 0
        for article in articles:
            success = await self._post_article(article)
            if success:
                self._mark_seen(article["title"])
                posted += 1
                if posted < len(articles):
                    await asyncio.sleep(POST_DELAY)

        self._save_seen_titles()
        log.info("Cycle complete: posted %d/%d articles.", posted, len(articles))

    # ── Scheduler ─────────────────────────────────────────────────────────────

    async def run(self) -> None:
        log.info("Verifying bot credentials…")
        me = await self.bot.get_me()
        log.info("Logged in as @%s", me.username)

        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            self.fetch_and_post,
            trigger="interval",
            minutes=self.interval_minutes,
            id="news_fetch",
            next_run_time=datetime.now(timezone.utc),
        )
        scheduler.start()
        log.info(
            "Scheduler started — fetching every %d minutes. Press Ctrl+C to stop.",
            self.interval_minutes,
        )

        try:
            while True:
                await asyncio.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            log.info("Shutting down…")
            scheduler.shutdown()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    bot = TelegramNewsBot()
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
