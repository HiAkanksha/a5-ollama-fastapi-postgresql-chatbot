"""
FastAPI chatbot API: stores chats in PostgreSQL and generates replies with Ollama.
"""

import os
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from database import (
    create_session,
    create_tables,
    create_user,
    get_connection,
    get_history,
    save_message,
)
from models import ChatRequest, ChatResponse, HistoryResponse, MessageItem, SessionCreate, UserCreate

# Pull Ollama settings and DATABASE_URL companion vars from .env into os.environ.
load_dotenv()

# Model name Ollama will run (must match a model you have pulled locally).
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
# Base URL of the Ollama server, e.g. http://localhost:11434 — no trailing slash required below.
OLLAMA_URL = os.getenv("OLLAMA_URL")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: make sure DB tables exist before any requests are served.
    await create_tables()
    # Fail fast if Ollama env vars are missing so /chat does not die mysteriously later.
    if not OLLAMA_MODEL or not OLLAMA_URL:
        raise ValueError("OLLAMA_MODEL and OLLAMA_URL must be set in your .env file.")
    # Shared async HTTP client with a long timeout because local LLMs can take a while.
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        # Stash the client on app.state so route handlers can reuse one connection pool.
        app.state.http_client = client
        yield
    # Shutdown: AsyncClient context closes automatically here.


app = FastAPI(lifespan=lifespan)


"""
Registers a new user id in the database so they can create sessions and chat.
"""
@app.post("/user")
async def create_user_route(body: UserCreate):
    # Open a short-lived DB connection to see if this user_id is already taken.
    conn = await get_connection()
    try:
        # fetchrow returns a record if a row exists, or None if the user is new.
        existing = await conn.fetchrow(
            "SELECT user_id FROM users WHERE user_id = $1",
            body.user_id,
        )
    finally:
        # Return the connection to the server so we do not leak sockets.
        await conn.close()
    # If we found a row, the client must pick a different id or use the existing account.
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="User already exists. Use a different user_id or sign in as that user.",
        )
    # Safe to insert: create_user adds the row (no conflict expected after the check above).
    await create_user(body.user_id)
    # Tell the client registration succeeded and echo back the id they registered.
    return {"message": "User created", "user_id": body.user_id}


"""
Creates a new chat session tied to a user so messages can be grouped under session_id.
"""
@app.post("/session")
async def create_session_route(body: SessionCreate):
    # Persist the session row (user must already exist due to foreign key on sessions.user_id).
    await create_session(body.user_id, body.session_id)
    # Confirm creation and return the session identifier the client will send on /chat.
    return {"message": "Session created", "session_id": body.session_id}


"""
Sends the user's message to Ollama with full history, saves both sides, returns the assistant reply.
"""
@app.post("/chat", response_model=ChatResponse)
async def chat_route(body: ChatRequest):
    # Step 1: Load every prior message for this user+session (oldest first) from PostgreSQL.
    history = await get_history(body.user_id, body.session_id)
    # Step 2a: Ollama expects a list of {role, content} dicts; start with a fixed system instruction.
    messages_array: list[dict[str, str]] = [
        {"role": "system", "content": "You are a helpful assistant"},
    ]
    # Step 2b: Replay stored turns so the model remembers the conversation.
    for turn in history:
        messages_array.append({"role": turn["role"], "content": turn["content"]})
    # Step 2c: Append the brand-new user message from this request.
    messages_array.append({"role": "user", "content": body.message})
    # Build the JSON body Ollama's /api/chat endpoint expects (non-streaming).
    ollama_payload = {
        "model": OLLAMA_MODEL,
        "messages": messages_array,
        "stream": False,
    }
    # Normalize base URL so we always hit .../api/chat regardless of trailing slash in .env.
    base = OLLAMA_URL.rstrip("/")
    chat_url = f"{base}/api/chat"
    # Reuse the long-timeout client created in lifespan (120s limit for slow local models).
    client: httpx.AsyncClient = app.state.http_client
    try:
        # Step 3: POST to Ollama; await until the full reply is ready (no streaming).
        response = await client.post(chat_url, json=ollama_payload)
    except httpx.RequestError as exc:
        # Network errors (Ollama not running, wrong port, etc.).
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach Ollama at {OLLAMA_URL}: {exc}",
        ) from exc
    # Non-2xx means Ollama rejected the request; surface status and body for debugging.
    if response.status_code != httpx.codes.OK:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama returned {response.status_code}: {response.text}",
        )
    # Parse JSON once so we can read fields safely.
    data = response.json()
    try:
        # Step 4: Ollama puts the assistant text under message.content in the chat response.
        reply = data["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Unexpected response shape from Ollama (missing message.content).",
        ) from exc
    # Step 5: Persist what the human said so history stays complete for the next turn.
    await save_message(body.user_id, body.session_id, "user", body.message)
    # Step 6: Persist the model answer with role "assistant" for future context.
    await save_message(body.user_id, body.session_id, "assistant", reply)
    # Step 7: Respond to the API client with the reply and echo ids for correlation.
    return ChatResponse(reply=reply, session_id=body.session_id, user_id=body.user_id)


"""
Returns all stored messages for a session as a list of role/content objects.
"""
@app.get("/history/{user_id}/{session_id}", response_model=HistoryResponse)
async def history_route(user_id: int, session_id: str):
    # Same query /chat uses to build context, exposed read-only for clients.
    rows = await get_history(user_id, session_id)
    # Wrap plain dicts as Pydantic models so FastAPI validates the response shape.
    items = [MessageItem(role=r["role"], content=r["content"]) for r in rows]
    return HistoryResponse(messages=items)
