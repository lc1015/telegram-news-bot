# Deploying to Railway.app

Railway runs your bot 24/7 in the cloud — even when your PC is off.

---

## Prerequisites

- A [GitHub](https://github.com) account (free)
- A [Railway](https://railway.app) account (free tier, sign in with GitHub)

---

## Step 1 — Push code to GitHub

1. Create a new repo at https://github.com/new
   - Name: `telegram-news-bot`
   - Set to **Private** (your .env is gitignored but keep it private anyway)
   - Do NOT initialise with README

2. Push your local code:
```bash
cd C:\Users\User\news_bot
git remote add origin https://github.com/YOUR_USERNAME/telegram-news-bot.git
git push -u origin main
```

---

## Step 2 — Deploy on Railway

1. Go to https://railway.app and log in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your `telegram-news-bot` repo
4. Railway auto-detects Python and reads `Procfile` — click **Deploy**

---

## Step 3 — Set environment variables on Railway

Your `.env` file is NOT pushed to GitHub (gitignored).  
You must add the variables manually in Railway:

1. Click your project → **Variables** tab
2. Add each variable:

| Variable | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | your token |
| `TELEGRAM_CHANNEL_ID` | your channel |
| `NEWSAPI_KEY` | your key |
| `KEYWORDS` | Malaysia,Ringgit,KLCI,... |
| `INTERVAL_MINUTES` | 30 |
| `MAX_ARTICLES_PER_CYCLE` | 10 |
| `NEWS_CATEGORY` | general |
| `NEWS_COUNTRY` | my |

3. Click **Deploy** — the bot starts automatically

---

## Step 4 — Verify it's running

- Railway → your project → **Logs** tab
- You should see: `Logged in as @your_bot` and fetch cycle logs

---

## Updating the bot later

Just push changes to GitHub — Railway redeploys automatically:
```bash
git add .
git commit -m "update keywords"
git push
```

---

## Free tier limits

Railway free tier gives **$5 credit/month**. A lightweight bot like this
uses roughly **$0.50–1.00/month** — well within the free allowance.

If you exceed it, upgrade to Hobby plan ($5/month) or move to:
- **Render.com** (free tier, 750 hrs/month)
- **PythonAnywhere** (free tier, always-on tasks on paid plan ~$5/month)
