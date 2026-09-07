import json
import re
import traceback
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from openai import OpenAI
from tools import cv_matcher_tool, news, gmail_tool, calendar_tool, youtube_tool, system_tool, computer_settings_tool, screen_processor_tool
from config.settings import settings


client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url=settings.BASE_URL,
    default_headers={
        "HTTP-Referer": settings.SITE_URL,
        "X-OpenRouter-Title": settings.SITE_NAME,
    }
)

# Combine every tool module's definitions + functions into one registry.
TOOL_MODULES = [news, gmail_tool, calendar_tool, youtube_tool, system_tool, cv_matcher_tool, computer_settings_tool, screen_processor_tool]
ALL_TOOL_DEFINITIONS = [d for module in TOOL_MODULES for d in module.TOOL_DEFINITIONS]
ALL_TOOL_FUNCTIONS = {}
for module in TOOL_MODULES:
    ALL_TOOL_FUNCTIONS.update(module.TOOL_FUNCTIONS)

NEWS_TOOL_NAMES = set(news.TOOL_FUNCTIONS.keys())
NEWS_TOPIC_LABELS = {
    "get_world_news": "world headlines",
    "get_tech_news": "tech headlines",
    "get_hacker_news_trends": "trending Hacker News stories",
    "search_world_news": "search results",
}

YOUTUBE_TOOL_NAMES = set(youtube_tool.TOOL_FUNCTIONS.keys())

TEXT_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*<function=([\w\-]+)>\s*(\{.*?\})?\s*</function>\s*</tool_call>",
    re.DOTALL,
)


def _parse_text_tool_calls(content: str) -> list[dict]:
    """Extract {"name": ..., "arguments": {...}} dicts from text-based tool-call format."""
    calls = []
    for name, raw_args in TEXT_TOOL_CALL_RE.findall(content or ""):
        try:
            args = json.loads(raw_args) if raw_args and raw_args.strip() else {}
        except json.JSONDecodeError:
            args = {}
        calls.append({"name": name.strip(), "arguments": args})
    return calls


def _complete(messages: list[dict], session_id: str | None = None,
              use_tools: bool = False):
    """Thin wrapper around client.chat.completions.create()."""
    extra_body = {"models": settings.FALLBACK_MODELS}
    if session_id:
        extra_body["session_id"] = session_id

    kwargs = {
        "model": settings.MODEL,
        "messages": messages,
        "extra_body": extra_body,
    }
    if use_tools:
        kwargs["tools"] = ALL_TOOL_DEFINITIONS
        kwargs["tool_choice"] = "auto"

    return client.chat.completions.create(**kwargs)


def _normalize_news_item(tool_name: str, item: dict) -> dict:
    """Normalize news items to consistent card schema."""
    if tool_name == "get_hacker_news_trends":
        return {
            "title": item.get("title") or "Untitled",
            "source": "Hacker News",
            "content": item.get("content") or "",
            "body": f"{item.get('score', '?')} points",
            "url": item.get("url") or "",
            "image": item.get("image") or "",
        }
    if tool_name == "search_world_news":
        return {
            "title": item.get("title") or "Untitled",
            "source": "BBC Search",
            "content": item.get("content") or "",
            "body": item.get("summary") or "",
            "url": item.get("link") or "",
            "image": item.get("image") or "",
        }
    return {
        "title": item.get("title") or "Untitled",
        "source": "World" if tool_name == "get_world_news" else "Tech",
        "content": item.get("content") or "",
        "body": item.get("summary") or "",
        "url": item.get("link") or "",
        "image": item.get("image") or "",
    }


