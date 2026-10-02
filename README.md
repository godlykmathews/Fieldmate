# Fieldmate

A local laptop assistant with voice, persistent conversations, subject categories, document retrieval, notes, tasks, and optional permission-based web search. Its simple dark interface has **Chat** and **Documents** tabs.

## Run

Open Ollama, then double-click **Start Fieldmate.command**, or run:

```sh
cd /path/to/Assistant
./.venv/bin/python -m fieldmate
```

Open http://127.0.0.1:8765. The app binds only to this laptop. All fonts and UI assets are local.

For a new installation (internet needed for the initial downloads):

```sh
ollama pull qwen3:8b
ollama pull nomic-embed-text
uv sync --python 3.12 --extra dev --extra decision
uv run --extra decision python setup_voice.py
uv run --extra decision python setup_decision.py
./.venv/bin/python -m fieldmate
```

Use the existing `.venv` directly while offline. `uv run` without `--extra decision` may remove the optional Laya packages during synchronization. Python 3.12 or 3.13 is required. Laya is optional: if unavailable, structured Ollama decisions provide clarification routing.

## Everyday use

- **New thread** starts a fresh context. Threads persist across reloads and app restarts. The sidebar separates open and closed conversations. The `…` button renames, closes/reopens, or adds instructions to the current conversation.
- Choose **General, Fieldwork, Medicine, Biology, or Physics** beside the model selector. In **Settings → Categories**, add subjects or edit their instructions. Category changes keep the current thread's history; use a new thread for a clean start.
- **Settings → Assistant** contains a recommended default prompt, editable instructions, the default model for new threads, the search preference, and the clarification engine.
- Select an installed **Ollama chat model** in the composer. **Gemma 4 works**: `gemma4:e2b` was tested with an ongoing Qwen conversation. Model switching retains context. New models must first be pulled using Ollama; the UI never silently downloads them. Chat models must support Ollama chat and structured JSON output. Embedding-only models are excluded.
- **Documents** imports PDF, Markdown, and UTF-8 TXT files up to 20 MB. View extracted passages, change category, or remove documents from the index. Shared documents apply to all subjects; category documents apply only to that category. Scanned PDFs require OCR first. `examples/demo-field-guide.md` is fictional, not a real operating manual.
- Say **“Save a note: …”**, **“Add a task: … tomorrow”**, **“Show my notes”**, or **“Show my tasks”**. The notebook icon shows notes and task checkboxes and provides JSON export. Set an optional site/project in conversation settings to organize captures. Tasks do not schedule notifications.

## Conversation and evidence

The server loads history from the selected thread; client-supplied history cannot inject another conversation. Recent turns and a persistent summary of older turns maintain continuity within a bounded model context. Summaries retain goals, facts, corrections, and unresolved questions. The full transcript stays in SQLite, including turns that were summarized. Summarization can lose detail; it is conversational memory, not a verified source of truth.

For questions, the coordinator asks a local decision engine whether to answer, clarify, or propose a web search. Laya's open typed-decision checkpoint provides an advisory ambiguity signal. Ollama resolves references and phrases a specific clarification only when information is essential. Laya's scores are not treated as calibrated certainty; it cannot authorize tools or network access.

The assistant answers general questions from model knowledge and cross-checks relevant document passages using local retrieval. Replies label **model knowledge**, **document sources**, **mixed evidence**, or **uncertainty**. Source excerpts are accepted only if the ID exists and the normalized quote is a verbatim substring of a retrieved passage. Invalid references are removed and flagged. A matching quote does not prove that the generated explanation is correct, relevant, complete, or medically appropriate. Documents may be wrong or stale; reported conflicts need review. Health categories are educational, not a clinical decision system.

Retrieval uses Nomic embeddings, SQLite, an exact cosine scan, and a keyword boost. The similarity gate is a prototype heuristic. Chat-model changes do **not** affect the document index. Changing embedding models requires reindexing; Nomic task prefixes are built into the embedding adapter.

## Internet search with permission

