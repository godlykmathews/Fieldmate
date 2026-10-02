# Fieldmate v2 validation — 2026-10-02

- 31 automated tests passed in the installed environment. Ruff and JavaScript syntax checks passed.
- Real local-model suite passed in 93.3 seconds. Qwen3 answered a general biology question; Gemma4 e2b continued its context after switching models; Laya ran locally; missing medicine names triggered a focused clarification.
- Nomic retrieval found exact excerpts for a fictional visit-handover guide. The assistant did not invent the absent pump torque specification.
- Explicit notes and tasks persisted, duplicate request receipts prevented repeated writes, and preparing a web permission did not open an outbound connection.
- Piper generated audio and Whisper transcribed it back successfully. Live human-microphone quality remains unevaluated.
- Offline smoke checks rejected outbound Python socket connections while allowing loopback Ollama. This is a process-level test, not a machine-wide firewall audit.
- A public DuckDuckGo query for Ollama structured-output documentation returned usable results. No private query or existing user conversation was used in that search test.
- Browser checks confirmed the dark layout, thread switching, category selectors, Gemma model switching, and the explicit editable web permission card.
- Existing data was backed up using SQLite's backup API before migration. Existing exchanges appear under Earlier conversation; user documents and notebook records are preserved.

See validation-v2.json for real-model outputs and timings. Quotation checks verify provenance, not the truth or completeness of generated explanations. Laya is advisory because neither its class choice nor its shipped confidence calibration is a guarantee of correct clarification routing.

Final browser checks: approved search completed with source links; resolved permissions remained resolved after reload; closing a thread kept its transcript and disabled sending; Documents displayed the existing imported file; the new-chat screen used the saved Gemma4 e2b preference. No browser errors or warnings were recorded. Screenshots: fieldmate-chat-v2.png, fieldmate-documents-v2.png, fieldmate-web-v2.png.

Sanitized DevRelay session: 370 (unpublished).
