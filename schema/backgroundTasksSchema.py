from pydantic import BaseModel

class BackgroundTaskRequest(BaseModel):
    type: str
    query: str
    interval_hours: int = 6