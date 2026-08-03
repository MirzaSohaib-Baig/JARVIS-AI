"""
YouTube tool. Auth is handled by auth/google_auth.py (shared with gmail_tool
and calendar_tool) — one consent screen covers all three.

Unlike Instagram/X, YouTube's Data API genuinely gives you your real
subscription feed (recent uploads from channels you follow), and its
official iframe embed is what makes inline video playback (the popup
window) both possible and fully within YouTube's terms of use — no
scraping, no unofficial embed tricks.
"""

from auth.google_auth import get_youtube_service

# Capped to limit API quota usage — each subscribed channel costs a
# separate quota-consuming call to list its recent uploads, so this isn't
# "free" in the API-quota sense even though it costs no money.
MAX_CHANNELS_TO_CHECK = 10


def get_subscription_feed(max_results: int = 8) -> list[dict]:
    """Recent videos from channels the user is subscribed to on YouTube —
    their actual personal feed, not search results."""
    yt = get_youtube_service()

    subs = (
        yt.subscriptions()
        .list(part="snippet", mine=True, maxResults=MAX_CHANNELS_TO_CHECK, order="alphabetical")
        .execute()
    )
    channel_ids = [item["snippet"]["resourceId"]["channelId"] for item in subs.get("items", [])]

    videos = []
    for channel_id in channel_ids:
        try:
            activities = (
                yt.activities()
                .list(part="snippet,contentDetails", channelId=channel_id, maxResults=2)
                .execute()
            )
        except Exception:
            continue  # a single channel erroring (e.g. no public uploads) shouldn't kill the whole feed

        for item in activities.get("items", []):
            upload = item.get("contentDetails", {}).get("upload")
            if not upload:
                continue
            sn = item["snippet"]
            videos.append(
                {
                    "title": sn.get("title"),
                    "channel": sn.get("channelTitle"),
                    "video_id": upload["videoId"],
                    "thumbnail": sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "published": sn.get("publishedAt", ""),
                }
            )

    videos.sort(key=lambda v: v["published"], reverse=True)
    return videos[:max_results]


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_subscription_feed",
            "description": "Get recent videos from the user's YouTube subscriptions — their actual personal feed. Use this for 'what's new on YouTube' or similar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Maximum number of videos to return (default 8)."},
                },
                "required": [],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_subscription_feed": get_subscription_feed,
}