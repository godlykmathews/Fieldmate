"""One-time model download. The app never downloads models during normal operation."""

import os
import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download


def main():
    data = Path(os.getenv("FIELDMATE_DATA_DIR", "data"))
    models = data / "models"
    models.mkdir(parents=True, exist_ok=True)
    print("Downloading Whisper base (multilingual, about 150 MB)…", flush=True)
    snapshot_download(
        "Systran/faster-whisper-base",
        local_dir=str(models / "whisper-base"),
        allow_patterns=[
            "model.bin",
            "config.json",
            "tokenizer.json",
            "vocabulary.*",
            "preprocessor_config.json",
        ],
        max_workers=2,
    )
    root = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/"
    for name in ["en_US-lessac-medium.onnx", "en_US-lessac-medium.onnx.json", "MODEL_CARD"]:
        destination = models / ("lessac-MODEL_CARD.txt" if name == "MODEL_CARD" else name)
        if destination.exists():
            continue
        print(f"Downloading Piper {name}…", flush=True)
        temporary = destination.with_suffix(destination.suffix + ".part")
        urllib.request.urlretrieve(root + name, temporary)
        temporary.replace(destination)
    print("Voice models are ready. Restart Fieldmate if it is already open.", flush=True)


if __name__ == "__main__":
    main()
