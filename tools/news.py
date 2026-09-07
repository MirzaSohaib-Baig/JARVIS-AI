"""
News tool — upgraded with real article content fetching (Gap 1).

The key difference from the previous version: search_world_news now fetches
the actual text of each article and returns it as 'content' alongside the
headline and URL. The orchestrator passes this content to the model as
context, so JARVIS can say "the article says Pakistan's inflation dropped
from 12% to 7% according to the State Bank report" rather than just
"here's a headline about Pakistan's inflation."

That's the behaviour from Mark-LII that felt like it was "pinpointing" to
exact news — it was reading the pages, not just passing URLs.

Content fetching is intentionally defensive:
- 5-second timeout per article (news summaries aren't worth hanging on)
- Strips scripts/styles/nav/footer before extracting text
- Truncates at MAX_ARTICLE_CHARS so a single long article doesn't blow
  the model's context window
- Falls back to the DuckDuckGo 'body' snippet if a fetch fails — still
  better than a headline alone
- Never raises on a fetch error — a failed article fetch is silently
  swallowed; the caller still gets the other results

Your existing TOOL_DEFINITIONS and TOOL_FUNCTIONS are unchanged in shape —
the only difference is what's inside the dicts that get returned.
"""

import re
import feedparser
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from config.settings import settings

MAX_ARTICLE_CHARS = 2000   # per article — enough for a solid paragraph-level
                            # summary, not so much that 5 articles overflow the
                            # context window
FETCH_TIMEOUT = 5           # seconds — fail fast, don't hang the whole response
FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def _fetch_article_text(url: str) -> str:
    """
    Fetch and extract readable text from a URL. Returns "" on any failure —
    callers fall back to the snippet they already have.
    """
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        resp = requests.get(url, timeout=FETCH_TIMEOUT, headers=FETCH_HEADERS)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove boilerplate that's never article content
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "noscript", "iframe", "ads"]):
            tag.decompose()

        # Prefer <article> body; fall back to <main>; fall back to <body>
        container = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", {"id": re.compile(r"content|article|story", re.I)})
            or soup.body
        )
        if container is None:
            return ""

        text = " ".join(container.get_text(separator=" ").split())
        return text[:MAX_ARTICLE_CHARS]
    except Exception:
        return ""


def _enrich(item: dict) -> dict:
    """
    Add fetched article content to a news item dict. If fetching fails or
    returns nothing, falls back to whatever 'summary' was already there
    (the RSS excerpt or DuckDuckGo snippet) — still better than a headline.
    """
    url = item.get("link") or item.get("url") or ""
    content = _fetch_article_text(url)
    item["content"] = content if content else item.get("summary", "")
    return item


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


def get_world_news(limit: int = 4) -> list[dict]:
    feed = feedparser.parse(settings.RSS_FEEDS["world"])
    return [
        _enrich({
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", ""),
            "image": _extract_image(entry),
        })
        for entry in feed.entries[:limit]
    ]


def get_tech_news(limit: int = 4) -> list[dict]:
    feed = feedparser.parse(settings.RSS_FEEDS["tech"])
    return [
        _enrich({
            "title": entry.title,
            "link": entry.link,
            "summary": entry.get("summary", ""),
            "image": _extract_image(entry),
        })
        for entry in feed.entries[:limit]
    ]


def get_hacker_news_trends(limit: int = 4) -> list[dict]:
    ids = requests.get(settings.HN_TOP_STORIES_URL, timeout=10).json()[:limit]
    stories = []
    for story_id in ids:
        item = requests.get(settings.HN_ITEM_URL.format(story_id), timeout=10).json()
        url = item.get("url") or ""
        content = _fetch_article_text(url)
        stories.append({
            "title": item.get("title"),
            "url": url,
            "score": item.get("score"),
            "content": content,  # HN items have no built-in summary, so content matters more here
        })
    return stories


def search_world_news(query: str, limit: int = 4) -> list[dict]:
    """
    Search world/tech news via DuckDuckGo then fetch the actual article
    content so JARVIS can summarise what it read, not just headlines.
    """
    results = []
    with DDGS() as ddgs:
        ddg_news = list(ddgs.news(query, max_results=limit))
        for article in ddg_news:
            url = article.get("url") or ""
            snippet = article.get("body") or ""
            content = _fetch_article_text(url)
            results.append({
                "title": article.get("title") or "Untitled",
                "link": url,
                "summary": snippet,
                "content": content if content else snippet,
                "image": article.get("image") or "",
                "source_name": article.get("source") or "DuckDuckGo News",
            })
    return results


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_world_news",
            "description": "Get the latest world news headlines with article content for summarisation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tech_news",
            "description": "Get the latest technology news and tech industry updates with article content.",
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
            "description": (
                "Search world news for a specific named topic, person, or event. "
                "Returns actual article content so JARVIS can give a detailed summary, "
                "not just headlines. Use this when the user names something specific."
            ),
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