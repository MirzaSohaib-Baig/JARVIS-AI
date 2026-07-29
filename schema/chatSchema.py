from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    session_id: str | None = None

class ChatResponse(BaseModel):
    reply: str
    history: list[dict]
    cards: list[dict] = []