def _clean_youtube_for_model(tool_name: str, result) -> str:
    """
    Strip video IDs, embed URLs, and raw technical details from YouTube
    results before the model sees them. The model gets clean, human-readable
    text only — no 11-character IDs, no iframe URLs, no API internals.
    """
    if isinstance(result, list):
        if not result:
            return "No videos found."
        
        # Check if these are video cards (have "type": "video")
        if len(result) > 0 and isinstance(result[0], dict) and result[0].get("type") == "video":
            lines = []
            for i, item in enumerate(result[:10]):
                title = item.get("title", "Untitled")
                channel = item.get("channel", "")
                body = item.get("body", "")
                
                line = f"{i+1}. {title}"
                if channel:
                    line += f" — {channel}"
                if body:
                    line += f" ({body})"
                lines.append(line)
            return "\n".join(lines)
        
        return json.dumps(result, default=str)
    
    if isinstance(result, str):
        return result
    
    if isinstance(result, dict):
        if result.get("type") == "video":
            title = result.get("title", "Untitled")
            channel = result.get("channel", "")
            return f"Video: {title}" + (f" by {channel}" if channel else "")
        return json.dumps(result, default=str)
    
    return str(result)


def _run_tool(func_name: str, func_args: dict, cards: list[dict]) -> tuple:
    """
    Runs one tool call. Returns (raw_result, cleaned_for_model).

    - raw_result: the full, unmodified tool output
    - cleaned_for_model: sanitized version the LLM sees (no video IDs/URLs)
    
    IMPORTANT: Video cards (type="video") are added directly to the `cards` list
    so the frontend can open native video player windows.
    """
    func = ALL_TOOL_FUNCTIONS.get(func_name)
    if func is None:
        error_msg = f"Error: no such tool '{func_name}'"
        return error_msg, error_msg

    try:
        result = func(**func_args)

        # ── News tools → collect into cards list ─────────────────────────
        if func_name in NEWS_TOOL_NAMES and isinstance(result, list):
            for item in result:
                card = _normalize_news_item(func_name, item)
                cards.append(card)
            # Build what the model actually reads — full article content, not just headlines
            model_text = "\n\n".join(
                f"[{c['source']}] {c['title']}\n{c['content']}"
                for c in cards[-len(result):]
                if c.get("content")
            )
            cleaned = (
                f"Found {len(result)} results. Read this article content and summarise "
                f"the key facts — do NOT just list headlines:\n\n{model_text}"
            ) if model_text else f"Found {len(result)} results. They will be shown as cards."
            return result, cleaned

        # ── YouTube tools → add video cards directly to cards list ───────
        if func_name in YOUTUBE_TOOL_NAMES:
            if isinstance(result, list):
                for item in result:
                    if isinstance(item, dict) and item.get("type") == "video":
                        # ADD VIDEO CARD TO CARDS LIST — this is what the frontend needs!
                        cards.append(item)
                cleaned = _clean_youtube_for_model(func_name, result)
            elif isinstance(result, dict) and result.get("type") == "video":
                # ADD SINGLE VIDEO CARD TO CARDS LIST
                cards.append(result)
                cleaned = _clean_youtube_for_model(func_name, result)
            elif isinstance(result, str):
                cleaned = result
            else:
                cleaned = _clean_youtube_for_model(func_name, result)
            return result, cleaned

        # ── All other tools → pass through as-is ─────────────────────────
        cleaned = json.dumps(result, default=str) if not isinstance(result, str) else result
        return result, cleaned

    except Exception as e:
        print(f"\n[JARVIS] Tool '{func_name}' failed:")
        traceback.print_exc()
        print()
        error_msg = f"Error running {func_name}: {e}"
        return error_msg, error_msg


MAX_TOOL_ROUNDS = 4


def _run_tool_round(message, messages: list[dict], cards: list[dict],
                    called_tool_names: set[str]) -> bool:
    """
    Executes every tool call in one model response. YouTube results are
    CLEANED before being sent back to the model — no video IDs or embed
    URLs ever reach the LLM's context.
    
    Video cards are added to the `cards` list so the frontend receives them.
    """
    if message.tool_calls:
        messages.append(message)
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments or "{}")
            called_tool_names.add(func_name)

            raw_result, cleaned = _run_tool(func_name, func_args, cards)

            # Send CLEANED result to the model
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": func_name,
                "content": cleaned,
            })
        return True

    text_calls = _parse_text_tool_calls(message.content or "")
    if text_calls:
        messages.append({"role": "assistant", "content": "Looking that up now."})
        result_lines = []
        for call in text_calls:
            func_name = call["name"]
            called_tool_names.add(func_name)
            _, cleaned = _run_tool(func_name, call["arguments"], cards)
            result_lines.append(f"{func_name} result: {cleaned}")
        messages.append({
            "role": "system",
            "content": "Tool results:\n" + "\n".join(result_lines)
        })
        return True

    return False


