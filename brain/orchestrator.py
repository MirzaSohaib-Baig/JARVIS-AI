"""
The orchestrator: sends the user's message to the LLM via the OpenAI SDK
(pointed at OpenRouter's OpenAI-compatible endpoint), lets the model decide
whether to call a tool (news, email, etc.), runs that tool, and feeds the
result back for a final reply.

This is the "brain" — as you add more tools (Home Assistant, Tasker, etc.)
you just register them here, nothing else changes.
"""

import json
import re
import traceback
from openai import OpenAI
from tools import news, gmail_tool, calendar_tool
from config.settings import settings


client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY,
    base_url=settings.BASE_URL,
    default_headers={
        "HTTP-Referer": settings.SITE_URL,
        "X-OpenRouter-Title": settings.SITE_NAME,
    }
    )

SYSTEM_PROMPT = """You are a personal assistant in the style of JARVIS from Iron Man:
concise, capable, and a little dry-witted. You have tools for news/tech trends,
email, and (soon) home automation and phone control. Use a tool whenever the
user's request needs live data or an action — don't guess at news or send
emails from memory. Keep replies short and conversational, this is a chat, not
a report."""

# Combine every tool module's definitions + functions into one registry.
# Add new tool modules here as you build them (calendar_tool, home_assistant_tool, etc.)
TOOL_MODULES = [news, gmail_tool, calendar_tool]
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

# Some free/open-weight models routed through OpenRouter don't reliably
# support the native structured "tool_calls" field — instead they emit the
# call as plain text inside the response content, e.g.:
#   <tool_call><function=get_tech_news>{}</function></tool_call>
# This regex catches that pattern so the orchestrator still works no matter
# which model in the fallback chain actually serves a given request.
TEXT_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*<function=([\w\-]+)>\s*(\{.*?\})?\s*</function>\s*</tool_call>",
    re.DOTALL,
)


def _parse_text_tool_calls(content: str) -> list[dict]:
    """Extract {"name": ..., "arguments": {...}} dicts from the text-based
    tool-call format described above. Returns [] if none are found."""
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
    """
    Thin wrapper around client.chat.completions.create() that adds the
    OpenRouter-specific fallback chain and session_id via extra_body (since
    neither is a standard OpenAI API parameter).
    """
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
    """Different news tools return slightly different shapes — normalize to
    one card schema the frontend can render consistently."""
    if tool_name == "get_hacker_news_trends":
        return {
            "title": item.get("title") or "Untitled",
            "source": "Hacker News",
            "body": f"{item.get('score', '?')} points",
            "url": item.get("url") or "",
            "image": item.get("image") or "",
        }
    if tool_name == "search_world_news":
        return {
            "title": item.get("title") or "Untitled",
            "source": "BBC Search",
            "body": item.get("summary") or "",
            "url": item.get("link") or "",
            "image": item.get("image") or "",
        }
    return {
        "title": item.get("title") or "Untitled",
        "source": "World" if tool_name == "get_world_news" else "Tech",
        "body": item.get("summary") or "",
        "url": item.get("link") or "",
        "image": item.get("image") or "",
    }


def _run_tool(func_name: str, func_args: dict, news_cards: list[dict]):
    """Runs one tool call, appending to news_cards in place if it was a news
    tool. Returns the (JSON-serializable) result, or an error string."""
    func = ALL_TOOL_FUNCTIONS.get(func_name)
    if func is None:
        return f"Error: no such tool '{func_name}'"
    try:
        result = func(**func_args)
        if func_name in NEWS_TOOL_NAMES and isinstance(result, list):
            news_cards.extend(_normalize_news_item(func_name, item) for item in result)
        return result
    except Exception as e:
        print(f"\n[JARVIS] Tool '{func_name}' failed:")
        traceback.print_exc()
        print()
        return f"Error running {func_name}: {e}"


