import datetime
from auth.google_auth import get_calendar_service
from config.settings import settings

# event_id = None  # Global variable to store the event ID for editing/deleting

def _event_to_dict(event: dict) -> dict:
    """Common shape for returning an event — includes the event ID, since
    the model needs it to reference this event in a later edit/delete call."""
    return {
        "id": event.get("id"),
        "summary": event.get("summary"),
        "start": event["start"].get("dateTime", event["start"].get("date")),
    }

def create_event(summary: str, start_time: str, end_time: str, time_zone: str = settings.DEFAULT_TIMEZONE) -> dict:
    """Create a new calendar event."""
    service = get_calendar_service()
    event = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": time_zone},
        "end": {"dateTime": end_time, "timeZone": time_zone},
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
    
    return [_event_to_dict(event) for event in mine]

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
            "name": "create_event",
            "description": "Create a new calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Event summary/title"},
                    "start_time": {"type": "string", "description": "Event start time in ISO format (e.g., '2023-09-01T10:00:00Z')"},
                    "end_time": {"type": "string", "description": "Event end time in ISO format (e.g., '2023-09-01T11:00:00Z')"},
                    "time_zone": {"type": "string", "description": "Time zone for the event (default is 'UTC')"},
                },
                "required": ["summary", "start_time", "end_time"],
            },
        }
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
            "description": "Get the user's own calendar events (events they created).",
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
            "description": (
                'Edit the summary of an event that the user created. '
                'Provide the event ID and the new summary text.'
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": 'The ID of the event to edit.'},
                    "new_summary": {"type": "string", 'description': 'The new summary text for the event.'},
                },
                'required': ['event_id', 'new_summary'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'delete_my_event',
            'description': (
                'Delete an event that the user created. '
                'Provide the event ID of the event to delete.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'event_id': {'type': 'string', 'description': 'The ID of the event to delete.'},
                },
                'required': ['event_id'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_event_details',
            'description': (
                'Get details about a specific event. '
                'Provide the event ID to retrieve its details.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'event_id': {'type': 'string', 'description': 'The ID of the event to retrieve details for.'},
                },
                'required': ['event_id'],
            },
        },
    },
]   

TOOL_FUNCTIONS = {
    "create_event": create_event,
    "get_upcoming_events": get_upcoming_events,
    "get_my_events": get_my_events,
    "edit_my_event": edit_my_event,
    "delete_my_event": delete_my_event,
    "get_event_details": get_event_details,
}