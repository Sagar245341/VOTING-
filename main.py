from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "votes.db"


@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                label TEXT NOT NULL,
                votes INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS voters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poll_id INTEGER NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
                voter_name TEXT NOT NULL,
                option_id INTEGER NOT NULL REFERENCES options(id) ON DELETE CASCADE,
                UNIQUE(poll_id, voter_name)
            );
            """
        )
        if connection.execute("SELECT COUNT(*) FROM polls").fetchone()[0] == 0:
            seeded_polls = [
                (
                    "Which community project should we fund next?",
                    "Your vote helps the team prioritize this quarter's biggest shared win.",
                    ["Pocket park renovation", "Neighborhood tool library", "Free coding workshops"],
                ),
                (
                    "Pick the next team social",
                    "Choose the plan that sounds like the best way to spend an afternoon together.",
                    ["Outdoor food market", "Board game cafe", "Late museum night"],
                ),
            ]
            for question, description, options in seeded_polls:
                cursor = connection.execute(
                    "INSERT INTO polls (question, description) VALUES (?, ?)",
                    (question, description),
                )
                connection.executemany(
                    "INSERT INTO options (poll_id, label) VALUES (?, ?)",
                    [(cursor.lastrowid, option) for option in options],
                )


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Pulse Vote", description="A simple, transparent voting app", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class VoteRequest(BaseModel):
    voter_name: str = Field(min_length=2, max_length=80)
    option_id: int


class PollRequest(BaseModel):
    question: str = Field(min_length=5, max_length=200)
    description: str = Field(default="", max_length=500)
    options: list[str] = Field(min_length=2, max_length=8)


def poll_payload(connection: sqlite3.Connection, poll: sqlite3.Row) -> dict:
    options = connection.execute(
        "SELECT id, label, votes FROM options WHERE poll_id = ? ORDER BY id",
        (poll["id"],),
    ).fetchall()
    total_votes = sum(option["votes"] for option in options)
    return {
        "id": poll["id"],
        "question": poll["question"],
        "description": poll["description"],
        "total_votes": total_votes,
        "options": [
            {
                "id": option["id"],
                "label": option["label"],
                "votes": option["votes"],
                "percentage": round(option["votes"] / total_votes * 100) if total_votes else 0,
            }
            for option in options
        ],
    }


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/polls")
def list_polls() -> list[dict]:
    with get_connection() as connection:
        polls = connection.execute("SELECT * FROM polls ORDER BY id DESC").fetchall()
        return [poll_payload(connection, poll) for poll in polls]


@app.post("/api/polls", status_code=201)
def create_poll(payload: PollRequest) -> dict:
    options = [option.strip() for option in payload.options if option.strip()]
    if len(options) < 2 or len(set(option.lower() for option in options)) != len(options):
        raise HTTPException(status_code=400, detail="Add at least two unique options.")

    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO polls (question, description) VALUES (?, ?)",
            (payload.question.strip(), payload.description.strip()),
        )
        connection.executemany(
            "INSERT INTO options (poll_id, label) VALUES (?, ?)",
            [(cursor.lastrowid, option) for option in options],
        )
        poll = connection.execute("SELECT * FROM polls WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return poll_payload(connection, poll)


@app.post("/api/polls/{poll_id}/vote")
def cast_vote(poll_id: int, payload: VoteRequest) -> dict:
    voter_name = payload.voter_name.strip()
    with get_connection() as connection:
        poll = connection.execute("SELECT * FROM polls WHERE id = ?", (poll_id,)).fetchone()
        option = connection.execute(
            "SELECT * FROM options WHERE id = ? AND poll_id = ?",
            (payload.option_id, poll_id),
        ).fetchone()
        if poll is None:
            raise HTTPException(status_code=404, detail="Poll not found.")
        if option is None:
            raise HTTPException(status_code=400, detail="Choose an option from this poll.")
        try:
            connection.execute(
                "INSERT INTO voters (poll_id, voter_name, option_id) VALUES (?, ?, ?)",
                (poll_id, voter_name, payload.option_id),
            )
            connection.execute("UPDATE options SET votes = votes + 1 WHERE id = ?", (payload.option_id,))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="You have already voted in this poll.")
        return poll_payload(connection, poll)
