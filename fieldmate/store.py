"""A small local vector store and durable notebook. No external database service."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .prompts import CATEGORIES, DEFAULT_PROMPT


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, digest TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL, pages INTEGER NOT NULL, embed_model TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    page INTEGER NOT NULL, text TEXT NOT NULL, embedding TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notes (
                    id TEXT PRIMARY KEY, text TEXT NOT NULL, site TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, site TEXT NOT NULL,
                    due_date TEXT, completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS exchanges (
                    request_id TEXT PRIMARY KEY, payload TEXT NOT NULL, response TEXT NOT NULL,
                    created_at TEXT NOT NULL);
            """)
            db.executescript("""
                CREATE TABLE IF NOT EXISTS categories (id TEXT PRIMARY KEY, name TEXT NOT NULL, prompt TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS threads (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, category_id TEXT NOT NULL REFERENCES categories(id),
                    model TEXT NOT NULL, custom_prompt TEXT NOT NULL DEFAULT '', site TEXT NOT NULL DEFAULT '',
                    closed INTEGER NOT NULL DEFAULT 0, summary TEXT NOT NULL DEFAULT '', summary_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS search_permissions (
                    id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads(id), request_id TEXT NOT NULL,
                    query TEXT NOT NULL, question TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL);
            """)
            for category in CATEGORIES:
                db.execute("INSERT OR IGNORE INTO categories VALUES (?,?,?)", category)
            columns = {r["name"] for r in db.execute("PRAGMA table_info(exchanges)")}
            if "thread_id" not in columns:
                db.execute("ALTER TABLE exchanges ADD COLUMN thread_id TEXT REFERENCES threads(id)")
            if "category_id" not in {r["name"] for r in db.execute("PRAGMA table_info(documents)")}:
                db.execute("ALTER TABLE documents ADD COLUMN category_id TEXT REFERENCES categories(id)")
            if db.execute("SELECT 1 FROM exchanges WHERE thread_id IS NULL").fetchone():
                stamp = now()
                db.execute(
                    "INSERT OR IGNORE INTO threads (id,title,category_id,model,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                    ("legacy", "Earlier conversation", "fieldwork", "", stamp, stamp),
                )
                db.execute("UPDATE exchanges SET thread_id='legacy' WHERE thread_id IS NULL")
            db.execute("CREATE INDEX IF NOT EXISTS exchanges_thread ON exchanges(thread_id,created_at)")

    def preferences(self, default_model="qwen3:8b"):
        defaults = {
            "default_model": default_model,
            "system_prompt": DEFAULT_PROMPT,
            "web_mode": "ask",
            "decision_engine": "laya",
        }
        with self.connect() as db:
            row = db.execute("SELECT value FROM preferences WHERE id=1").fetchone()
        return defaults | (json.loads(row["value"]) if row else {})

    def set_preferences(self, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO preferences VALUES (1,?)", (json.dumps(value),))
        return value

    def categories(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM categories ORDER BY rowid")]

    def category(self, category_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM categories WHERE id=?", (category_id,)).fetchone()
        if not row:
            raise ValueError("Category not found.")
        return dict(row)

    def save_category(self, name, prompt, category_id=None):
        category_id = category_id or str(uuid.uuid4())
        with self.connect() as db:
            db.execute(
                "INSERT INTO categories VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,prompt=excluded.prompt",
                (category_id, name, prompt),
            )
        return self.category(category_id)

    def threads(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM threads ORDER BY closed,updated_at DESC")]

    def thread(self, thread_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM threads WHERE id=?", (thread_id,)).fetchone()
        if not row:
            raise ValueError("Conversation not found. Create a new thread.")
        return dict(row)

    def create_thread(self, category_id, model):
        self.category(category_id)
        thread_id, stamp = str(uuid.uuid4()), now()
        with self.connect() as db:
            db.execute(
                "INSERT INTO threads (id,title,category_id,model,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                (thread_id, "New chat", category_id, model, stamp, stamp),
            )
        return self.thread(thread_id)

    def update_thread(self, thread_id, values):
        self.thread(thread_id)
        allowed = {
            "title",
            "category_id",
            "model",
            "custom_prompt",
            "site",
            "closed",
            "summary",
            "summary_count",
        }
        if set(values) - allowed:
            raise ValueError("Unknown conversation setting.")
        if "category_id" in values:
            self.category(values["category_id"])
        values = values | {"updated_at": now()}
        with self.connect() as db:
            db.execute(
                "UPDATE threads SET " + ",".join(f"{key}=?" for key in values) + " WHERE id=?",
                (*values.values(), thread_id),
            )
            if values.get("closed"):
                db.execute(
                    "UPDATE search_permissions SET state='cancelled' WHERE thread_id=? AND state='pending'",
                    (thread_id,),
                )
        return self.thread(thread_id)

    def set_document_category(self, document_id, category_id):
        if category_id:
            self.category(category_id)
        with self.connect() as db:
            return (
                db.execute(
                    "UPDATE documents SET category_id=? WHERE id=?", (category_id, document_id)
                ).rowcount
                > 0
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def documents(self):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute("""
                SELECT d.*, COUNT(c.id) AS chunks FROM documents d LEFT JOIN chunks c
                ON c.document_id=d.id GROUP BY d.id ORDER BY d.created_at DESC
            """)
            ]

    def document_by_digest(self, digest):
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE digest=?", (digest,)).fetchone()
            return dict(row) if row else None

    def add_document(self, name, digest, pages, model, chunks):
        document_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute(
                "INSERT INTO documents (id,name,digest,created_at,pages,embed_model) VALUES (?,?,?,?,?,?)",
                (document_id, name, digest, now(), pages, model),
            )
            for page, text, embedding in chunks:
                db.execute(
                    "INSERT INTO chunks VALUES (?,?,?,?,?)",
                    (str(uuid.uuid4()), document_id, page, text, json.dumps(embedding)),
                )
        return document_id

    def delete_document(self, document_id):
        with self.connect() as db:
            return db.execute("DELETE FROM documents WHERE id=?", (document_id,)).rowcount > 0

    def chunks(self, model, category_id=None):
        with self.connect() as db:
            rows = db.execute(
                """SELECT c.*, d.name FROM chunks c JOIN documents d
                ON c.document_id=d.id WHERE d.embed_model=?
                AND (? IS NULL OR d.category_id IS NULL OR d.category_id=?)""",
                (model, category_id, category_id),
            ).fetchall()
            return [dict(row) | {"embedding": json.loads(row["embedding"])} for row in rows]

    def document_chunks(self, document_id):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id,page,text FROM chunks WHERE document_id=? ORDER BY page,rowid", (document_id,)
                )
            ]

    def notes(self, site="", query=""):
        with self.connect() as db:
            rows = db.execute(
                """SELECT * FROM notes WHERE (?='' OR site=?)
                AND (?='' OR instr(lower(text),lower(?))>0) ORDER BY created_at DESC LIMIT 200""",
                (site, site, query, query),
            ).fetchall()
            return [dict(row) for row in rows]

    def tasks(self, site=""):
        with self.connect() as db:
            return [
                dict(row) | {"completed": bool(row["completed"])}
                for row in db.execute(
                    "SELECT * FROM tasks WHERE (?='' OR site=?) ORDER BY completed,due_date IS NULL,due_date,created_at DESC",
                    (site, site),
                )
            ]

    def add_note(self, text, site, *, db=None):
        item = {"id": str(uuid.uuid4()), "text": text, "site": site, "created_at": now()}
        if db is None:
            with self.connect() as connection:
                self._insert_note(connection, item)
        else:
            self._insert_note(db, item)
        return item

    @staticmethod
    def _insert_note(db, item):
        db.execute("INSERT INTO notes VALUES (:id,:text,:site,:created_at)", item)

    def add_task(self, title, site, due_date, *, db=None):
        item = {
            "id": str(uuid.uuid4()),
            "title": title,
            "site": site,
            "due_date": due_date,
            "completed": False,
            "created_at": now(),
        }
        if db is None:
            with self.connect() as connection:
                self._insert_task(connection, item)
        else:
            self._insert_task(db, item)
        return item

    @staticmethod
    def _insert_task(db, item):
        db.execute("INSERT INTO tasks VALUES (:id,:title,:site,:due_date,:completed,:created_at)", item)

    def complete_task(self, task_id, completed):
        with self.connect() as db:
            return db.execute("UPDATE tasks SET completed=? WHERE id=?", (completed, task_id)).rowcount > 0

    def cached(self, request_id, payload):
        with self.connect() as db:
            row = db.execute("SELECT * FROM exchanges WHERE request_id=?", (request_id,)).fetchone()
        if row:
            if row["payload"] != payload:
                raise ValueError("This request ID was already used for a different message.")
            return json.loads(row["response"])
        return None

    def save_exchange(self, request_id, payload, response, *, db=None, thread_id=None):
        values = (request_id, payload, json.dumps(response), now(), thread_id)

        def write(connection):
            connection.execute(
                "INSERT INTO exchanges (request_id,payload,response,created_at,thread_id) VALUES (?,?,?,?,?)",
                values,
            )
            if thread_id:
                connection.execute(
                    "UPDATE threads SET updated_at=?,title=CASE WHEN title='New chat' THEN ? ELSE title END WHERE id=?",
                    (now(), json.loads(payload)["text"][:65], thread_id),
                )

        if db is None:
            with self.connect() as connection:
                write(connection)
        else:
            write(db)

    def history(self, limit=10000, thread_id=None):
        with self.connect() as db:
            rows = db.execute(
                "SELECT request_id,payload,response,created_at FROM exchanges WHERE (? IS NULL OR thread_id=?) ORDER BY rowid DESC LIMIT ?",
                (thread_id, thread_id, limit),
            ).fetchall()
        return [
            {
                "request": json.loads(row["payload"]),
                "response": json.loads(row["response"]),
                "created_at": row["created_at"],
                "request_id": row["request_id"],
            }
            for row in reversed(rows)
        ]

    def new_permission(self, thread_id, request_id, query, question, db):
        item = {
            "id": str(uuid.uuid4()),
            "thread_id": thread_id,
            "request_id": request_id,
            "query": query,
            "question": question,
            "state": "pending",
            "created_at": now(),
        }
        db.execute(
            "INSERT INTO search_permissions VALUES (:id,:thread_id,:request_id,:query,:question,:state,:created_at)",
            item,
        )
        return item

    def permission(self, permission_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM search_permissions WHERE id=?", (permission_id,)).fetchone()
        if not row:
            raise ValueError("Search request not found.")
        return dict(row)

    def claim_permission(self, permission_id, thread_id, approve, query):
        # A claimed permission is never reused, even if a network request or model call fails.
        with self.connect() as db:
            count = db.execute(
                "UPDATE search_permissions SET state=?,query=? WHERE id=? AND thread_id=? AND state='pending'",
                ("approved" if approve else "declined", query, permission_id, thread_id),
            ).rowcount
        if not count:
            raise ValueError("This search permission was already used or cancelled.")

    def pending_permissions(self, thread_id):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM search_permissions WHERE thread_id=? AND state='pending'", (thread_id,)
                )
            ]
