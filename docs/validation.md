# Prototype validation

Validated on an Apple Silicon Mac on October 2, 2026.

* 18 automated tests passed; Ruff and JavaScript syntax checks passed.
* Real local Ollama checks answered document-backed questions with verified source excerpts and abstained on unavailable and unrelated information.
* SQLite notes and tasks persisted correctly, and a repeated request did not create a duplicate note.
* Piper synthesized a spoken note and Whisper transcribed it correctly.
* The integration process blocked outbound socket connections while permitting local Ollama. This is a simulated offline check; the user's Wi-Fi was not disabled.
* Browser checks verified the actual document response, expandable evidence, imported guide viewer, notes/tasks views, and readiness screen. No browser console errors were observed.
* `validation.json` records the integration test output. Warm document answers took approximately 15–16 seconds on the installed Qwen3 8B model; explicit note/task capture does not need that model call.

The user's physical microphone, wind/noise conditions, multilingual accuracy, and hands-free detector still need a human trial. The demo guide is fictional. Real field procedures require the friend's own documents and evaluation. The prototype verifies excerpt text, not semantic relevance or completeness.
