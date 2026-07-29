# JARVIS — Phase 1 (text brain + news + email)

This is the first working slice: a chat assistant (via Telegram) that can
answer questions, pull live news/tech trends, and send/read email — all on
free tiers. Fan control, router control, and phone control get added in later
phases once this is running.

## 1. Install dependencies

```bash
cd jarvis
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## 2. Get your free LLM API key (the brain)

**Recommended: OpenRouter** (https://openrouter.ai) — sign up with email or
Google, no phone verification. Go to "Keys" in the dashboard, create a key.
Copy `.env.example` to `.env` and paste it into `LLM_API_KEY`. The defaults
in `.env.example` are already set to OpenRouter's free Llama 3.3 70B.

**Alternative: Groq** (https://console.groq.com) — faster inference if
signup works for you (it has intermittent signup bugs unrelated to region —
worth a retry with a different login method if it fails). Swap in the Groq
lines that are commented out in `.env.example`.

Both — and Cerebras, also listed in `.env.example` — use the same
OpenAI-compatible API shape, so switching between them is a `.env` edit,
never a code change.

## 3. Create your Telegram bot (free, 2 minutes)

1. Open Telegram, message **@BotFather**.
2. Send `/newbot`, follow the prompts (pick any name/username).
3. BotFather gives you a token like `123456:ABC-DEF...` — put it in `.env` as `TELEGRAM_BOT_TOKEN`.

## 4. Test the brain without Telegram first

```bash
python orchestrator.py
```

Try asking: *"What's trending in tech right now?"* — it should call the
Hacker News tool and summarize real results, not make something up.

## 5. Gmail setup (only needed once you want email working)

1. Go to https://console.cloud.google.com, create a project.
2. Enable the **Gmail API**.
3. Go to "APIs & Services" -> "Credentials" -> "Create Credentials" -> "OAuth
   client ID" -> Application type: **Desktop app**.
4. Download the JSON file, rename it `credentials.json`, put it in this
   `jarvis/` folder.
5. First time you send an email through JARVIS, a browser window will open
   asking you to log into the Google account you want it to send as. After
   that it's saved in `token.json` and won't ask again.

## 6a. Run the Telegram bot

```bash
python telegram_bot.py
```

Now message your bot from your phone.

## 6b. Or run the browser HUD instead (or alongside it)

```bash
uvicorn server:app --reload --port 8000
```

Then open **http://localhost:8000** — this serves `jarvis-hud.html` and wires
its chat box to the same `handle_message()` brain as the Telegram bot. Type a
message and it'll actually hit your tools (news, email) and reply for real.

Both interfaces can run at the same time (different terminals) — they share
the exact same `orchestrator.py`, nothing conflicts.

This is JARVIS, running for free, on your laptop.

## What's next (later phases)

- **Voice**: add Whisper (speech-to-text) + Piper (text-to-speech) so you can
  talk to it instead of typing.
- **Home Assistant**: install it (Docker is easiest) on this laptop or a
  Raspberry Pi, add your Broadlink RM4 Pro, teach it your fan remote's codes.
  Then add a `home_assistant_tool.py` here following the exact same pattern
  as `news.py` — one function per action, registered in `TOOL_DEFINITIONS`.
- **Router control**: add a smart plug to Home Assistant on the router's
  power, control it the same way as the fan.
- **Android control**: install Tasker, set up an HTTP Shortcuts listener on
  your phone, add a `phone_tool.py` that POSTs to your phone's IP to trigger
  actions (open app, search YouTube, etc.).

Every new capability follows the same shape: a Python function + a tool
definition dict + registering it in `orchestrator.py`'s `TOOL_MODULES` list.
That's the whole extensibility model — the brain doesn't change.
