"""Real-model offline checks in a temporary database; never touches user history."""

import argparse
import json
import socket
import time
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

from fieldmate.config import Settings
from fieldmate.conversation import ConversationAssistant
from fieldmate.ollama import Ollama
from fieldmate.retrieval import Retrieval
from fieldmate.store import Store
from fieldmate.voice import Voice


def forbid_outbound_connections():
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "localhost", "::1"}:
            raise AssertionError("An offline component attempted an outbound connection.")
        return original(sock, address)

    socket.socket.connect = connect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--report", default="docs/validation-v2.json")
    parser.add_argument("--skip-voice", action="store_true")
    args = parser.parse_args()
    forbid_outbound_connections()
    started, results = time.monotonic(), []
    root = Path(__file__).resolve().parents[1]
    with TemporaryDirectory(prefix="fieldmate-smoke-") as directory:
        settings = Settings(data_dir=Path(directory))
        store = Store(settings.data_dir / "test.sqlite3")
        ollama = Ollama(settings)
        retrieval = Retrieval(store, ollama, settings)
        assistant = ConversationAssistant(store, retrieval, ollama, settings)
        assistant.decision.path = Path(args.data_dir).resolve() / "models/laya-typed-decisions"
        thread = store.create_thread("biology", "qwen3:8b")

        def ask(text, check, label=None):
            timer = time.monotonic()
            r = assistant.respond(str(uuid.uuid4()), text, thread_id=thread["id"])
            assert check(r), r
            row = {
                "test": label or text,
                "passed": True,
                "seconds": round(time.monotonic() - timer, 2),
                "text": r["text"],
                "model": r.get("model"),
                "basis": r.get("basis"),
                "decision": r.get("decision"),
            }
            results.append(row)
            print(json.dumps(row), flush=True)
            return r

        ask(
            "I am learning photosynthesis. Explain it in two sentences.",
            lambda r: "light" in r["text"].lower(),
        )
        store.update_thread(thread["id"], {"model": "gemma4:e2b"})
        ask(
            "Why does it need light?",
            lambda r: any(w in r["text"].lower() for w in ["plant", "photosynth", "chlorophyll"]),
        )
        thread = store.create_thread("medicine", "qwen3:8b")
        ask("Can I take it with my other medicine?", lambda r: r["action"] == "clarify")
        thread = store.create_thread("fieldwork", "qwen3:8b")
        retrieval.ingest("Demo field guide.md", (root / "examples/demo-field-guide.md").read_bytes())
        ask("What should I include in a visit handover?", lambda r: r["grounded"] and bool(r["sources"]))
        ask(
            "According to the guide, what is the pump torque limit in newton meters?",
            lambda r: not r["grounded"] and not any(w in r["text"] for w in ["500", "200", "100 Nm"]),
        )
        # Explicit captures are deterministic and idempotent.
        receipt = assistant.respond(
            "retry-note", "Save a note: the identifier is unreadable", thread_id=thread["id"]
        )
        assert (
            assistant.respond(
                "retry-note", "Save a note: the identifier is unreadable", thread_id=thread["id"]
            )
            == receipt
        )
        assert len(store.notes()) == 1
        task = assistant.respond("task-note", "Add a task: revisit tomorrow", thread_id=thread["id"])
        assert task["item"]["due_date"]
        # Web request planning must work even when outbound sockets are prohibited.
        r = assistant.respond(
            "web-permission", "Ollama documentation", thread_id=thread["id"], request_web=True
        )
        assert r["action"] == "search_permission"
        results.append({"test": "Captures, retries, permission without outbound search", "passed": True})
    if not args.skip_voice:
        voice = Voice(Path(args.data_dir).resolve())
        try:
            audio = voice.speak("Save a note. The site identifier is unreadable.")
            transcription = voice.transcribe(audio)
            assert "unreadable" in transcription["text"].lower(), transcription
            results.append(
                {"test": "Piper to Whisper round trip", "passed": True, "text": transcription["text"]}
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            voice.close()
    report = {
        "passed": True,
        "seconds": round(time.monotonic() - started, 2),
        "outbound_connections": "Python socket connects blocked; loopback Ollama allowed",
        "tests": results,
    }
    Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps({"passed": True, "seconds": report["seconds"]}), flush=True)


if __name__ == "__main__":
    main()
