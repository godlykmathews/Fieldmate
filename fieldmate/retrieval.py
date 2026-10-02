import io
import math
import re
from dataclasses import dataclass
from hashlib import sha256

from pypdf import PdfReader


def extract_pages(name, content):
    suffix = name.rsplit(".", 1)[-1].lower()
    if suffix == "pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("Password-protected PDFs are not supported. Export an unlocked copy.")
            if len(reader.pages) > 300:
                raise ValueError("Use a document with no more than 300 pages for this prototype.")
            pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        except ValueError:
            raise
        except Exception as error:
            raise ValueError("This PDF could not be read. Try a text PDF, Markdown, or TXT file.") from error
    elif suffix in {"md", "txt"}:
        try:
            pages = [(1, content.decode("utf-8-sig"))]
        except UnicodeDecodeError as error:
            raise ValueError("Text documents must be UTF-8 encoded.") from error
    else:
        raise ValueError("Upload a PDF, Markdown, or TXT document.")
    if not any(text.strip() for _, text in pages):
        raise ValueError("No text was found. Scanned PDFs need OCR before importing.")
    return pages


def split_passages(pages, max_chars=1600):
    passages = []
    for page, text in pages:
        text = text.replace("\x00", "").replace("\r\n", "\n")
        paragraphs = re.split(r"\n\s*\n", text)
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            # Bounded word slices with overlap keep long PDF paragraphs under embedding context limits.
            words = paragraph.split()
            start = 0
            while start < len(words):
                end, size = start, 0
                while end < len(words) and (size + len(words[end]) < max_chars or end == start):
                    size += len(words[end]) + 1
                    end += 1
                passages.append((page, " ".join(words[start:end])))
                if end == len(words):
                    break
                start = max(start + 1, end - 30)
    return passages


def cosine(a, b):
    if len(a) != len(b) or not a or not b:
        return 0.0
    numerator = sum(x * y for x, y in zip(a, b))
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return numerator / denominator if denominator else 0.0


STOP_WORDS = set(
    "a an the what how when where which should do i we you my our it is are to for of on in "
    "and or can could would tell me about please does did with from this that have has".split()
)


def keywords(text):
    return set(re.findall(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", text.lower())) - STOP_WORDS


@dataclass
class Retrieval:
    store: object
    ollama: object
    settings: object

    def ingest(self, name, content):
        digest = sha256(content).hexdigest()
        existing = self.store.document_by_digest(digest)
        if existing:
            return {"id": existing["id"], "duplicate": True, "name": existing["name"]}
        pages = extract_pages(name, content)
        passages = split_passages(pages)
        if len(passages) > 2000:
            raise ValueError("This file has too many passages. Import smaller documents.")
        vectors = []
        for start in range(0, len(passages), 24):
            vectors.extend(self.ollama.embed([text for _, text in passages[start : start + 24]]))
        document_id = self.store.add_document(
            name,
            digest,
            len(pages),
            self.settings.embed_model,
            [(p, t, v) for (p, t), v in zip(passages, vectors)],
        )
        return {"id": document_id, "duplicate": False, "name": name, "chunks": len(passages)}

    def search(self, query, limit=5, category_id=None):
        chunks = self.store.chunks(self.settings.embed_model, category_id)
        if not chunks:
            return []
        vector = self.ollama.embed([query], query=True)[0]
        terms = keywords(query)
        ranked = []
        for chunk in chunks:
            similarity = cosine(vector, chunk["embedding"])
            lexical = len(terms & keywords(chunk["text"])) / max(1, len(terms))
            # Semantic gate avoids treating nearest neighbors as proof. Keyword overlap improves exact codes.
            if similarity < self.settings.min_similarity:
                continue
            ranked.append(
                {
                    "id": chunk["id"],
                    "document": chunk["name"],
                    "page": chunk["page"],
                    "text": chunk["text"],
                    "similarity": round(similarity, 4),
                    "score": 0.8 * similarity + 0.2 * lexical,
                }
            )
        return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]
