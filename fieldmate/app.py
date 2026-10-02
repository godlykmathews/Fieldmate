import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .assistant import due_from_text
from .config import Settings
from .conversation import ConversationAssistant
from .ollama import ModelError, Ollama
from .prompts import DEFAULT_PROMPT
from .retrieval import Retrieval
from .store import Store
from .text import speech_text
from .voice import Voice

STATIC = Path(__file__).parent / "static"


class Message(BaseModel):
    request_id: str = Field(min_length=8, max_length=100)
    text: str = Field(min_length=1, max_length=6000)
    site: str = Field(default="", max_length=100)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=6)
    thread_id: str
    request_web: bool = False


class ThreadInput(BaseModel):
    category_id: str = "general"
    model: str = Field(default="", max_length=200)


class ThreadUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    category_id: str | None = None
    model: str | None = Field(default=None, max_length=200)
    custom_prompt: str | None = Field(default=None, max_length=4000)
    site: str | None = Field(default=None, max_length=100)
    closed: bool | None = None


class CategoryInput(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    prompt: str = Field(default="", max_length=3000)


class PreferencesInput(BaseModel):
    default_model: str = Field(min_length=1, max_length=200)
    system_prompt: str = Field(min_length=1, max_length=8000)
    web_mode: str = Field(pattern="^(ask|off)$")
    decision_engine: str = Field(pattern="^(laya|ollama)$")


class DocumentCategory(BaseModel):
    category_id: str | None = None


class SearchApproval(BaseModel):
    thread_id: str
    approve: bool
    query: str = Field(default="", max_length=1200)


class NoteInput(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    site: str = Field(default="", max_length=100)


class TaskInput(BaseModel):
    title: str = Field(min_length=1, max_length=6000)
    site: str = Field(default="", max_length=100)
    due_date: str | None = None


class Completion(BaseModel):
    completed: bool


class SpeechInput(BaseModel):
    text: str = Field(min_length=1, max_length=3500)


def create_app(settings=None):
    settings = settings or Settings.from_env()
    store = Store(settings.data_dir / "fieldmate.sqlite3")
    ollama = Ollama(settings)
    retrieval = Retrieval(store, ollama, settings)
    assistant = ConversationAssistant(store, retrieval, ollama, settings)
    voice = Voice(settings.data_dir)
    import_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        yield
        voice.close()

    app = FastAPI(title="Fieldmate", lifespan=lifespan)
    app.state.store = store
    app.state.ollama = ollama
    app.state.assistant = assistant
    app.state.retrieval = retrieval
    app.state.voice = voice

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        # Reject DNS-rebinding hosts and cross-origin writes to this unauthenticated local app.
        host = request.url.hostname
        if host not in {"127.0.0.1", "localhost", "::1", "testserver"}:
            return JSONResponse({"detail": "Fieldmate accepts only local connections."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
            return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(ModelError)
    async def model_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=503)

    @app.exception_handler(ValueError)
    async def value_error(request, error):
        return JSONResponse({"detail": str(error)}, status_code=400)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status")
    def status():
        state = ollama.status()
        return {
            "ollama": state,
            "chat_model": assistant.preferences()["default_model"],
            "embed_model": settings.embed_model,
            "voice": voice.status(),
            "document_count": len(store.documents()),
            "open_tasks": sum(not item["completed"] for item in store.tasks()),
            "note_count": len(store.notes()),
            "local_only": assistant.preferences()["web_mode"] == "off",
            "decision": assistant.decision.status(),
        }

    @app.post("/api/chat")
    def chat(message: Message):
        if not message.text.strip():
            raise ValueError("Type or say something first.")
        return assistant.respond(
            message.request_id,
            message.text.strip(),
            message.site.strip(),
            thread_id=message.thread_id,
            request_web=message.request_web,
        )

    @app.get("/api/settings")
    def preferences():
        return assistant.preferences() | {"default_prompt": DEFAULT_PROMPT}

    @app.get("/api/models")
    def models():
        return [model for model in ollama.status()["models"] if "completion" in ollama.capabilities(model)]

    @app.put("/api/settings")
    def save_preferences(body: PreferencesInput):
        if not body.system_prompt.strip():
            raise ValueError("Instructions cannot be empty. Restore the default prompt if needed.")
        ollama.validate_model(body.default_model)
        with assistant.lock:
            return store.set_preferences(body.model_dump())

    @app.get("/api/categories")
    def categories():
        return store.categories()

    @app.post("/api/categories")
    def add_category(body: CategoryInput):
        if not body.name.strip():
            raise ValueError("Give this category a name.")
        return store.save_category(body.name.strip(), body.prompt)

    @app.put("/api/categories/{category_id}")
    def update_category(category_id: str, body: CategoryInput):
        store.category(category_id)
        if not body.name.strip():
            raise ValueError("Give this category a name.")
        with assistant.lock:
            return store.save_category(body.name.strip(), body.prompt, category_id)

    @app.get("/api/threads")
    def threads():
        return store.threads()

    @app.post("/api/threads")
    def add_thread(body: ThreadInput):
        model = body.model or assistant.preferences()["default_model"]
        # Creating a blank chat works while Ollama is stopped; validation happens on model changes.
        return store.create_thread(body.category_id, model)

    @app.get("/api/threads/{thread_id}")
    def thread(thread_id: str):
        return {
            "thread": store.thread(thread_id),
            "exchanges": store.history(thread_id=thread_id),
            "permissions": store.pending_permissions(thread_id),
        }

    @app.patch("/api/threads/{thread_id}")
    def update_thread(thread_id: str, body: ThreadUpdate):
        values = body.model_dump(exclude_none=True)
        if "model" in values:
            ollama.validate_model(values["model"])
        if "title" in values and not values["title"].strip():
            raise ValueError("A conversation needs a title.")
        with assistant.lock:
            return store.update_thread(thread_id, values)

    @app.post("/api/search/{permission_id}")
    def search(permission_id: str, body: SearchApproval):
        return assistant.resolve_search(permission_id, body.thread_id, body.approve, body.query)

    @app.get("/api/history")
    def history(thread_id: str):
        store.thread(thread_id)
        return store.history(thread_id=thread_id)

    @app.get("/api/documents")
    def documents():
        return store.documents()

    @app.get("/api/documents/{document_id}")
    def document(document_id: str):
        documents = [d for d in store.documents() if d["id"] == document_id]
        if not documents:
            raise HTTPException(404, "Document not found.")
        return {"document": documents[0], "passages": store.document_chunks(document_id)}

    @app.post("/api/documents")
    def import_document(file: UploadFile):
        content = file.file.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise ValueError("Keep documents under 20 MB.")
        name = Path(file.filename or "document.txt").name[:200]
        if not content:
            raise ValueError("This document is empty.")
        with import_lock:
            return retrieval.ingest(name, content)

    @app.delete("/api/documents/{document_id}")
    def delete_document(document_id: str):
        if not store.delete_document(document_id):
            raise HTTPException(404, "Document not found.")
        return {"deleted": True}

    @app.patch("/api/documents/{document_id}")
    def categorize_document(document_id: str, body: DocumentCategory):
        if not store.set_document_category(document_id, body.category_id):
            raise HTTPException(404, "Document not found.")
        return {"updated": True}

    @app.get("/api/notes")
    def notes(site: str = "", query: str = ""):
        return store.notes(site, query)

    @app.post("/api/notes")
    def add_note(note: NoteInput):
        if not note.text.strip():
            raise ValueError("A note needs some text.")
        return store.add_note(note.text.strip(), note.site.strip())

    @app.get("/api/tasks")
    def tasks(site: str = ""):
        return store.tasks(site)

    @app.post("/api/tasks")
    def add_task(task: TaskInput):
        if not task.title.strip():
            raise ValueError("A task needs a title.")
        return store.add_task(task.title.strip(), task.site.strip(), due_from_text("", task.due_date))

    @app.patch("/api/tasks/{task_id}")
    def complete_task(task_id: str, body: Completion):
        if not store.complete_task(task_id, body.completed):
            raise HTTPException(404, "Task not found.")
        return {"completed": body.completed}

    @app.get("/api/export")
    def export():
        return Response(
            json.dumps({"notes": store.notes(), "tasks": store.tasks()}, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="fieldmate-notebook.json"'},
        )

    @app.post("/api/transcribe")
    def transcribe(file: UploadFile):
        content = file.file.read(12 * 1024 * 1024 + 1)
        if not content or len(content) > 12 * 1024 * 1024:
            raise ValueError("Use an audio recording under one minute and 12 MB.")
        return voice.transcribe(content)

    @app.post("/api/speak")
    def speak(body: SpeechInput):
        text = speech_text(body.text)
        if not text:
            raise ValueError("There is no readable text to speak.")
        return Response(voice.speak(text), media_type="audio/wav")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
