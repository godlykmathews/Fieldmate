"""Local ambiguity scoring. No network access or downloads during a conversation."""

import importlib.util
import logging
import os

log = logging.getLogger(__name__)


class DecisionEngine:
    def __init__(self, data_dir):
        self.path = data_dir / "models" / "laya-typed-decisions"
        self.agent = None
        self.error = None

    def status(self):
        ready = importlib.util.find_spec("laya") is not None and (self.path / "model.safetensors").exists()
        return {
            "ready": ready and not self.error,
            "engine": "Laya typed decisions",
            "error": self.error,
            "fallback": "Ollama structured decision",
            "setup": "Run .venv/bin/python setup_decision.py" if not ready else None,
        }

    def ambiguity(self, text, context, enabled=True):
        fallback = {"engine": "Ollama structured decision", "clarification_hint": None}
        if not enabled or not self.status()["ready"]:
            return fallback
        try:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
            if self.agent is None:
                from laya import Agent

                self.agent = Agent(str(self.path), device="cpu")
            result = self.agent.predict(
                {"recent_conversation": context[-3200:], "user_request": text},
                {
                    "next_step": {
                        "type": "choice",
                        "instructions": "Use the conversation to resolve references. Clarify ONLY if a missing fact prevents a useful answer. A broad question is answerable.",
                        "criteria": {
                            "answer": "Can answer with available context and reasonable assumptions.",
                            "clarify": "An essential name or fact is missing; interpretations materially change the answer.",
                        },
                    }
                },
            )
            return {
                "engine": "Laya",
                "clarification_hint": result["answers"]["next_step"].get("choice") == "clarify",
            }
        except Exception as error:
            log.warning("Laya unavailable: %s", type(error).__name__)
            self.error = f"Laya could not load ({type(error).__name__}); using Ollama decisions."
            return fallback
