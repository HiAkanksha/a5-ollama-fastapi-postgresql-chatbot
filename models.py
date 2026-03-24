"""Pydantic schemas for validating FastAPI request bodies and shaping JSON responses."""

from pydantic import BaseModel


# Carries the JSON body when a client calls POST /user to register a user id.
class UserCreate(BaseModel):
    user_id: int


# Carries the JSON body when a client calls POST /session to start a chat session.
class SessionCreate(BaseModel):
    user_id: int
    session_id: str


# Carries the JSON body when a client sends a chat message via POST /chat.
class ChatRequest(BaseModel):
    user_id: int
    session_id: str
    message: str


# Shape of the JSON returned by POST /chat after the assistant replies.
class ChatResponse(BaseModel):
    reply: str
    session_id: str
    user_id: int


# One chat line (user or assistant) used inside history payloads.
class MessageItem(BaseModel):
    role: str
    content: str


# Shape of the JSON returned by GET /history listing past messages in order.
class HistoryResponse(BaseModel):
    messages: list[MessageItem]