def handle_message(user_message: str, history: list[dict] | None = None,
                   session_id: str | None = None) -> dict:
    """
    Takes a user message (+ optional prior conversation history), runs the
    tool-calling loop, and returns {"reply": str, "cards": list[dict]}.

    KEY DESIGN:
    - YouTube video IDs, embed URLs are NEVER exposed to the LLM
    - The model sees only clean text like "1. Bohemian Rhapsody — Queen"
    - Full video card data (with embed_url) is in `cards` for the frontend
    - The frontend checks `card.type === "video"` to open native player windows
    """
    now_local = datetime.now(tz=ZoneInfo(settings.DEFAULT_TIMEZONE))
    today = now_local.date()
    date_context = (
        f"Current date/time: {now_local.strftime('%A, %Y-%m-%d %H:%M')} ({settings.DEFAULT_TIMEZONE}).\n"
        f"Pre-computed relative dates — use these exact values verbatim, do not recompute them yourself:\n"
        f"  today = {today.isoformat()}\n"
        f"  tomorrow = {(today + timedelta(days=1)).isoformat()}\n"
        f"  yesterday = {(today - timedelta(days=1)).isoformat()}\n"
        f"  day after tomorrow = {(today + timedelta(days=2)).isoformat()}\n"
        f"For anything else relative ('next Friday', 'in 3 days'), compute it yourself "
        f"from the current date above — never guess or default to a placeholder date."
    )

    messages = [
        {"role": "system", "content": settings.SYSTEM_PROMPT},
        {"role": "system", "content": date_context}
    ]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # Single cards list — holds BOTH news cards AND video cards
    cards: list[dict] = []
    called_tool_names: set[str] = set()
    message = None

    for round_num in range(MAX_TOOL_ROUNDS):
        data = _complete(messages, session_id=session_id, use_tools=True)
        message = data.choices[0].message

        tools_ran = _run_tool_round(message, messages, cards, called_tool_names)
        if not tools_ran:
            # Model gave a plain answer — final reply
            return {"reply": message.content, "cards": cards}

        # Fast path: first round, only news tools called
        if round_num == 0 and cards and called_tool_names.issubset(NEWS_TOOL_NAMES):
            # labels = [NEWS_TOPIC_LABELS.get(name, name) for name in called_tool_names]
            # label_text = " and ".join(labels)
            # card_content = [card.get("content") for card in cards if card.get("content") is not None]
            # return {
            #     "reply": f"Here are the top {label_text}: {', '.join(card_content)}",
            #     "cards": cards,
            # }
            pass

    # Hit MAX_TOOL_ROUNDS — force final completion
    if cards:
        messages.append({
            "role": "system",
            "content": (
                "The results are being shown to the user as separate visual "
                "cards/windows. Give a brief one-sentence acknowledgement only — "
                "do not list or summarize individual items in text."
            ),
        })

    final_data = _complete(messages, session_id=session_id, use_tools=False)
    return {"reply": final_data.choices[0].message.content, "cards": cards}


if __name__ == "__main__":
    print("JARVIS (text mode). Ctrl+C to quit.\n")
    conversation: list[dict] = []
    while True:
        user_input = input("You: ")
        result = handle_message(user_input, conversation, session_id="cli-session")
        print(f"JARVIS: {result['reply']}\n")
        if result.get("cards"):
            for card in result["cards"]:
                card_type = card.get("type", "news")
                if card_type == "video":
                    print(f"  [▶ Video] {card['title']} — {card.get('channel', '')}")
                    print(f"    embed_url: {card.get('embed_url', 'N/A')}")
                else:
                    print(f"  [{card.get('source', '?')}] {card['title']}")
            print()
        conversation.append({"role": "user", "content": user_input})
        conversation.append({"role": "assistant", "content": result["reply"]})