"""Local-only speech models. Downloads happen in setup_voice.py, never in request handlers."""

import atexit
import gc
import io
import os
import threading
import wave
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"


class Voice:
    def __init__(self, data_dir: Path):
        self.models = data_dir / "models"
        self.stt = None
        self.tts = None
        self.stt_lock = threading.Lock()
        self.tts_lock = threading.Lock()
        atexit.register(self.close)

    def close(self):
        # Release CTranslate2/ONNX objects before interpreter-level native library teardown.
        with self.stt_lock, self.tts_lock:
            if self.stt is not None:
                self.stt.model.unload_model()
                self.stt = None
            self.tts = None
            gc.collect()

    def status(self):
        return {
            "transcription": (self.models / "whisper-base" / "model.bin").is_file(),
            "speech": (self.models / "en_US-lessac-medium.onnx").is_file()
            and (self.models / "en_US-lessac-medium.onnx.json").is_file(),
            "stt_model": "Whisper base · multilingual · CPU int8",
            "tts_model": "Piper · Lessac",
        }

    def transcribe(self, content):
        if not self.status()["transcription"]:
            raise ValueError("Voice input isn't set up yet. Run the voice setup command in the README.")
        import onnxruntime
        from faster_whisper import WhisperModel

        onnxruntime.disable_telemetry_events()

        with self.stt_lock:
            if self.stt is None:
                self.stt = WhisperModel(
                    str(self.models / "whisper-base"),
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=4,
                    local_files_only=True,
                )
            try:
                segments, info = self.stt.transcribe(
                    io.BytesIO(content), beam_size=3, vad_filter=True, condition_on_previous_text=False
                )
                if info.duration > 65:
                    raise ValueError("Recordings must be under one minute.")
                text = " ".join(segment.text.strip() for segment in segments).strip()
            except ValueError:
                raise
            except Exception as error:
                raise ValueError("This audio could not be transcribed. Try recording again.") from error
        return {"text": text, "language": info.language, "duration": info.duration}

    def speak(self, text):
        if not self.status()["speech"]:
            raise ValueError("Voice output isn't set up yet. Run the voice setup command in the README.")
        import onnxruntime
        from piper import PiperVoice

        onnxruntime.disable_telemetry_events()

        with self.tts_lock:
            if self.tts is None:
                self.tts = PiperVoice.load(str(self.models / "en_US-lessac-medium.onnx"))
            output = io.BytesIO()
            with wave.open(output, "wb") as wav:
                self.tts.synthesize_wav(text, wav)
        return output.getvalue()
