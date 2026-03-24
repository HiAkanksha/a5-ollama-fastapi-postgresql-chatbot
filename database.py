"""
Database helpers: load settings from .env and talk to PostgreSQL with asyncpg.
"""

import os

import asyncpg
from dotenv import load_dotenv

# Read variables from a .env file in the project folder into the environment.
load_dotenv()


# Opens one async connection to PostgreSQL using the URL from your .env file.
async def get_connection() -> asyncpg.Connection:
    # Read the connection string that python-dotenv put into the environment.
    database_url = os.getenv("DATABASE_URL")
    # Fail fast with a clear message if DATABASE_URL was never set.
    if not database_url:
        raise ValueError("DATABASE_URL is missing from environment; check your .env file.")
    # asyncpg.connect is async: we must await it to get a live connection object.
    conn = await asyncpg.connect(dsn=database_url)
    # Return the open connection; the caller should close it when finished.
    return conn


# Creates the users, sessions, and messages tables once; safe to run multiple times.
async def create_tables() -> None:
    # Grab a connection so we can run SQL against the database.
    conn = await get_connection()
    try:
        # users: one row per chat user, keyed by user_id.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        )
        # sessions: each chat thread belongs to a user.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id VARCHAR PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id),
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        )
        # messages: individual chat lines tied to a session and user.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR REFERENCES sessions(session_id),
                user_id INTEGER,
                role VARCHAR,
                content TEXT,
                timestamp TIMESTAMP DEFAULT NOW()
            );
            """
        )
    finally:
        # Always release the connection back to the pool / close the socket.
        await conn.close()


# Adds a user row; does nothing if that user_id is already in the table.
async def create_user(user_id: int) -> None:
    conn = await get_connection()
    try:
        # ON CONFLICT DO NOTHING skips the insert when user_id already exists (primary key clash).
        await conn.execute(
            """
            INSERT INTO users (user_id)
            VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            """,
            user_id,
        )
    finally:
        await conn.close()


# Starts a new chat session row linked to the given user.
async def create_session(user_id: int, session_id: str) -> None:
    conn = await get_connection()
    try:
        # $1 and $2 are parameter placeholders; asyncpg fills them safely (no SQL injection).
        await conn.execute(
            """
            INSERT INTO sessions (session_id, user_id)
            VALUES ($1, $2)
            """,
            session_id,
            user_id,
        )
    finally:
        await conn.close()


# Stores one chat message (user or assistant text) for a session.
async def save_message(
    user_id: int, session_id: str, role: str, content: str
) -> None:
    conn = await get_connection()
    try:
        await conn.execute(
            """
            INSERT INTO messages (session_id, user_id, role, content)
            VALUES ($1, $2, $3, $4)
            """,
            session_id,
            user_id,
            role,
            content,
        )
    finally:
        await conn.close()


# Fetches every message in a session for this user, oldest first, as simple dicts.
async def get_history(user_id: int, session_id: str) -> list[dict[str, str]]:
    conn = await get_connection()
    try:
        # fetch returns a list of Row objects; we only need role and content columns.
        rows = await conn.fetch(
            """
            SELECT role, content
            FROM messages
            WHERE user_id = $1 AND session_id = $2
            ORDER BY timestamp ASC
            """,
            user_id,
            session_id,
        )
        # Turn each database row into a plain dict the rest of your app can use easily.
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    finally:
        await conn.close()
