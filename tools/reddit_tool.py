"""
Reddit tool. Needs a free "script" app registered at
https://www.reddit.com/prefs/apps (2-minute self-service signup, no review
process) — see .env.example for the four values this needs. This is
genuinely free for personal-scale read access like this, unlike X/Instagram.
"""

import time
import requests
from config.settings import settings

_token_cache = {"token": None, "expires_at": 0}


def _get_reddit_token() -> str:
    """Reddit's OAuth 'password' grant — intended specifically for a script
    accessing its own developer's account, which is exactly this use case.
    Token is cached in-process and only re-fetched once it's actually
    expired."""
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    if not all([settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET, settings.REDDIT_USERNAME, settings.REDDIT_PASSWORD]):
        raise RuntimeError(
            "Reddit credentials aren't set. Register a free 'script' app at "
            "https://www.reddit.com/prefs/apps and set REDDIT_CLIENT_ID, "
            "REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD in .env."
        )

    resp = requests.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET),
        data={"grant_type": "password", "username": settings.REDDIT_USERNAME, "password": settings.REDDIT_PASSWORD},
        headers={"User-Agent": settings.REDDIT_USER_AGENT},
        timeout=10,
    )
    resp.raise_for_status()
    token_data = resp.json()
    if "access_token" not in token_data:
        raise RuntimeError(f"Reddit auth failed: {token_data}")

    _token_cache["token"] = token_data["access_token"]
    _token_cache["expires_at"] = time.time() + token_data.get("expires_in", 3600) - 60
    return _token_cache["token"]


def get_reddit_feed(subreddit: str = "", limit: int = 8) -> list[dict]:
    """Trending posts from Reddit. Omit subreddit for the user's personal
    front page (their subscribed subreddits combined) — this is the closest
    match to 'what's circulating that isn't formal published news'. Pass a
    specific subreddit name to check just that one instead."""
    token = _get_reddit_token()
    headers = {"Authorization": f"bearer {token}", "User-Agent": settings.REDDIT_USER_AGENT}
    path = f"/r/{subreddit}/hot" if subreddit else "/hot"

    resp = requests.get(
        f"https://oauth.reddit.com{path}", headers=headers, params={"limit": limit}, timeout=10
    )
    resp.raise_for_status()
    posts = resp.json()["data"]["children"]

    output = []
    for post in posts:
        d = post["data"]
        is_video = bool(d.get("is_video"))
        video_url = None
        if is_video:
            video_url = d.get("media", {}).get("reddit_video", {}).get("fallback_url")

        thumb = d.get("thumbnail", "")
        output.append(
            {
                "title": d.get("title", "Untitled"),
                "subreddit": d.get("subreddit_name_prefixed", ""),
                "permalink": f"https://reddit.com{d.get('permalink', '')}",
                "thumbnail": thumb if thumb.startswith("http") else "",
                "score": d.get("score", 0),
                "is_video": is_video and bool(video_url),
                "video_url": video_url,
            }
        )
    return output


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_reddit_feed",
            "description": "Get trending Reddit posts — either the user's personal front page (subscribed subreddits) or a specific subreddit if named. Good for 'what's trending' or grassroots content that isn't formal published news.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subreddit": {"type": "string", "description": "A specific subreddit name (without r/), or omit for the personal front page."},
                    "limit": {"type": "integer", "description": "Number of posts to return (default 8)."},
                },
                "required": [],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_reddit_feed": get_reddit_feed,
}