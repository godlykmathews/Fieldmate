# Community research notes

These two posts describe their authors' projects and experience; they are not independent benchmarks or proof of correctness. Implementation choices were checked against upstream documentation.

## Local Voice-Controlled AI Agent (Whisper + Ollama + Streamlit)

Author: Jessica Ekka
https://dev.to/jessica_ekka_c7a605f5a2ee/local-voice-controlled-ai-agent-whisper-ollama-streamlit-6ac

The author combines voice transcription, rules plus model intent detection, a bounded execution layer, and a UI. They describe malformed JSON and parameter extraction as practical problems. Fieldmate uses deterministic explicit capture commands and Ollama schema-constrained responses. No comments were returned when checked.

## Making RAG admit when it's guessing: source-grounded hallucination checks

Author: Sid Probstein
https://dev.to/sidswirl/making-rag-admit-when-its-guessing-source-grounded-hallucination-checks-g22

The author warns that an answer can have citations without being supported by them. The comment discussion points out that a source checker also needs evaluation and that unverified claims differ from contradicted ones. Fieldmate starts with verified verbatim excerpts rather than claiming to validate arbitrary model paraphrases. Relevance still needs evaluation on the friend's real documents.

## Primary references

* https://docs.ollama.com/capabilities/structured-outputs
* https://docs.ollama.com/capabilities/embeddings
* https://github.com/SYSTRAN/faster-whisper
* https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md

## v2: keep conversational memory separate from document evidence

### 🌐 Community Wisdom: [AI agent memory vs RAG — what's the difference?](https://dev.to/statewave/ai-agent-memory-vs-rag-whats-the-difference-17cc)
> **Source**: [Statewave](https://dev.to/statewave)
> **Tags**: `ai`, `rag`, `llm`, `architecture`
>
> The author distinguishes document retrieval from conversational memory and describes compaction and provenance. Commenters emphasize stale facts and cross-session leakage; the author acknowledges that session boundaries need explicit application policy. This is one architecture account and discussion, not a benchmark or proof of our implementation. Fieldmate uses separate thread-scoped history and summary storage; document retrieval does not serve as chat memory.
>
> 🔗 [Read Full Discussion](https://dev.to/statewave/ai-agent-memory-vs-rag-whats-the-difference-17cc)

Primary references: [Laya API and checkpoint documentation](https://github.com/NandhaKishorM/laya), [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [DDGS explicit search backends](https://github.com/deedy5/ddgs).

Laya proposes an ambiguity signal; deterministic rules handle clear missing references and the local generator resolves nuanced context. The generator never grants itself search approval. Exact excerpt matching validates quotation provenance, not the factual correctness of the generated prose.

## Contextual note and task capture

### 🌐 Community Wisdom: [Smaller Context, Recoverable History: Inside an Agent Memory Handoff](https://dev.to/badbat4560/smaller-context-recoverable-history-inside-an-agent-memory-handoff-404j)
> **Source**: [badbat4560](https://dev.to/badbat4560)
> **Tags**: `agents`, `ai`, `architecture`, `llm`
>
> The author distinguishes compact working context from recoverable exact source text. Their limited synthetic benchmark does not establish universally lossless memory. A commenter supports preserving exact tool records separately from summaries. For Fieldmate, this supports resolving captures to stored thread messages rather than asking the model to reconstruct a plan from its summary. Whole-message selection uses constrained source IDs; the server copies the original content.
>
> 🔗 [Read Full Discussion](https://dev.to/badbat4560/smaller-context-recoverable-history-inside-an-agent-memory-handoff-404j)

Counter-position: [Agent Memory's Real Failure Is Currency, Not Retrieval](https://dev.to/madebyexpert/agent-memorys-real-failure-is-currency-not-retrieval-40h9) argues that retrieval can still return stale facts. No comments were returned when checked. Fieldmate's selector receives chronological candidates and instructions to prefer the latest revision of the requested subject; this is not a guarantee of perfect semantic selection. Missing, invented, or invalid references do not cause writes.
