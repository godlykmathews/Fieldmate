import io

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from fieldmate.app import create_app
from fieldmate.config import Settings
from fieldmate.retrieval import Retrieval, extract_pages, split_passages
from fieldmate.store import Store


class Embeddings:
    def embed(self, texts, query=False):
        return [[1.0, 0.0] if "identifier" in text.lower() else [0.0, 1.0] for text in texts]


def test_vector_search_and_document_delete(tmp_path):
    settings = Settings(data_dir=tmp_path, min_similarity=0.6)
    store = Store(tmp_path / "test.sqlite3")
    retrieval = Retrieval(store, Embeddings(), settings)
    result = retrieval.ingest(
        "Guide.txt",
        b"If an identifier is unreadable, record it as unreadable.\n\nDownload guides before a visit.",
    )
    assert retrieval.ingest(
        "Copy.txt",
        b"If an identifier is unreadable, record it as unreadable.\n\nDownload guides before a visit.",
    )["duplicate"]
    assert len(store.documents()) == 1
    matches = retrieval.search("unreadable identifier")
    assert len(matches) == 1
    assert "identifier" in matches[0]["text"]
    store.delete_document(result["id"])
    assert retrieval.search("identifier") == []


def test_chunking_preserves_pages_and_long_paragraph_tail():
    text = " ".join(f"word{i}" for i in range(900))
    chunks = split_passages([(4, text)])
    assert len(chunks) > 1
    assert all(page == 4 and len(passage) <= 1600 for page, passage in chunks)
    assert "word899" in chunks[-1][1]


def test_bad_documents_fail_clearly():
    with pytest.raises(ValueError, match="UTF-8"):
        extract_pages("test.txt", b"\xff")
    with pytest.raises(ValueError, match="Upload a PDF"):
        extract_pages("test.exe", b"anything")
    pdf = PdfWriter()
    pdf.add_blank_page(width=100, height=100)
    output = io.BytesIO()
    pdf.write(output)
    with pytest.raises(ValueError, match="Scanned PDFs"):
        extract_pages("scan.pdf", output.getvalue())


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    app.state.retrieval.ollama = Embeddings()
    with TestClient(app) as client:
        yield client


def test_api_import_capture_complete_and_export(client):
    assert client.get("/").status_code == 200
    result = client.post("/api/documents", files={"file": ("guide.txt", b"Write down the asset identifier.")})
    assert result.status_code == 200
    assert client.get("/api/documents").json()[0]["chunks"] == 1
    document_id = result.json()["id"]
    assert client.get("/api/documents/" + document_id).json()["passages"][0]["page"] == 1
    note = client.post(
        "/api/chat",
        json={
            "request_id": "capture-test",
            "text": "Save a note: tag missing",
            "site": "North",
            "thread_id": client.post("/api/threads", json={}).json()["id"],
        },
    )
    assert note.status_code == 200
    assert client.get("/api/notes?site=South").json() == []
    task = client.post(
        "/api/tasks", json={"title": "Ask the contact", "site": "North", "due_date": "2026-10-05"}
    ).json()
    assert client.patch("/api/tasks/" + task["id"], json={"completed": True}).status_code == 200
    export = client.get("/api/export").json()
    assert len(export["notes"]) == 1
    assert export["tasks"][0]["completed"]
    assert client.delete("/api/documents/" + document_id).status_code == 200
    assert client.get("/api/documents").json() == []


def test_cross_origin_writes_and_rebinding_hosts_are_rejected(client):
    assert (
        client.post(
            "/api/notes", json={"text": "intrusion"}, headers={"Origin": "https://unrelated.example"}
        ).status_code
        == 403
    )
    assert client.get("/api/notes", headers={"Host": "unrelated.example"}).status_code == 403
    assert client.get("/api/notes").json() == []
    assert (
        client.post(
            "/api/notes", json={"text": "same origin"}, headers={"Origin": "http://testserver"}
        ).status_code
        == 200
    )


def test_voice_is_explicitly_unavailable_before_setup(client):
    response = client.post("/api/speak", json={"text": "Hello"})
    assert response.status_code == 400
    assert "setup" in response.json()["detail"]


def test_blank_fields_are_rejected(client):
    assert client.post("/api/notes", json={"text": "   "}).status_code == 400
    assert (
        client.post(
            "/api/chat", json={"request_id": "empty-message", "text": "  ", "thread_id": "missing"}
        ).status_code
        == 400
    )
    assert client.post("/api/tasks", json={"title": "x", "due_date": "2026-02-31"}).status_code == 400