def handle_message(user_message: str, history: list[dict] | None = None,
                    session_id: str | None = None) -> dict:
    """
    Takes a user message (+ optional prior conversation history), runs the
    tool-calling loop, and returns {"reply": str, "cards": list[dict]}.

    "cards" is only populated when a news tool was called — it's the
    structured article data (title/source/body/url per item) so a frontend
    can render actual visual panels/windows instead of dumping headlines as
    a wall of text. Callers that only want text (like telegram_bot.py) just
    read result["reply"].

    session_id groups related requests together on OpenRouter's side (e.g.
    per browser tab / per Telegram chat) — pass the same value across a
    conversation if you want that grouping; safe to omit entirely.
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    data = _complete(messages, session_id=session_id, use_tools=True)
    message = data.choices[0].message
    news_cards: list[dict] = []
    called_tool_names: set[str] = set()

    if message.tool_calls:
        # Normal path: the model used real structured tool calling.
        messages.append(message)
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments or "{}")
            called_tool_names.add(func_name)
            result = _run_tool(func_name, func_args, news_cards)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": func_name,
                    "content": json.dumps(result, default=str),
                }
            )
    else:
        # Fallback path: check whether the model tried to call a tool using
        # the text-based <tool_call> format instead of the structured API.
        text_calls = _parse_text_tool_calls(message.content or "")
        if not text_calls:
            return {"reply": message.content, "cards": []}

        # Don't echo the raw <tool_call> text back into history — replace it
        # with a clean note, then feed tool results in as plain context
        # (no tool_call_id thread to maintain here since none was ever created).
        messages.append({"role": "assistant", "content": "Looking that up now."})
        result_lines = []
        for call in text_calls:
            called_tool_names.add(call["name"])
            result = _run_tool(call["name"], call["arguments"], news_cards)
            result_lines.append(f"{call['name']} result: {json.dumps(result, default=str)}")
        messages.append({"role": "system", "content": "Tool results:\n" + "\n".join(result_lines)})

    # Speed optimization: if this turn ONLY called news tools, skip the
    # second model round-trip entirely and build the spoken acknowledgment
    # locally. The two model calls (pick a tool -> narrate the result) were
    # each costing a full network + inference round-trip; for a pure news
    # request the narration adds no information the cards/windows don't
    # already carry, so cutting it roughly halves the time until windows
    # actually open. Mixed turns (news + email, etc.) still go through the
    # real second call below, since those genuinely need the model to
    # describe the non-news action it took.
    if news_cards and called_tool_names and called_tool_names.issubset(NEWS_TOOL_NAMES):
        labels = [NEWS_TOPIC_LABELS.get(name, name) for name in called_tool_names]
        label_text = " and ".join(labels)
        reply = f"Pulled {len(news_cards)} {label_text} — opening them now."
        return {"reply": reply, "cards": news_cards}

    # Ask for a short spoken-style reply — the articles themselves are
    # shown as cards/windows, so the text reply shouldn't re-list them.
    if news_cards:
        messages.append(
            {
                "role": "system",
                "content": "The news results are being shown to the user as separate visual cards/windows. Give a brief one-sentence spoken acknowledgement only — do not list or summarize the individual headlines in text.",
            }
        )

    final_data = _complete(messages, session_id=session_id, use_tools=False)
    return {"reply": final_data.choices[0].message.content, "cards": news_cards}


if __name__ == "__main__":
    # Quick command-line test, no Telegram or browser needed
    print("JARVIS (text mode). Ctrl+C to quit.\n")
    conversation: list[dict] = []
    while True:
        user_input = input("You: ")
        result = handle_message(user_input, conversation, session_id="cli-session")
        print(f"JARVIS: {result['reply']}\n")
        if result["cards"]:
            for card in result["cards"]:
                print(f"  [{card['source']}] {card['title']} -> {card['url']}")
            print()
        conversation.append({"role": "user", "content": user_input})
        conversation.append({"role": "assistant", "content": result["reply"]})