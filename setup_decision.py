"""Explicit one-time download; the running assistant never downloads models."""

import os
from pathlib import Path

os.environ.pop("HF_HUB_OFFLINE", None)
os.environ.pop("TRANSFORMERS_OFFLINE", None)
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

if __name__ == "__main__":
    from huggingface_hub import snapshot_download

    target = Path(__file__).parent / "data" / "models" / "laya-typed-decisions"
    snapshot_download(
        "convaiinnovations/laya-typed-decisions",
        local_dir=target,
        allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model"],
    )
    print(f"Laya checkpoint ready: {target}")
