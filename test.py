from config.settings import settings
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta

now_local = datetime.now(tz=ZoneInfo(settings.DEFAULT_TIMEZONE))
today = now_local.date()
date_context = (
        f"Current date/time: {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')} ({settings.DEFAULT_TIMEZONE}).\n"
        f"Pre-computed relative dates — use these exact values verbatim, do not recompute them yourself:\n"
        f"  today = {today.isoformat()}\n"
        f"  tomorrow = {(today + timedelta(days=1)).isoformat()}\n"
        f"  yesterday = {(today - timedelta(days=1)).isoformat()}\n"
        f"  day after tomorrow = {(today + timedelta(days=2)).isoformat()}\n"
        f"For anything else relative ('next Friday', 'in 3 days'), compute it yourself "
        f"from the current date above — never guess or default to a placeholder date."
    )

print(date_context)