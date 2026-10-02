import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    chat_model: str = "qwen3:8b"
    embed_model: str = "nomic-embed-text:latest"
    ollama_url: str = "http://127.0.0.1:11434"
    min_similarity: float = 0.48

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("FIELDMATE_DATA_DIR", "data")).resolve(),
            chat_model=os.getenv("FIELDMATE_MODEL", "qwen3:8b"),
            embed_model=os.getenv("FIELDMATE_EMBED_MODEL", "nomic-embed-text:latest"),
        )
