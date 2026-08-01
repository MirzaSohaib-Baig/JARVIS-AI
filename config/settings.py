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
]

    # Gmail & calendar setup instructions: https://developers.google.com/gmail/api/quickstart/python
    TOKEN_PATH = getenv("GOOGLE_TOKEN_PATH", "secrets/token.json")
    CREDENTIALS_PATH = getenv("GOOGLE_CREDENTIALS_PATH", "secrets/credentials.json")
    DEFAULT_TIMEZONE = getenv("JARVIS_TIMEZONE", "UTC")

    # News sources for the news tool.
    RSS_FEEDS = {
        "world": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "tech": "https://techcrunch.com/feed/",
    }

    HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
    HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

    NEWSAPI_SEARCH_URL = "https://newsapi.org/v2/everything"
    NEWSAPI_KEY = getenv("NEWSAPI_KEY")

settings = Settings()