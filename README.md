# A5 — Conversational Chatbot (Ollama + FastAPI + PostgreSQL)

## 1. What the project does

This project is a small **REST API** for a conversational chatbot. It stores **users**, **chat sessions**, and **messages** in **PostgreSQL**, and uses **Ollama** (a local LLM server) to generate assistant replies. You register a user, open a session, send messages to `/chat`, and optionally read the full thread from `/history`.

## 2. Tech stack

| Piece | Role |
|--------|------|
| **Ollama** | Runs the language model locally and exposes an HTTP API. |
| **FastAPI** | Web framework for routes, validation, and automatic OpenAPI docs. |
| **PostgreSQL** | Database for users, sessions, and message history. |
| **asyncpg** | Async driver used to connect to PostgreSQL from Python. |
| **httpx** | Async HTTP client used to call Ollama’s REST API from the app. |

Other libraries in this repo include **Pydantic** (request/response models), **uvicorn** (ASGI server), and **python-dotenv** (loading `.env`).

## 3. Prerequisites

Before you start, you should have:

- **Python 3.10 or newer** (`python --version`)
- **PostgreSQL** installed and running (with a superuser or a user that can create databases)
- **Ollama** installed and running so the app can reach it at the URL in your `.env` (usually `http://localhost:11434`)

## 4. Install PostgreSQL and create `chatbot_db`

### Install PostgreSQL

1. Download the installer for your OS from the [official PostgreSQL downloads](https://www.postgresql.org/download/).
2. Run the installer and note the **port** (default `5432`) and the **postgres user password** you set.
3. Make sure the PostgreSQL **service** is running before you start the API.

### Create the database

Open a terminal and use the `psql` tool (installed with PostgreSQL), or use **pgAdmin** and run the same SQL.

**Example using `psql` as the `postgres` user:**

```bash
psql -U postgres -h localhost
```

Then run:

```sql
CREATE DATABASE chatbot_db;
```

Type `\q` to exit. Your connection string in `.env` will point at this database (see below).

## 5. Install Ollama and pull the Mistral model

1. Install Ollama from [ollama.com](https://ollama.com/) and start the Ollama app (or service) so it listens on **port 11434** by default.
2. In a terminal, pull the model this project expects in `.env.example`:

```bash
ollama pull mistral
```

3. Confirm Ollama is up, for example by visiting its docs or running a quick test in the Ollama app.

## 6. Set up the `.env` file

Do **not** commit real passwords to git. Use a local `.env` file only on your machine.

1. Copy the example file:

```bash
copy .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

2. Edit **`.env`** and set **`DATABASE_URL`** to match your Postgres user, password, host, port, and database name, for example:

`postgresql://postgres:YOUR_PASSWORD@localhost:5432/chatbot_db`

3. Keep **`OLLAMA_MODEL=mistral`** and **`OLLAMA_URL=http://localhost:11434`** unless you use another model or Ollama runs elsewhere.

## 7. Install dependencies

From the project root (ideally inside a virtual environment):

```bash
pip install -r requirements.txt
```

## 8. Run the app

From the project root:

```bash
uvicorn main:app --reload
```

The API listens on **http://127.0.0.1:8000** by default. `--reload` restarts the server when you change code (handy while learning).

## 9. Test with Swagger UI

With the server running, open a browser and go to:

**http://localhost:8000/docs**

You will see **Swagger UI**: you can try each route there, see request bodies, and read responses without using `curl`.

## 10. Example `curl` commands

Replace values if your user id, session id, or message text differ. On Windows, `curl` is available in modern PowerShell; use double quotes as shown.

**POST `/user`** — register user id `1`:

```bash
curl -X POST "http://localhost:8000/user" -H "Content-Type: application/json" -d "{\"user_id\": 1}"
```

**POST `/session`** — create session `my-session` for user `1`:

```bash
curl -X POST "http://localhost:8000/session" -H "Content-Type: application/json" -d "{\"user_id\": 1, \"session_id\": \"my-session\"}"
```

**POST `/chat`** — send a message (user and session must already exist):

```bash
curl -X POST "http://localhost:8000/chat" -H "Content-Type: application/json" -d "{\"user_id\": 1, \"session_id\": \"my-session\", \"message\": \"Hello, what is 2+2?\"}"
```

**GET `/history/{user_id}/{session_id}`** — list messages for that session:

```bash
curl "http://localhost:8000/history/1/my-session"
```

Order of use: create **user** → create **session** → **chat** (repeat) → **history** when you want to inspect stored messages.

## 11. Folder structure

Typical layout for this assignment (your machine may also have a local `venv/` folder from `python -m venv`, which is not listed here):

```text
a5-ollama-fastapi-postgresql-chatbot/
├── .env                 # Your real secrets (create from .env.example; keep private)
├── .env.example         # Template for DATABASE_URL, OLLAMA_MODEL, OLLAMA_URL
├── database.py          # Async PostgreSQL helpers (asyncpg)
├── main.py              # FastAPI app, routes, Ollama integration (httpx)
├── models.py            # Pydantic models for requests/responses
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

If you use a virtual environment, you will often see `venv/` next to these files; add `venv/` to `.gitignore` if you use git so it is not committed.
