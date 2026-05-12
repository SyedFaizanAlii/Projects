import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DEFAULT_JSON_PATH = Path(__file__).resolve().parent.parent / "ingestion" / "pubmed_documents.json"
DEFAULT_PERSIST_DIR = Path(__file__).resolve().parent.parent / "db" / "chroma_index"


class VectorStoreManager:
    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.persist_dir = Path(persist_dir or DEFAULT_PERSIST_DIR)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model
        self.embedding = HuggingFaceEmbeddings(model_name=self.embedding_model)

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name="medical_documents",
            metadata={"hnsw:space": "cosine"},
        )

    def load_documents_from_json(self, path: Optional[Path] = None) -> List[Dict[str, Any]]:
        path = Path(path or DEFAULT_JSON_PATH)
        if not path.exists():
            raise FileNotFoundError(f"PubMed JSON data not found at {path}")

        with path.open("r", encoding="utf-8") as handle:
            records = json.load(handle)

        documents = []
        for item in records:
            pmid = item.get("pmid", "unknown")
            doi = item.get("doi")
            category = item.get("category", "Unknown")
            title = item.get("title", "")
            publication_date = item.get("publication_date")
            source_url = item.get("source_url")
            chunks = item.get("chunks") or []

            if not chunks:
                text = "\n\n".join(filter(None, [title, item.get("abstract", "")]))
                chunks = [text] if text else []

            for index, chunk in enumerate(chunks):
                document_id = f"{pmid}-{index}-{uuid.uuid4().hex[:6]}"
                metadata = {
                    "specialty": category,
                    "pmid": pmid,
                    "doi": doi,
                    "title": title,
                    "publication_date": publication_date,
                    "source_url": source_url,
                    "chunk_index": index,
                }
                documents.append({
                    "id": document_id,
                    "text": chunk,
                    "metadata": metadata,
                })

        logger.info("Loaded %d chunked documents from %s", len(documents), path)
        return documents

    def index_documents(self, documents: List[Dict[str, Any]]) -> None:
        if not documents:
            logger.warning("No documents were provided for indexing.")
            return

        # Reset collection to avoid duplicate IDs on re-index
        try:
            self.client.delete_collection("medical_documents")
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name="medical_documents",
            metadata={"hnsw:space": "cosine"},
        )

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]

        logger.info("Generating embeddings for %d documents", len(texts))
        embeddings = self.embedding.embed_documents(texts)

        # Add in batches to respect ChromaDB's max batch size
        batch_size = 5000
        total = len(ids)
        logger.info("Adding %d documents to ChromaDB in batches of %d", total, batch_size)
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            self.collection.add(
                ids=ids[start:end],
                documents=texts[start:end],
                metadatas=metadatas[start:end],
                embeddings=embeddings[start:end],
            )
            logger.info("  Indexed batch %d-%d of %d", start + 1, end, total)

        logger.info("Successfully persisted %d documents into ChromaDB", total)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_embedding = self.embedding.embed_query(query)
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        hits = []
        for i, _id in enumerate(result.get("ids", [[]])[0]):
            hits.append(
                {
                    "id": _id,
                    "document": result.get("documents", [[]])[0][i] if i < len(result.get("documents", [[]])[0]) else "",
                    "metadata": result.get("metadatas", [[]])[0][i] if i < len(result.get("metadatas", [[]])[0]) else {},
                    "distance": result.get("distances", [[]])[0][i] if i < len(result.get("distances", [[]])[0]) else 0.0,
                }
            )
        return hits


def main() -> None:
    manager = VectorStoreManager()
    documents = manager.load_documents_from_json()
    manager.index_documents(documents)
    logger.info("Vector store ready at %s", manager.persist_dir)


if __name__ == "__main__":
    main()
