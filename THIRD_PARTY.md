# Open components

Check the corresponding upstream license/model card before redistribution. The application does not replace those licenses with its own.

| Component | Purpose | Upstream |
|---|---|---|
| Ollama | Local language and embedding inference | https://github.com/ollama/ollama · MIT |
| Qwen3 8B | Request understanding and source selection | https://ollama.com/library/qwen3:8b · Apache-2.0 |
| Nomic Embed Text | Local document embeddings | https://huggingface.co/nomic-ai/nomic-embed-text-v1.5 · Apache-2.0 |
| faster-whisper | Local speech recognition | https://github.com/SYSTRAN/faster-whisper · MIT |
| Whisper base | Open speech model | https://huggingface.co/Systran/faster-whisper-base · upstream Whisper MIT |
| Piper | Local speech synthesis | https://github.com/OHF-Voice/piper1-gpl · GPL-3.0 |
| Lessac medium voice | English speech weights | https://huggingface.co/rhasspy/piper-voices/tree/main/en/en_US/lessac/medium · consult downloaded MODEL_CARD |

FastAPI, Uvicorn, HTTPX, Pydantic, PyAV, ONNX Runtime, CTranslate2, pypdf, Hugging Face Hub, and transitive packages have their own licenses. Use `uv.lock` for the resolved dependency inventory.

| Additional v2 component | Purpose | Upstream |
|---|---|---|
| Laya 0.3.23 + typed-decisions checkpoint | Local ambiguity signal | https://github.com/NandhaKishorM/laya · Apache-2.0; https://huggingface.co/convaiinnovations/laya-typed-decisions |
| DDGS | Optional approved search via DuckDuckGo | https://github.com/deedy5/ddgs · MIT |
| Gemma 4 (optional selected model) | Interchangeable local chat | https://ollama.com/library/gemma4 · consult the exact model's license before redistribution |

Laya depends on PyTorch, Transformers and Safetensors. The checkpoint temperature warning is retained in diagnostics; the application uses an advisory class choice, not a calibrated confidence score.
