"""
test_bot.py — Credential & connectivity verifier
=================================================
Run this before starting the main bot to confirm everything is wired up:

    python test_bot.py

Checks performed:
  1. .env file exists and all required keys are present
  2. Telegram bot token is valid (calls getMe)
  3. Bot can send a message to the configured channel
  4. NewsAPI key is valid and returns results for the first keyword
"""

import asyncio
import os
import sys

import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

load_dotenv()

# ── ANSI colours for terminal output ──────────────────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

PASS = f"{GREEN}[PASS]{RESET}"
FAIL = f"{RED}[FAIL]{RESET}"
INFO = f"{YELLOW}[INFO]{RESET}"


def section(title: str) -> None:
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print("─" * 50)


# ── 1. Check .env file ────────────────────────────────────────────────────────

def check_env() -> bool:
    section("1 / 4  Environment variables")
    required = {
        "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "TELEGRAM_CHANNEL_ID": os.getenv("TELEGRAM_CHANNEL_ID", ""),
        "NEWSAPI_KEY": os.getenv("NEWSAPI_KEY", ""),
    }
    all_ok = True
    for key, value in required.items():
        if value and value not in ("your_bot_token_here", "your_newsapi_key_here", "@your_channel_here"):
            print(f"  {PASS} {key} is set")
        else:
            print(f"  {FAIL} {key} is missing or still a placeholder")
            all_ok = False

    optional = {
        "KEYWORDS": os.getenv("KEYWORDS", "Bitcoin,MSFT,Apple"),
        "INTERVAL_MINUTES": os.getenv("INTERVAL_MINUTES", "30"),
    }
    for key, value in optional.items():
        print(f"  {INFO} {key} = {value}")

    return all_ok


# ── 2. Check Telegram bot token ───────────────────────────────────────────────

async def check_telegram_bot() -> bool:
    section("2 / 4  Telegram bot token")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        print(f"  {PASS} Token valid — bot is @{me.username} (id={me.id})")
        return True
    except TelegramError as exc:
        print(f"  {FAIL} Token invalid: {exc}")
        return False


# ── 3. Check channel send permission ─────────────────────────────────────────

async def check_channel_send() -> bool:
    section("3 / 4  Telegram channel access")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "")
    bot = Bot(token=token)
    try:
        msg = await bot.send_message(
            chat_id=channel_id,
            text="✅ <b>News Bot test message</b>\n\nCredentials verified successfully!",
            parse_mode="HTML",
        )
        print(f"  {PASS} Test message sent (message_id={msg.message_id})")
        # Clean up the test message
        await bot.delete_message(chat_id=channel_id, message_id=msg.message_id)
        print(f"  {INFO} Test message deleted from channel")
        return True
    except TelegramError as exc:
        print(f"  {FAIL} Could not send to channel '{channel_id}': {exc}")
        print(f"  {INFO} Make sure the bot is an admin of the channel.")
        return False


# ── 4. Check NewsAPI key ──────────────────────────────────────────────────────

def check_newsapi() -> bool:
    section("4 / 4  NewsAPI key")
    api_key = os.getenv("NEWSAPI_KEY", "")
    raw_keywords = os.getenv("KEYWORDS", "Bitcoin")
    keyword = raw_keywords.split(",")[0].strip()

    params = {
        "q": keyword,
        "apiKey": api_key,
        "language": "en",
        "pageSize": 1,
    }
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything", params=params, timeout=10
        )
        data = resp.json()
        if resp.status_code == 200 and data.get("status") == "ok":
            total = data.get("totalResults", 0)
            print(f"  {PASS} NewsAPI key valid — {total} results for '{keyword}'")
            return True
        else:
            msg = data.get("message", resp.text)
            print(f"  {FAIL} NewsAPI error: {msg}")
            return False
    except requests.RequestException as exc:
        print(f"  {FAIL} Request failed: {exc}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print("\n╔══════════════════════════════════════════════╗")
    print("║      Telegram News Bot — Credential Test     ║")
    print("╚══════════════════════════════════════════════╝")

    results = []
    results.append(check_env())

    if results[0]:
        results.append(await check_telegram_bot())
        if results[-1]:
            results.append(await check_channel_send())
        else:
            results.append(False)
        results.append(check_newsapi())
    else:
        print(f"\n  {FAIL} Fix .env before running other checks.")
        sys.exit(1)

    # Summary
    print(f"\n{'─'*50}")
    passed = sum(results)
    total = len(results)
    if passed == total:
        print(f"  {PASS} All {total} checks passed — ready to run the bot!")
        print(f"\n  Start with:  python telegram_news_bot.py\n")
    else:
        print(f"  {FAIL} {total - passed}/{total} checks failed — fix issues above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
