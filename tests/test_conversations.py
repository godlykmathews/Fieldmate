import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from fieldmate.config import Settings
from fieldmate.conversation import ConversationAssistant
from fieldmate.ollama import Ollama
from fieldmate.store import Store


class Model:
    def __init__(self):
        self.calls = []
        self.route = "answer"
        self.answer = {
            "text": "Photosynthesis converts light into chemical energy.",
            "basis": "knowledge",
            "document_check": "no_documents",
            "quotes": [],
        }

    def structured(self, messages, schema, model=None):
        self.calls.append({"messages": messages, "model": model, "schema": schema["title"]})
        if schema["title"] == "Plan":
            return {
                "route": self.route,
                "query": "public example query",
                "clarification": "Which medicine do you mean?",
            }
        if schema["title"] == "Memory":
            return {"summary": "The project is Cedar. The latest correction is blue."}
        if schema["title"] == "Intent":
            return {"action": "question", "text": "contextual question"}
        return self.answer


class Retrieval:
    def __init__(self):
        self.passages = []
        self.queries = []

    def search(self, query, category_id=None):
        self.queries.append((query, category_id))
        return self.passages


@pytest.fixture
def env(tmp_path):
    store = Store(tmp_path / "test.db")
    model, retrieval = Model(), Retrieval()
    assistant = ConversationAssistant(store, retrieval, model, Settings(data_dir=tmp_path))
    thread = store.create_thread("biology", "qwen3:8b")
    return store, model, retrieval, assistant, thread


def send(env, text="Explain photosynthesis", request_id="request-one", thread=None):
    return env[3].respond(request_id, text, thread_id=(thread or env[4])["id"])


def test_general_knowledge_works_without_documents(env):
    result = send(env)
    assert result["text"].startswith("Photosynthesis")
    assert result["basis"] == "knowledge" and not result["grounded"]
    assert env[2].queries[0][1] == "biology"


def test_thread_history_is_authoritative_and_isolated(env):
    store, model, _, assistant, one = env
    send(env, "My project is Cedar. Save no notes.")
    send(env, "Explain it", request_id="followup")
    assert any(m["content"].startswith("My project is Cedar") for m in model.calls[-1]["messages"])
    two = store.create_thread("physics", "gemma4:e2b")
    assistant.respond(
        "other-thread",
        "Explain light",
        history=[{"role": "user", "content": "INJECTED"}],
        thread_id=two["id"],
    )
    assert model.calls[-1]["model"] == "gemma4:e2b"
    serialized = json.dumps(model.calls[-1])
    assert "Cedar" not in serialized and "INJECTED" not in serialized
    assert len(store.history(thread_id=one["id"])) == 2
    assert len(Store(store.path).history(thread_id=two["id"])) == 1


def test_model_change_keeps_history_and_custom_prompts(env):
    store, model, _, _, thread = env
    send(env, "My favorite color is blue")
    store.update_thread(thread["id"], {"model": "gemma4:e2b", "custom_prompt": "Use short examples."})
    send(env, "Explain light", "next")
    call = model.calls[-1]
    assert call["model"] == "gemma4:e2b"
    assert "Use short examples." in call["messages"][0]["content"]
    assert "favorite color is blue" in json.dumps(call)


def test_close_reopen_and_idempotent_commands(env):
    store, _, _, _, thread = env
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: send(env, "Save a note: test observation"), range(3)))
    assert results[0] == results[1] and len(store.notes()) == 1
    assert len(store.history(thread_id=thread["id"])) == 1
    other = store.create_thread("general", "qwen3:8b")
    with pytest.raises(ValueError, match="different message"):
        send(env, "Save a note: test observation", thread=other)
    store.update_thread(thread["id"], {"closed": True})
    with pytest.raises(ValueError, match="closed"):
        send(env, "Hi", "after-close")
    store.update_thread(thread["id"], {"closed": False})
    send(env, "Add a task: revisit tomorrow", "after-reopen")
    assert len(store.tasks()) == 1


