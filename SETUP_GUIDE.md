# Telegram News Bot — Setup Guide

A step-by-step guide for getting the bot running from scratch.

---

## Prerequisites

- Python 3.10 or newer
- A Telegram account
- A free NewsAPI account

---

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 2. Create a Telegram Bot with BotFather

1. Open Telegram and search for **@BotFather**
2. Start a chat and send `/newbot`
3. Follow the prompts:
   - Choose a **display name** (e.g. `My News Bot`)
   - Choose a **username** ending in `bot` (e.g. `my_news_feed_bot`)
4. BotFather will reply with your **bot token** — it looks like:
   ```
   1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
   ```
5. Copy and save this token — you'll need it in the next step.

---

## 3. Create a Telegram Channel

1. In Telegram, tap the pencil icon → **New Channel**
2. Set a name and (optionally) a description
3. Choose **Public** for a username like `@mynewsfeed`, or **Private**
4. Skip adding members for now

### Add your bot as an administrator

1. Open your channel → tap the channel name → **Administrators**
2. **Add Administrator** → search for your bot's username
3. Grant at minimum:
   - ✅ Post Messages
   - ✅ Delete Messages (so test_bot.py can clean up its test message)

---

## 4. Get your channel ID

| Channel type | How to find the ID |
|---|---|
| Public | Use the username, e.g. `@mynewsfeed` |
| Private | Forward any channel message to **@userinfobot** — it replies with `chat_id: -100xxxxxxxxxx` |

---

## 5. Get a free NewsAPI key

1. Go to [https://newsapi.org/register](https://newsapi.org/register)
2. Sign up with your email address
3. Your API key appears on the dashboard immediately

> **Free tier limits:** 100 requests/day, articles up to 1 month old.  
> For production use, consider a paid plan.

---

## 6. Configure the bot

Run the interactive wizard:

```bash
python setup.py
```

This creates a `.env` file with your credentials. You can also copy `.env.example` to `.env` and edit it manually.

---

## 7. Verify everything works

```bash
python test_bot.py
```

This checks all four things in order:
1. `.env` variables are set
2. Bot token is valid
3. Bot can post to the channel
4. NewsAPI key returns results

---

## 8. Start the bot

```bash
python telegram_news_bot.py
```

The bot will:
- Run immediately on startup
- Fetch news every `INTERVAL_MINUTES` minutes (default: 30)
- Post up to `MAX_ARTICLES_PER_CYCLE` articles per cycle (default: 5)
- Skip articles already posted (tracked in `seen_titles.txt`)
- Log activity to `bot.log` and the console

Press **Ctrl+C** to stop.

---

## Advanced: run with a named profile

```bash
# List available profiles
python config_advanced.py --list

# Run with the crypto profile (Bitcoin, Ethereum, etc.)
python config_advanced.py --profile crypto

# Preview a profile without starting
python config_advanced.py --profile tech --dry-run
```

Edit `config_advanced.py` to add your own profiles with custom keywords and intervals.

---

## File reference

| File | Purpose |
|---|---|
| `telegram_news_bot.py` | Main bot — run this to start |
| `test_bot.py` | Credential verifier |
| `setup.py` | Interactive setup wizard |
| `config_advanced.py` | Multi-profile runner |
| `.env` | Your credentials (git-ignored) |
| `.env.example` | Credential template |
| `seen_titles.txt` | Auto-generated dedup database |
| `bot.log` | Auto-generated log file |
| `requirements.txt` | Python dependencies |

---

## Troubleshooting

**"Chat not found" / "Forbidden"**  
→ Make sure the bot is an admin of the channel and the channel ID is correct.

**"Invalid API key" from NewsAPI**  
→ Double-check the key in `.env`. Free keys activate within a few minutes of registration.

**Articles aren't posting**  
→ Check `bot.log` for error details. Free NewsAPI keys return older articles — if all articles are already in `seen_titles.txt`, delete that file to reset dedup state.

**Bot stops unexpectedly**  
→ Look for exceptions in `bot.log`. Common causes: network timeout, Telegram rate limit (try increasing `INTERVAL_MINUTES`).

---

## Keeping the bot running 24/7

On Linux/macOS, use **systemd** or **screen**:
```bash
screen -S newsbot
python telegram_news_bot.py
# Detach with Ctrl+A, D
```

On Windows, use **Task Scheduler** or run in a terminal you leave open.
