from os import getenv

from dotenv import load_dotenv

load_dotenv()

class Settings:

    # Required by OpenRouter
    OPENROUTER_API_KEY = getenv("LLM_API_KEY")
    MODEL = getenv("LLM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
    BASE_URL = getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    # meta-llama/llama-3.3-70b-instruct:free tacked on as a third fallback — it's
    # the most established, longest-running free model on OpenRouter, so it's a
    # good last resort if both primary picks are rate-limited at the same time.
    FALLBACK_MODELS = getenv(
        "LLM_FALLBACK_MODELS",
        "poolside/laguna-m.1:free,cohere/north-mini-code:free,meta-llama/llama-3.3-70b-instruct:free",
    ).split(",")

    # Optional but recommended by OpenRouter for app-attribution/analytics on
    # their dashboard — harmless to leave as-is for local personal use.
    SITE_URL = getenv("SITE_URL", "http://127.0.0.1:8000")
    SITE_NAME = getenv("SITE_NAME", "JARVIS")
    SCOPES = [
    #// Gmail API scopes
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",

    #// Calendar API scopes
    "https://www.googleapis.com/auth/calendar.events",

    #// YouTube API scopes
    "https://www.googleapis.com/auth/youtube.readonly",
]

    # Gmail & calendar setup instructions: https://developers.google.com/gmail/api/quickstart/python
    TOKEN_PATH = getenv("GOOGLE_TOKEN_PATH", "secrets/token.json")
    CREDENTIALS_PATH = getenv("GOOGLE_CREDENTIALS_PATH", "secrets/credentials.json")
    DEFAULT_TIMEZONE = (getenv("JARVIS_TIMEZONE", "UTC"))

    # News sources for the news tool.
    RSS_FEEDS = {
        "world": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "tech": "https://techcrunch.com/feed/",
    }

    HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
    HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

    NEWSAPI_SEARCH_URL = "https://newsapi.org/v2/everything"
    NEWSAPI_KEY = getenv("NEWSAPI_KEY")

    SYSTEM_PROMPT = """You are a personal assistant in the style of JARVIS from Iron Man:
                    concise, capable, and a little dry-witted. You have tools for news/tech trends,
                    email, and (soon) home automation and phone control. Use a tool whenever the
                    user's request needs live data or an action — don't guess at news or send
                    emails from memory. Keep replies short and conversational, this is a chat, not
                    a report.

                    If a tool result contains an error, relay the SPECIFIC technical detail (the
                    file path, error type, or status code mentioned) rather than a generic
                    statement like "credentials aren't set up" — the person debugging this needs
                    the actual cause, not a softened paraphrase.
                    
                    When the user refers to a calendar event by description rather than by ID
                    (e.g. "cancel my meeting with Sarah", "move tomorrow's standup"), look it up
                    yourself with get_my_events/get_upcoming_events and act on the match directly
                    — never ask the person to find and paste an event ID themselves, that's your
                    job. If more than one event plausibly matches (same title, same day, or
                    otherwise ambiguous), do NOT guess which one — list the matching events with
                    enough distinguishing detail (exact time, who else is on it) and ask which
                    one they mean before editing or deleting anything. Acting on the wrong event
                    by guessing is worse than asking one clarifying question."""

settings = Settings()