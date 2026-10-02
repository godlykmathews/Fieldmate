import httpx


class ModelError(RuntimeError):
    pass


class Ollama:
    def __init__(self, settings):
        self.settings = settings
        self._capabilities = {}

    def capabilities(self, model):
        if model not in self._capabilities:
            details = self._post("/api/show", {"model": model})
            remote = details.get('remote_host') or details.get('remote_model') or model.endswith(':cloud')
            self._capabilities[model] = [] if remote else details.get("capabilities", [])
        return self._capabilities[model]

    def validate_model(self, model):
        if model not in self.status()["models"]:
            raise ValueError("Choose an installed Ollama model. Pull additional models in Ollama first.")
        if "completion" not in self.capabilities(model):
            raise ValueError("This is an embedding model. Choose a chat model instead.")
        return model

    def _post(self, endpoint, payload):
        try:
            with httpx.Client(timeout=httpx.Timeout(180, connect=5), trust_env=False) as client:
                response = client.post(self.settings.ollama_url + endpoint, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as error:
            raise ModelError("Ollama is not reachable. Open Ollama, then try again.") from error
        except httpx.TimeoutException as error:
            raise ModelError(
                "The local model took too long. Try a shorter question or a smaller model."
            ) from error
        except httpx.HTTPStatusError as error:
            detail = (
                error.response.json().get("error", "")
                if error.response.headers.get("content-type", "").startswith("application/json")
                else ""
            )
            raise ModelError(f"Ollama could not run this model. {detail}") from error

    def status(self):
        try:
            with httpx.Client(timeout=3, trust_env=False) as client:
                response = client.get(self.settings.ollama_url + "/api/tags")
                response.raise_for_status()
                models = [item["name"] for item in response.json()["models"]]
            return {"connected": True, "models": models, "error": None}
        except (httpx.HTTPError, ValueError, KeyError):
            return {"connected": False, "models": [], "error": "Open Ollama to connect your local models."}

    def embed(self, texts, *, query=False):
        # Nomic's task prefixes distinguish queries from passages.
        prefix = "search_query: " if query else "search_document: "
        response = self._post(
            "/api/embed",
            {
                "model": self.settings.embed_model,
                "input": [prefix + text for text in texts],
                "truncate": False,
                "keep_alive": "10m",
            },
        )
        vectors = response.get("embeddings", [])
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            raise ModelError("Ollama returned incomplete document embeddings. Nothing was saved.")
        return vectors

    def structured(self, messages, schema, model=None):
        import json

        model = model or self.settings.chat_model
        payload = {
            "model": model,
            "messages": messages,
            "format": schema,
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0, "num_ctx": 16384, "num_predict": 1800},
        }
        capabilities = self.capabilities(model)
        if 'completion' not in capabilities:
            raise ModelError('Choose a downloaded local chat model. Cloud and embedding models cannot answer here.')
        if "thinking" in capabilities:
            payload["think"] = False
        response = self._post("/api/chat", payload)
        try:
            return json.loads(response["message"]["content"])
        except (KeyError, json.JSONDecodeError) as error:
            raise ModelError("The local model returned an invalid response. Please try again.") from error