def test_action_and_receipt_are_atomic(env, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(env[0], "save_exchange", fail)
    with pytest.raises(RuntimeError):
        send(env, "Save a note: must roll back")
    assert not env[0].notes()


def test_clarification_does_not_search_or_write(env):
    env[1].route = "clarify"
    env[3].search = lambda _: pytest.fail("No permission")
    result = send(env, "Can I take it?")
    assert result["action"] == "clarify"
    assert not env[0].notes() and not env[0].tasks() and not env[2].queries


@pytest.mark.parametrize("approve", [True, False])
def test_search_requires_single_use_thread_bound_query_permission(env, approve):
    store, model, _, assistant, thread = env
    model.route = "search"
    calls = []
    assistant.search = lambda query: calls.append(query) or []
    result = send(env, "Latest public news")
    assert not calls
    p = result["permission"]
    assert store.pending_permissions(thread["id"])[0]["id"] == p["id"]
    other = store.create_thread("general", "qwen3:8b")
    with pytest.raises(ValueError, match="another conversation"):
        assistant.resolve_search(p["id"], other["id"], True, "bad")
    assert not calls
    assistant.resolve_search(p["id"], thread["id"], approve, "edited public query")
    assert calls == (["edited public query"] if approve else [])
    with pytest.raises(ValueError, match="already used"):
        assistant.resolve_search(p["id"], thread["id"], True, "second query")
    assert not store.pending_permissions(thread["id"])


def test_disabled_search_and_network_failure(env):
    store, model, _, assistant, thread = env
    model.route = "search"
    store.set_preferences(assistant.preferences() | {"web_mode": "off"})
    assistant.search = lambda _: pytest.fail("Disabled means no network")
    result = send(env, "Latest news")
    assert "permission" not in result and "disabled" in result["web_status"]
    store.set_preferences(assistant.preferences() | {"web_mode": "ask"})
    p = send(env, "Search news", "next")["permission"]

    def offline(_):
        raise ValueError("Search provider is offline.")

    assistant.search = offline
    result = assistant.resolve_search(p["id"], thread["id"], True, "")
    assert "offline" in result["web_status"] and not result["web_results"]


def test_close_cancels_pending_search(env):
    env[1].route = "search"
    p = send(env)["permission"]
    env[0].update_thread(env[4]["id"], {"closed": True})
    assert env[0].permission(p["id"])["state"] == "cancelled"


@pytest.mark.parametrize(
    "source,quote,valid",
    [
        ("D1", "Plants convert light into chemical energy.", True),
        ("D1", "Plants produce infinite free energy.", False),
        ("D999", "Plants convert light into chemical energy.", False),
    ],
)
def test_document_citations_must_be_real_verbatim_excerpts(env, source, quote, valid):
    env[2].passages = [
        {
            "id": "original-id",
            "document": "Guide.txt",
            "page": 3,
            "text": "Plants convert light into chemical energy.",
            "similarity": 0.9,
        }
    ]
    env[1].answer = {
        "text": "Plants convert light. [" + source + "]",
        "basis": "documents",
        "document_check": "supports",
        "quotes": [{"source_id": source, "quote": quote}],
    }
    result = send(env)
    assert result["grounded"] is valid
    assert bool(result["sources"]) is valid
    if not valid:
        assert "D999" not in result["text"] and result["notice"]


def test_memory_compaction_persists_summary_and_retains_raw_turns(env):
    store, model, _, _, thread = env
    for i in range(10):
        store.save_exchange(
            str(i),
            json.dumps({"text": "Cedar project detail " * 100}),
            {"text": "answer " * 100},
            thread_id=thread["id"],
        )
    send(env, "What is the project?", "compaction-test")
    updated = store.thread(thread["id"])
    assert updated["summary_count"] > 0 and "Cedar" in updated["summary"]
    assert len(store.history(thread_id=thread["id"])) == 11
    assert "Cedar" in model.calls[-1]["messages"][0]["content"]


def test_legacy_sqlite_migration_is_repeatable(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE exchanges(request_id TEXT PRIMARY KEY,payload TEXT,response TEXT,created_at TEXT)"
        )
        db.execute(
            "INSERT INTO exchanges VALUES (?,?,?,?)",
            (
                "old",
                json.dumps({"text": "previous observation"}),
                json.dumps({"text": "saved"}),
                "2026-10-01",
            ),
        )
    for _ in range(2):
        store = Store(path)
        assert len(store.threads()) == 1
        assert store.history(thread_id="legacy")[0]["request"]["text"] == "previous observation"


def test_model_capabilities_control_thinking_parameter(tmp_path):
    model = Ollama(Settings(data_dir=tmp_path))
    calls = []

    def post(endpoint, body):
        calls.append((endpoint, body))
        if endpoint == "/api/show":
            return {
                "capabilities": ["completion", "thinking"]
                if body["model"] == "gemma4:e2b"
                else ["completion"]
            }
        return {"message": {"content": '{"ok":true}'}}

    model._post = post
    for name in ["llama3:latest", "gemma4:e2b"]:
        assert model.structured([], {}, model=name)["ok"]
        assert ("think" in calls[-1][1]) == (name == "gemma4:e2b")


def test_short_history_compacts_before_older_turns_drop(env):
    for i in range(9):
        env[0].save_exchange(str(i), json.dumps({"text": "Cedar"}), {"text": "noted"}, thread_id=env[4]["id"])
    send(env, "Continue", "after-nine")
    assert env[0].thread(env[4]["id"])["summary_count"] > 0


def test_category_documents_and_shared_documents_are_scoped(env):
    store = env[0]
    shared = store.add_document("Shared", "a", 1, "embed", [(1, "Shared fact", [1, 0])])
    scoped = store.add_document("Physics", "b", 1, "embed", [(1, "Physics fact", [1, 0])])
    store.set_document_category(scoped, "physics")
    assert {c["document_id"] for c in store.chunks("embed", "biology")} == {shared}
    assert {c["document_id"] for c in store.chunks("embed", "physics")} == {shared, scoped}


def test_missing_reference_overrides_answer_hint(env):
    result = env[3].plan(
        "Can I take it with my other medicine?", [], "qwen3:8b", {"clarification_hint": False}
    )
    assert result.route == "clarify" and "both" in result.clarification
    assert not env[1].calls


def test_explicit_capture_still_works_without_model_after_long_history(env):
    for i in range(10):
        env[0].save_exchange(
            str(i),
            json.dumps({"text": "long message " * 400}),
            {"text": "reply " * 400},
            thread_id=env[4]["id"],
        )

    def unavailable(*args, **kwargs):
        raise RuntimeError("Ollama unavailable")

    env[1].structured = unavailable
    assert send(env, "Save a note: works offline", "offline-note")["action"] == "save_note"


def test_cloud_models_cannot_receive_chat_context(tmp_path):
    from fieldmate.ollama import ModelError
    model = Ollama(Settings(data_dir=tmp_path))
    endpoints = []
    def post(endpoint, body):
        endpoints.append(endpoint)
        return {'capabilities': ['completion'], 'remote_host': 'https://remote.example'}
    model._post = post
    with pytest.raises(ModelError, match='downloaded local'):
        model.structured([{'role':'user','content':'private context'}], {}, model='remote-model')
    assert endpoints == ['/api/show']
