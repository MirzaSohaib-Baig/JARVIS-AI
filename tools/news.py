"""
News & tech trends tool.
get_world_news / get_tech_news / get_hacker_news_trends use free, keyless
sources (RSS + Hacker News's public API). search_world_news uses NewsAPI.org's
free tier, since it needs real structured search results (headline + image +
summary) rather than headline scraping — BBC's own search page is a
JavaScript-rendered React app, not scrapable with plain requests, and would
need a Playwright/Chromium dependency plus selectors that break every time
BBC redesigns their site. NewsAPI.org gives the same data as a stable,
documented JSON contract instead.
"""
# from urllib.parse import quote_plus

import feedparser
import requests

from config.settings import settings


def _extract_image(entry) -> str:
    """
    RSS feeds carry article images in a few different, inconsistently-used
    places depending on the publisher. This tries the common ones in order
    and just returns "" if none are present — the frontend already handles a
    missing image gracefully, so this is best-effort, not guaranteed.
    """
    media_thumbnail = entry.get("media_thumbnail")
    if media_thumbnail:
        return media_thumbnail[0].get("url", "")

    media_content = entry.get("media_content")
    if media_content:
        return media_content[0].get("url", "")

    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            return link.get("href", "")

    return ""


def get_world_news(limit: int = 5) -> list[dict]:
    """Latest world news headlines."""
    feed = feedparser.parse(settings.RSS_FEEDS["world"])
    return [
        {
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", ""),
            "image": _extract_image(entry),
        }
        for entry in feed.entries[:limit]
    ]


def get_tech_news(limit: int = 5) -> list[dict]:
    """Latest tech news headlines from TechCrunch."""
    feed = feedparser.parse(settings.RSS_FEEDS["tech"])
    return [
        {
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", ""),
            "image": _extract_image(entry),
        }
        for entry in feed.entries[:limit]
    ]


def get_hacker_news_trends(limit: int = 5) -> list[dict]:
    """Top trending stories on Hacker News right now (good proxy for tech/dev trends)."""
    ids = requests.get(settings.HN_TOP_STORIES_URL, timeout=10).json()[:limit]
    stories = []
    for story_id in ids:
        item = requests.get(settings.HN_ITEM_URL.format(story_id), timeout=10).json()
        stories.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "score": item.get("score"),
            }
        )
    return stories


def search_world_news(query: str, limit: int = 6) -> list[dict]:
    """Search world news for a specific topic, person, or event — use this
    instead of get_world_news when the user names something specific they
    want to search for, rather than just wanting general headlines. Returns
    real individual search results (not just a link to a search page), each
    with a headline, summary, and image where available."""
    if not settings.NEWSAPI_KEY:
        raise RuntimeError(
            "NEWSAPI_KEY isn't set. Get a free key at https://newsapi.org/register "
            "and add it to your .env file."
        )

    response = requests.get(
        settings.NEWSAPI_SEARCH_URL,
        params={
            "q": query,
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": limit,
            "apiKey": settings.NEWSAPI_KEY,
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI error: {data.get('message', 'unknown error')}")

    return [
        {
            "title": article.get("title") or "Untitled",
            "link": article.get("url") or "",
            "summary": article.get("description") or "",
            "image": article.get("urlToImage") or "",
            "source_name": (article.get("source") or {}).get("name") or "",
        }
        for article in data.get("articles", [])
    ]


# --- Tool schema for the LLM (Groq function-calling format) ---
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_world_news",
            "description": "Get the latest world news headlines.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tech_news",
            "description": "Get the latest technology news and tech industry updates.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hacker_news_trends",
            "description": "Get what's currently trending among developers/tech (Hacker News top stories). Use this for 'new trends' or 'updated tech stack' style questions.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_world_news",
            "description": "Search world news for a specific named topic, person, or event (e.g. 'search news about the election', 'find news on SpaceX'). Returns real individual search results with images, not just a link to a search page. Use this instead of get_world_news whenever the user names something specific.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The topic, person, or event to search for"},
                },
                "required": ["query"],
            },
        },
    },
]

# Maps function name -> actual python function, used by the orchestrator
TOOL_FUNCTIONS = {
    "get_world_news": get_world_news,
    "get_tech_news": get_tech_news,
    "get_hacker_news_trends": get_hacker_news_trends,
    "search_world_news": search_world_news,
}