"""
YouTube tool. Auth via auth/google_auth.py (shared with gmail/calendar) —
uses the official YouTube Data API throughout, no HTML scraping. Scraping
YouTube's pages (search results, trending, video metadata) is fragile —
their page structure changes without notice, silently breaking regex-based
extraction — and against YouTube's Terms of Service. The Data API already
covers all of this officially, and you already have OAuth access to it.

Videos never open themselves from in here. Every function just returns data
shaped as a "video" card ({"type": "video", "embed_url": ...}) — opening the
actual native popup window is native_ui.py's ContentWindowManager's job,
same as every other tool in this project. A tool that tries to pop its own
window (like the old webbrowser.open() version did) breaks that separation
and, worse, opens your system's actual browser instead of a real native
window — which is the opposite of what you're trying to build.
"""

from typing import Optional

from auth.google_auth import get_youtube_service

MAX_CHANNELS_TO_CHECK = 10


def _video_card(video_id: str, title: str, channel: str, thumbnail: str = "", body: str = "") -> dict:
    """Common shape for a single video result. 'type': 'video' is what
    tells the UI layer to open this as a native embedded player instead of
    treating it like a regular article window."""
    return {
        "title": title,
        "channel": channel,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "embed_url": f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1",
        "image": thumbnail,
        "type": "video",
        "body": body,
    }


def get_subscription_feed(max_results: int = 8) -> list[dict]:
    """Recent videos from channels the user is subscribed to — their actual
    personal feed, not search results."""
    yt = get_youtube_service()
    subs = (
        yt.subscriptions()
        .list(part="snippet", mine=True, maxResults=MAX_CHANNELS_TO_CHECK, order="alphabetical")
        .execute()
    )
    channel_ids = [item["snippet"]["resourceId"]["channelId"] for item in subs.get("items", [])]

    dated: list[tuple[str, dict]] = []
    for channel_id in channel_ids:
        try:
            activities = (
                yt.activities()
                .list(part="snippet,contentDetails", channelId=channel_id, maxResults=2)
                .execute()
            )
        except Exception:
            continue  # one channel erroring shouldn't kill the whole feed

        for item in activities.get("items", []):
            upload = item.get("contentDetails", {}).get("upload")
            if not upload:
                continue
            sn = item["snippet"]
            card = _video_card(
                upload["videoId"],
                sn.get("title", ""),
                sn.get("channelTitle", ""),
                sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
            )
            dated.append((sn.get("publishedAt", ""), card))

    dated.sort(key=lambda pair: pair[0], reverse=True)
    return [card for _, card in dated[:max_results]]


def search_and_play_youtube(query: str) -> list[dict]:
    """Search YouTube and return the best match as a single video card,
    ready to open in the native popup player. Use this when the user says
    'play X on YouTube' or 'show me a video about X'."""
    yt = get_youtube_service()
    search = (
        yt.search()
        .list(part="snippet", q=query, type="video", maxResults=1)
        .execute()
    )
    items = search.get("items", [])
    if not items:
        return []

    item = items[0]
    video_id = item["id"]["videoId"]
    sn = item["snippet"]
    return [
        _video_card(
            video_id,
            sn.get("title", ""),
            sn.get("channelTitle", ""),
            sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
        )
    ]


def get_trending_videos(region: str = "US", max_results: int = 8) -> list[dict]:
    """Trending videos for a region, via the Data API's official
    chart=mostPopular parameter — not scraped from the trending page."""
    yt = get_youtube_service()
    resp = (
        yt.videos()
        .list(part="snippet,statistics", chart="mostPopular", regionCode=region.upper(), maxResults=max_results)
        .execute()
    )
    out = []
    for item in resp.get("items", []):
        sn = item["snippet"]
        views = item.get("statistics", {}).get("viewCount")
        body = f"{int(views):,} views" if views else ""
        out.append(
            _video_card(
                item["id"],
                sn.get("title", ""),
                sn.get("channelTitle", ""),
                sn.get("thumbnails", {}).get("medium", {}).get("url", ""),
                body,
            )
        )
    return out


def get_transcript(video_id: str) -> Optional[str]:
    """Video transcript/subtitles, if available. Uses the youtube-transcript-api
    package (community-maintained, not an official Google endpoint — there
    isn't one for reading a transcript on a video you don't own, so this is
    the standard accepted approach for this specific need)."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        lang_priority = ["en", "tr", "de", "fr", "es"]
        transcript = None
        try:
            transcript = transcript_list.find_manually_created_transcript(lang_priority)
        except Exception:
            try:
                transcript = transcript_list.find_generated_transcript(lang_priority)
            except Exception:
                transcript = next(iter(transcript_list), None)
        if transcript is None:
            return None
        fetched = transcript.fetch()
        return " ".join(entry["text"] for entry in fetched)
    except Exception as e:
        print(f"[JARVIS] Transcript fetch failed for {video_id}: {e}")
        return None


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_subscription_feed",
            "description": "Get recent videos from the user's YouTube subscriptions — their actual personal feed. Use for 'what's new on YouTube' or 'show my feed'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Maximum number of videos to return (default 8)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_and_play_youtube",
            "description": "Search YouTube for a video and return the best match, ready to open in the native player. Use when the user says 'play X on YouTube' or 'show me a video about X'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for on YouTube."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trending_videos",
            "description": "Get trending/popular YouTube videos for a region. Use for 'what's trending on YouTube' or 'popular videos'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {"type": "string", "description": "Two-letter country code (default US)."},
                    "max_results": {"type": "integer", "description": "Maximum results (default 8)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transcript",
            "description": "Get the transcript/subtitles of a specific YouTube video, e.g. to summarize it. Requires the video ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "video_id": {"type": "string", "description": "The 11-character YouTube video ID."},
                },
                "required": ["video_id"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_subscription_feed": get_subscription_feed,
    "search_and_play_youtube": search_and_play_youtube,
    "get_trending_videos": get_trending_videos,
    "get_transcript": get_transcript,
}