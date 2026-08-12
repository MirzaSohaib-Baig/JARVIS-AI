"""
News & tech trends tool using RSS, HackerNews, and DuckDuckGo Search (Keyless).
"""
import feedparser
import requests
from ddgs import DDGS
from config.settings import settings


def _extract_image(entry) -> str:
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
    """
    Search world/tech news via DuckDuckGo (Keyless real-time news search).
    Replaces NewsAPI.
    """
    results = []
    with DDGS() as ddgs:
        ddg_news = list(ddgs.news(query, max_results=limit))
        for article in ddg_news:
            results.append({
                "title": article.get("title") or "Untitled",
                "link": article.get("url") or "",
                "summary": article.get("body") or "",
                "image": article.get("image") or "",
                "source_name": article.get("source") or "DuckDuckGo News",
            })
    return results


# Tool definitions remain identical for Groq / Orchestrator compatibility
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
            "description": "Get what's currently trending among developers/tech (Hacker News top stories).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_world_news",
            "description": "Search world news for a specific named topic, person, or event using keyless DuckDuckGo search.",
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

TOOL_FUNCTIONS = {
    "get_world_news": get_world_news,
    "get_tech_news": get_tech_news,
    "get_hacker_news_trends": get_hacker_news_trends,
    "search_world_news": search_world_news,
}