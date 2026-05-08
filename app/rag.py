from __future__ import annotations

import hashlib
from pathlib import Path

import chromadb
from openai import OpenAI
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


class RAGService:
    def __init__(self, chroma_path: Path, embedding_model: str, openai_api_key: str) -> None:
        self.client = chromadb.PersistentClient(path=str(chroma_path))
        self.collection = self.client.get_or_create_collection(name="assistant_knowledge")
        self.openai = OpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model

    def list_source_files(self, rag_source_dir: Path) -> list[Path]:
        return sorted(
            [
                p
                for p in rag_source_dir.iterdir()
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
        )

    def read_file_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        raise ValueError(f"Unsupported extension: {suffix}")

    def chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
        normalized = " ".join(text.split())
        if not normalized:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(start + chunk_size, len(normalized))
            chunks.append(normalized[start:end])
            if end == len(normalized):
                break
            start = max(0, end - overlap)
        return chunks

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = self.openai.embeddings.create(model=self.embedding_model, input=texts)
        return [item.embedding for item in response.data]

    def clear_filename(self, filename: str) -> None:
        matches = self.collection.get(where={"filename": filename})
        ids = matches.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)

    def upsert_file(self, path: Path) -> int:
        filename = path.name
        self.clear_filename(filename)

        text = self.read_file_text(path)
        chunks = self.chunk_text(text)
        if not chunks:
            return 0

        embeddings = self._embed(chunks)
        ids = [self._chunk_id(filename, index, chunk) for index, chunk in enumerate(chunks)]
        metadatas = [{"filename": filename, "chunk_index": i} for i, _ in enumerate(chunks)]
        self.collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)
        return len(chunks)

    def clear_all(self) -> None:
        self.client.delete_collection(name="assistant_knowledge")
        self.collection = self.client.get_or_create_collection(name="assistant_knowledge")

    def get_chunks_for_filename(self, filename: str) -> list[str]:
        result = self.collection.get(where={"filename": filename}, include=["documents", "metadatas"])
        docs = result.get("documents", []) or []
        metadatas = result.get("metadatas", []) or []
        pairs = sorted(
            [(meta.get("chunk_index", 0), doc) for meta, doc in zip(metadatas, docs)],
            key=lambda item: item[0],
        )
        return [doc for _, doc in pairs]

    def search(self, query: str, top_k: int = 4) -> list[str]:
        embedding = self._embed([query])[0]
        result = self.collection.query(query_embeddings=[embedding], n_results=top_k)
        docs_list = result.get("documents", [[]])
        return docs_list[0] if docs_list else []

    @staticmethod
    def _chunk_id(filename: str, index: int, chunk: str) -> str:
        digest = hashlib.sha1(chunk.encode("utf-8", errors="ignore")).hexdigest()[:12]
        return f"{filename}:{index}:{digest}"
