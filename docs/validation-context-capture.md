# Contextual capture regression checks — 2026-10-02

The reported bug saved the literal labels `this` and `our study plan` rather than the existing conversation content. The write path bypassed contextual resolution, and its routing prompt told the model to preserve the command's wording.

## Fix

- Separate new literal content from references to existing conversation content.
- Resolve `save this` against the latest answer in the same thread, skipping action receipts and permission cards, without needing model inference.
- For named references, retrieve candidates from the persisted transcript, including turns already summarized out of recent context.
- Give the local selector short source IDs constrained by a JSON schema. Whole-content captures constrain the quote to an empty string so the server copies the original message. Specific excerpts must occur verbatim in a selected source.
- Default to the newest relevant version. An invalid or missing selection asks for clarification and writes nothing.
- Keep request idempotency, atomic writes, task dates, model choice, and thread isolation.

## Validation

The automated suite covers literal and contextual commands, both reported phrases, intervening receipts, older context, long messages and retrieval budgets, task dates, specific excerpts, fabricated selections, disconnected models, separate threads, retries, and rollback.

Local Gemma 4 12B replay uses a temporary SQLite copy. Checks compare actual saved content against the original stored answer, then exercise older context after topic changes, newer revisions, and a task extracted from a referenced step. No validation notes are written into the user's active notebook.

Live testing caught two problems that unit doubles did not expose: the model regenerated a purported quotation, and it over-clarified between the current study plan and older related topic lists. Whole-content selection is now enforced by the decoding schema, and the resolver instructions use subject and recency to resolve ordinary follow-ups.

Named reference selection still depends on the local model and a bounded candidate set. Exact text validation verifies its origin, not the truth of the saved content or perfect semantic selection.

## Recorded result

- Automated suite: 61 passed. Ruff checks and git diff whitespace checks passed.
- Live Gemma 4 12B replay: both reported commands saved the original 1,707-character answer; an older plan remained recoverable after compaction and topic changes; a named roadmap selected its newer revision; a referenced task step retained the requested due date.
- The two original placeholder notes and their matching chat receipts were restored after a SQLite backup.
- The app was restarted on port 8765. HTTP checks verified both restored notes and receipts against the original answer.
