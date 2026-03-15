"""RAG knowledge base — scans documents, chunks, embeds, and searches via FAISS."""

import os
import time
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from .config import KNOWLEDGE_DIR

# Extraction helpers

def _extract_pdf(path: str) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(path: str) -> str:
    import docx
    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".doc": _extract_docx,
    ".txt": _extract_text,
    ".md": _extract_text,
}


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


class KnowledgeBase:
    """Singleton RAG index over local documents."""

    _instance = None

    @classmethod
    def get(cls) -> "KnowledgeBase":
        if cls._instance is None:
            cls._instance = cls()
            cls._instance.index_documents()
        return cls._instance

    def __init__(self):
        self._model = SentenceTransformer("all-MiniLM-L6-v2")
        self._index: faiss.IndexFlatL2 | None = None
        self._chunks: list[str] = []
        self._files: list[str] = []
        self._doc_count = 0
        self._last_indexed: float | None = None

    def index_documents(self):
        """Scan KNOWLEDGE_DIR and rebuild the FAISS index."""
        knowledge_path = Path(KNOWLEDGE_DIR)
        if not knowledge_path.exists():
            print(f"Knowledge dir not found: {KNOWLEDGE_DIR}")
            return

        all_chunks = []
        files_indexed = []

        for filepath in sorted(knowledge_path.iterdir()):
            ext = filepath.suffix.lower()
            if ext not in EXTRACTORS:
                continue
            try:
                text = EXTRACTORS[ext](str(filepath))
                chunks = _chunk_text(text)
                all_chunks.extend(chunks)
                files_indexed.append(filepath.name)
                print(f"  KB: indexed {filepath.name} -> {len(chunks)} chunks")
            except Exception as e:
                print(f"  KB: failed to index {filepath.name}: {e}")

        if not all_chunks:
            print("KB: no documents found to index")
            return

        embeddings = self._model.encode(all_chunks, show_progress_bar=False)
        embeddings = np.array(embeddings, dtype="float32")

        self._index = faiss.IndexFlatL2(embeddings.shape[1])
        self._index.add(embeddings)
        self._chunks = all_chunks
        self._files = files_indexed
        self._doc_count = len(files_indexed)
        self._last_indexed = time.time()

        print(f"KB: indexed {self._doc_count} docs, {len(self._chunks)} chunks")

    def search(self, query: str, top_k: int = 3) -> list[str]:
        if self._index is None or not self._chunks:
            return []

        q_emb = self._model.encode([query], show_progress_bar=False)
        q_emb = np.array(q_emb, dtype="float32")

        distances, indices = self._index.search(q_emb, min(top_k, len(self._chunks)))
        return [self._chunks[i] for i in indices[0] if i < len(self._chunks)]

    def get_status(self) -> dict:
        return {
            "doc_count": self._doc_count,
            "chunk_count": len(self._chunks),
            "files": self._files,
            "last_indexed": self._last_indexed,
            "indexed": self._index is not None,
        }