Search defaults to **Ask before every search**. The globe button explicitly requests a search; time-sensitive questions can also cause the assistant to propose one. Both paths show an editable query and **Allow this search / Continue offline** buttons. Only the approved query is sent to DuckDuckGo using DDGS. The full conversation and documents are not uploaded. Check the query for personal details before approval.

Approval is stored server-side, bound to the thread and query, and consumed once. Declining, closing the conversation, or disabling search prevents it. Every new search needs another approval. No background connectivity probe runs. Connection/provider failures are shown explicitly and the assistant continues without claiming web verification. Results are **search snippets**, not full-page retrieval. The provider may rate-limit or block automated searches; there is no paid API key or automatic fallback to another provider. A failed/consumed permission must be requested again.

Choose **Disabled — stay offline** to prevent search requests entirely. Download models, import documents, and check voice before going offline; Ollama must still run locally.

## Voice

Click the microphone to record, then click again to transcribe locally with faster-whisper. Check the transcript before sending. **Start hands-free session** uses local browser volume detection and a silence timeout; it submits each utterance and pauses during processing or speech. Permission requests pause hands-free mode so approval remains an explicit click. **Read replies aloud** uses Piper locally. No browser cloud recognition or TTS API is used.

This is turn-taking, not full-duplex speech: it cannot interrupt the assistant by voice. Wind, quiet speech, or clipped utterance beginnings can affect the simple detector. Push-to-talk is preferable in noisy conditions. The included Piper voice is English. Browser microphone permission must be granted. Live human-microphone quality has not been evaluated; the automated Piper → Whisper round trip is tested.

## Storage and safety boundaries

`data/fieldmate.sqlite3` holds transcripts, summaries, settings, categories, source passages/vectors, notes, tasks, and search permissions. `data/models/` holds downloaded voice and Laya weights. Data is not encrypted by the app. The v2 migration moves old exchanges into **Earlier conversation** without deleting documents or notebook items. A SQLite backup is saved before upgrading this development installation.

Actions use validated fixed routes, not unrestricted shell or browser tools. Note/task writes and request receipts are atomic; retries do not duplicate them. Origin and host checks restrict access to the local app. One response is processed at a time on this laptop.

Defaults can also be seeded with `FIELDMATE_MODEL`, `FIELDMATE_EMBED_MODEL`, and `FIELDMATE_DATA_DIR`. Saved UI preferences take precedence for the default chat model.

## Validation

```sh
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check .
node --check fieldmate/static/app.js
./.venv/bin/python -m scripts.smoke_test --data-dir data
```

The tests cover thread isolation, SQLite migration, compaction, categories, custom instructions, model switching, citation validation, atomic captures, and search approval enforcement. The smoke script uses real Ollama and speech models in a temporary database while rejecting outbound Python socket connections. See `docs/validation-v2.json` for the completed real-model checks.

## Open innovation and build sessions

Ollama, open-weight chat models, Nomic, Whisper, Piper, and Laya perform the core work. After setup, inference and private-document handling can stay on the laptop without cloud inference fees. Prompts, routing, retrieval, and models can be inspected and changed. Software/model licenses are separate; see `THIRD_PARTY.md`. Source is MIT; Piper is GPL-3.0 and redistributed packages retain their own obligations.

DevRelay holds sanitized, curated build sessions (not complete raw transcripts):

- [Planning Fieldmate](https://dev.to/agent_sessions/planning-fieldmate-an-offline-voice-assistant-for-a-field-worker-fgfqpi), embed `{% agent_session 359 %}`.
- [Building Fieldmate](https://dev.to/agent_sessions/building-fieldmate-offline-rag-voice-notes-and-tasks-with-ollama-r0zolb), embed `{% agent_session 361 %}`.

See `docs/community-research.md` for design references and community caveats.

The v2 milestone was also saved as an unpublished curated session:
[Fieldmate v2 build log](https://dev.to/agent_sessions/fieldmate-v2-contextual-local-assistant-categories-and-permission-gated-web-search-dd9xt4), embed `{% agent_session 370 %}`. Its sanitized source is `docs/devrelay-v2.json`.
