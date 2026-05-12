import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from graph.neo4j_builder import Neo4jGraph, NullNeo4jGraph
from graph.vector_store_manager import VectorStoreManager

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

DEFAULT_CHROMA_DIR = Path(__file__).resolve().parent.parent / "db" / "chroma_index"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

class HybridRetriever:
    """Combines ChromaDB vector search and Neo4j graph search for medical queries."""

    def __init__(
        self,
        chroma_persist_dir: Optional[Path] = None,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
        graph: Optional[Neo4jGraph] = None,
    ):
        self.chroma_persist_dir = chroma_persist_dir or DEFAULT_CHROMA_DIR
        self.embedding_model = embedding_model
        self.vector_manager: Optional[VectorStoreManager] = None
        self.graph = graph or Neo4jGraph.from_env()
        self.graph_is_active = not isinstance(self.graph, NullNeo4jGraph)

    def set_graph(self, graph: Neo4jGraph) -> None:
        self.graph = graph
        self.graph_is_active = not isinstance(self.graph, NullNeo4jGraph)

    def _ensure_vector_manager(self):
        if self.vector_manager is not None:
            return
        try:
            self.vector_manager = VectorStoreManager(
                persist_dir=self.chroma_persist_dir,
                embedding_model=self.embedding_model,
            )
        except Exception as exc:
            logger.warning("VectorStoreManager initialization failed: %s. Vector search disabled.", exc)
            self.vector_manager = None

    def vector_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return the top K most relevant research snippets from ChromaDB."""
        self._ensure_vector_manager()
        if self.vector_manager is None:
            return []
        return self.vector_manager.search(query, top_k=top_k)

    def graph_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Return direct Neo4j relationships that match the query."""
        if not self.graph_is_active:
            return []

        search_terms = self._extract_search_terms(query)
        graph_results: List[Dict[str, Any]] = []

        for term in search_terms:
            graph_results.extend(self.graph.find_direct_relationships(term, limit=top_k))

        if not graph_results:
            graph_results = self.graph.find_direct_relationships(query, limit=top_k)

        unique = []
        seen = set()
        for row in graph_results:
            key = (
                row.get("source"),
                row.get("relation"),
                row.get("target"),
            )
            if key not in seen:
                seen.add(key)
                unique.append(row)
            if len(unique) >= top_k:
                break

        return unique

    def hybrid_search(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """Build a hybrid retrieval result with both vector and graph evidence."""
        vector_results = self.vector_search(query, top_k=top_k)
        graph_results = self.graph_search(query, top_k=top_k)
        context = self.build_context(query, vector_results, graph_results)

        return {
            "query": query,
            "vector_results": vector_results,
            "graph_results": graph_results,
            "context": context,
            "has_evidence": bool(vector_results or graph_results),
        }

    def build_context(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        graph_results: List[Dict[str, Any]],
    ) -> str:
        """Combine vector and graph retrieval results into a unified context."""
        lines = [f"Query: {query}", "", "Research snippets:"]

        for item in vector_results:
            meta = item.get("metadata", {})
            lines.append(
                f"- [{meta.get('specialty', 'Unknown')}] {item.get('document', '')[:280]} "
                f"(PMID={meta.get('pmid', 'n/a')}, DOI={meta.get('doi', 'n/a')})"
            )

        if not vector_results:
            lines.append("- No relevant research snippets found in ChromaDB.")

        lines.append("")
        lines.append("Knowledge graph relationships:")

        for row in graph_results:
            lines.append(
                f"- {row.get('source', 'Unknown')} ({row.get('source_type', 'Entity')}) "
                f"{row.get('relation', 'RELATED')} {row.get('target', 'Unknown')} "
                f"({row.get('target_type', 'Entity')})"
            )

        if not graph_results:
            lines.append("- No direct graph relationships found in Neo4j.")

        return "\n".join(lines)

    @staticmethod
    def _extract_search_terms(text: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z0-9\-]+", text)
        stop_words = {
            "the",
            "and",
            "or",
            "of",
            "with",
            "for",
            "in",
            "on",
            "by",
            "to",
            "from",
            "a",
            "an",
            "patient",
            "patients",
            "clinical",
            "medical",
            "treatment",
            "disease",
            "symptom",
        }
        terms = [token for token in tokens if len(token) > 3 and token.lower() not in stop_words]
        return terms[:5]

    @staticmethod
    def _extract_entities(text: str) -> List[str]:
        """Extract medical entities (diseases, drugs, symptoms) from query text."""
        text_lower = text.lower()
        entities = []
        
        # Medical keywords to extract
        medical_terms = {
            "disease": ["disease", "diabetes", "cancer", "heart failure", "kidney disease", "hypertension"],
            "symptom": ["symptom", "fever", "pain", "fatigue", "shortness of breath", "chest pain"],
            "drug": ["drug", "medication", "treatment", "therapy", "inhibitor", "antibiotic"],
        }
        
        for category, terms in medical_terms.items():
            for term in terms:
                if term in text_lower:
                    entities.append(term)
                    break
        
        # Also add extracted search terms
        tokens = re.findall(r"[A-Za-z0-9\-]+", text)
        stop_words = {
            "the", "and", "or", "of", "with", "for", "in", "on", "by", "to", "from",
            "a", "an", "patient", "patients", "clinical", "medical", "treatment",
            "disease", "symptom",
        }
        terms = [token for token in tokens if len(token) > 3 and token.lower() not in stop_words]
        entities.extend(terms)
        
        return list(set(entities))[:10]
