import datetime
from auth.google_auth import get_calendar_service
from zoneinfo import ZoneInfo
from config.settings import settings

# event_id = None  # Global variable to store the event ID for editing/deleting
# print(f"[JARVIS] calendar_tool using timezone: {settings.DEFAULT_TIMEZONE}"
#       + ("  (JARVIS_TIMEZONE not set in .env — falling back to UTC)" if settings.DEFAULT_TIMEZONE == "UTC" else ""))

def _event_to_dict(event: dict) -> dict:
    """Common shape for returning an event — includes the event ID, since
    the model needs it to reference this event in a later edit/delete call."""
    return {
        "id": event.get("id"),
        "summary": event.get("summary"),
        "start": event["start"].get("dateTime", event["start"].get("date")),
        "link": event.get("htmlLink"),
    }

def create_event(summary: str, start_time: str, end_time: str, time_zone: str = None) -> dict:
    """Create a new calendar event."""
    service = get_calendar_service()
    tz = time_zone or settings.DEFAULT_TIMEZONE
    event = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": tz},
        "end": {"dateTime": end_time, "timeZone": tz},
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 24 * 60},  # 24 hours before
                {"method": "popup", "minutes": 10},  # 10 minutes before
            ],
        },
    }
    created_event = service.events().insert(calendarId="primary", body=event).execute()
    # global event_id
    # event_id = created_event.get("id")  # Store the event ID for later reference
    # print(f"Event created with ID: {event_id}")
    return _event_to_dict(created_event)

def get_events_on_date(date: str) -> list[dict]:
    service = get_calendar_service()
    try:
        tzinfo = ZoneInfo(settings.DEFAULT_TIMEZONE)
    except Exception as e:
        tzinfo = datetime.timezone.utc

    day = datetime.date.fromisoformat(date)
    start_of_day = datetime.datetime.combine(day, datetime.time.min, tzinfo=tzinfo)
    end_of_day = datetime.datetime.combine(day, datetime.time.max, tzinfo=tzinfo)

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])
    return [_event_to_dict(event) for event in events]

def get_upcoming_events(max_results: int = 5) -> list[dict]:
    """Get the user's upcoming calendar events."""
    service = get_calendar_service()
    now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])

    if not events:
        print("No upcoming events found.")
        return
    
    return [_event_to_dict(event) for event in events]

def get_my_events(max_results: int = 5) -> list[dict]:
    """Get the user's own calendar events (events they created)."""
    service = get_calendar_service()
    limit = int(max_results) if max_results else 5
    fetch_limit = max(limit * 4, 25)  # Fetch more to filter later, but cap at 25
    now = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=fetch_limit,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])
    mine = [event for event in events if event.get("creator", {}).get("self")]

    if not mine:
        print("No events found.")
        return
    
    return [_event_to_dict(event) for event in mine[:limit]]  # Return only the requested number of events

def edit_my_event(event_id: str, new_summary: str) -> dict:
    """Edit the summary of an event that the user created."""
    service = get_calendar_service()
    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    event["summary"] = new_summary
    updated_event = service.events().update(calendarId="primary", eventId=event_id, body=event).execute()
    return _event_to_dict(updated_event)

def delete_my_event(event_id: str) -> None:
    """Delete an event that the user created."""
    service = get_calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    return f"Event with ID {event_id} has been deleted."


def get_event_details(event_id: str) -> dict:
    """Get details about a specific event."""
    service = get_calendar_service()
    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    return event

#// LLM tool definitions for calendar functions
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_events_on_date",
            "description": "Get all events on one specific date, including past dates. Use this whenever the user names a specific day — 'yesterday', 'last Tuesday', 'August 10th' — since the other calendar lookup tools can only see upcoming events, never past ones.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "The date to check, as 'YYYY-MM-DD'."},
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_events",
            "description": "Get the user's upcoming calendar events.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to retrieve (default is 5).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_events",
            "description": "Get the user's own calendar events (events they created, not ones others invited them to).",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of events to retrieve (default is 5).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_my_event",
            "description": "Edit the summary of an existing event. Provide the event ID and the new summary text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The ID of the event to edit."},
                    "new_summary": {"type": "string", "description": "The new summary text for the event."},
                },
                "required": ["event_id", "new_summary"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_my_event",
            "description": "Cancel/delete an event. Provide the event ID of the event to delete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The ID of the event to delete."},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_event_details",
            "description": "Get full details about a specific event. Provide the event ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "The ID of the event to retrieve details for."},
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "Schedule a new calendar event with a reminder. Use this whenever the user wants to schedule/book/set up a meeting or event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Title of the event."},
                    "start_time": {"type": "string", "description": "ISO 8601 start time, e.g. '2026-08-15T14:00:00'."},
                    "end_time": {"type": "string", "description": "ISO 8601 end time, e.g. '2026-08-15T15:00:00'."},
                    "time_zone": {"type": "string", "description": "IANA time zone, e.g. 'America/New_York'. Only pass this if the user names a specific timezone — otherwise omit it and the configured home timezone is used automatically."},
                },
                "required": ["summary", "start_time", "end_time"],
            },
        },
    },
]
 
TOOL_FUNCTIONS = {
    "get_events_on_date": get_events_on_date,
    "get_upcoming_events": get_upcoming_events,
    "get_my_events": get_my_events,
    "edit_my_event": edit_my_event,
    "delete_my_event": delete_my_event,
    "get_event_details": get_event_details,
    "create_event": create_event,
}
 