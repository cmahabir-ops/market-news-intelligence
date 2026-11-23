# Market News Intelligence — Version 1

A real RSS news scanner for crypto and US stocks, with rule-based impact hypotheses, title-based deduplication, Telegram alerts, a Streamlit dashboard, and persistent JSON event logs.

**No fabricated news or prices. No AI-model probability predictions. No live market-price validation in v1.** The dashboard displays only items fetched from public RSS sources. This is **not** a guaranteed low-latency or 24/7 service. Google News is an aggregator, not an original-source real-time wire.

## Windows setup

1. Install Python 3.11+ from python.org (check **Add Python to PATH**) and Git for Windows from git-scm.com.
2. Extract this project. Open PowerShell inside the extracted `market_news_intelligence` folder.
3. Run:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python engine.py
   streamlit run app.py
   ```

   If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe engine.py` instead.

4. Open the localhost URL displayed by Streamlit. The first scan fills `data/events.json` but intentionally **does not send historical first-run alerts**.

## Telegram setup

1. In Telegram, message the official `@BotFather`, run `/newbot`, and copy the bot token. Never put it in a public file or chat.
2. Send your new bot a message, such as `/start`.
3. In your browser visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` (substitute your token locally). Find `message.chat.id` in the response. If empty, message the bot again and retry. Treat token as secret.
4. For local testing in PowerShell, set temporary environment variables (replace values):

   ```powershell
   $env:TELEGRAM_BOT_TOKEN="your-token"
   $env:TELEGRAM_CHAT_ID="your-chat-id"
   python engine.py
   ```

   Alerts only send for **new**, significant items after the first scan. For a controlled test, temporarily set `alert_min_score` to 1 in `config.json`, wait for a newly published item, then restore to 3. Do not delete the event log just to test alerts.

## Free cloud setup (GitHub Actions + Streamlit Community Cloud)

**Important limitations:** GitHub scheduled workflows are best-effort, can be delayed or dropped, and may be automatically disabled after inactivity. A five-minute cron is not a five-minute latency guarantee. Streamlit Community Cloud may sleep and is not a reliable push-notification engine. The GitHub repo is public, so its `data/events.json` log is public too. Do not put private information in config or logs. Free-tier policies and quotas can change.

1. Create a **public** GitHub repository at github.com/new, e.g. `market-news-intelligence`.
2. In PowerShell inside the project folder:

   ```powershell
   git init
   git add .
   git commit -m "Initial news scanner"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/market-news-intelligence.git
   git push -u origin main
   ```

   Sign in to GitHub if prompted. Alternatively upload the extracted files via GitHub's web interface, **preserving `.github/workflows/scan.yml`**.
3. In the repository, go to **Settings → Secrets and variables → Actions → New repository secret**. Create `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally `CONTACT_EMAIL` (your contact email for API user-agent compliance).
4. Go to **Settings → Actions → General → Workflow permissions** and select **Read and write permissions** if the repository allows it; save. The workflow must be able to commit `data/events.json`.
5. Go to **Actions → Scan market news → Run workflow**. Inspect the logs for successful feed requests, errors, and a new commit. If a feed errors, the others still run.
6. Visit share.streamlit.io, sign in with GitHub, select the repository, branch `main`, and entrypoint `app.py`. Deploy. Streamlit will redeploy/restart when the repo changes; its page may need refreshing to show newly committed events.
7. Verify alerts by waiting for a newly detected significant headline. Telegram should contain a real source URL and published/detected timestamps. Do not rely on alerts for execution decisions.

## How it works

- `engine.py` requests public RSS feeds listed in `config.json`.
- Only entries with valid publication timestamps within the last 48 hours are considered.
- Deduplication hashes normalized headline text; different headlines about the same story may still appear.
- A transparent keyword heuristic identifies watchlist tickers and a *potential* direction. The 1–5 significance score is not a probability.
- Events are stored in `data/events.json` (most recent 2,000). GitHub Actions commits this file to preserve state between runs.
- New events above the configured threshold are sent to Telegram. **Alert delivery failures are logged but are not retried**; add a durable queue before production use.

## Security and limitations

- Never commit tokens, API keys, passwords, or personal data.
- SEC feed URLs and third-party feed availability can change. Review logs and update `config.json` if necessary.
- The SEC may require an identifiable User-Agent; set `CONTACT_EMAIL`.
- No price/volume analysis, sentiment model, AI LLM, causal validation, or directional probability is claimed in v1.
- Keyword classification can misinterpret negations, sarcasm, indirect effects, and multi-asset relationships.
- Stock exchanges have trading hours; crypto trades around the clock.
- Free hosting is best-effort and can stop or become unavailable. For reliable near-real-time alerts, budget for a continuously running server and licensed data feeds.

## Project files

- `engine.py` — ingestion, dedup, heuristic impact, Telegram alerts, JSON event log
- `app.py` — Streamlit dashboard
- `config.json` — feeds, watchlist, thresholds
- `.github/workflows/scan.yml` — cloud scheduled scanner
- `data/events.json` — initial empty log, populated with actual fetched events
